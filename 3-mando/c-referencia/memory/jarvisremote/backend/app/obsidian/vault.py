"""Vault de notas estilo Obsidian: archivos Markdown reales con frontmatter
YAML, organizados en `settings.obsidian_vault_path` -- abribles con Obsidian
de verdad si el usuario quiere, no un formato propietario.

Evolución de `app/tools/reflect.py` (que queda intacto, sigue siendo un log
rápido de una línea vía JSONL -- ver decisión en la sesión que agregó este
módulo): acá cada nota es un archivo propio con título, tags, autor y
contenido largo, y coexisten notas de dos autores distintos sin mezclarse --
la separación es doble a propósito: carpeta (`jarvis/` vs `human/`) *y* campo
`author` en el frontmatter, así un archivo movido a mano entre carpetas sigue
siendo identificable, y un filtro por metadata no depende de en qué carpeta
esté.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from ..config import settings
from . import embeddings
from . import profile as _profile

AUTHORS = ("jarvis", "human")

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")

# Umbral de similitud coseno para considerar una nota semánticamente
# relevante (embeddings de nomic-embed-text: notas sin relación entre sí
# suelen rondar 0.1-0.3, notas realmente relacionadas superan claramente
# 0.4 -- confirmado empíricamente contra este vault, ver README). Sin este
# corte, search_notes devolvería SIEMPRE algún resultado semántico (el
# coseno entre dos embeddings reales rara vez es negativo o cero), lo que
# rompería el contrato de "sin resultados si no hay nada relevante".
_SEMANTIC_MIN_SCORE = 0.4

# Penalización leve al score semántico de notas tag="investigacion" (las que
# crea `research_topic`, ver app/tools/research.py) SOLO dentro de
# `search_notes` -- no en `find_related_notes`, que research_topic usa para
# decidir si un tema ya está cubierto y necesita el score real sin ajustar.
# Bug real 2026-08-10: en un test real, una nota de investigación recién
# creada (título calcado de la query, ej. investigar "Fabric mod
# development" y después buscar exactamente "Fabric mod development")
# rankeó #1 por delante de una nota más específica y curada sobre el mismo
# tema, porque el título coincide casi literal con la query -- el modelo
# nunca llegó a leer la nota específica que sí tenía la respuesta. Esta
# penalización no resuelve ese caso puntual (ambas notas eran de
# investigación), pero sí ayuda en el caso general: una nota curada/manual
# sobre el mismo tema no debería perder contra un volcado de investigación
# más ruidoso solo por estar más "fresco" en similitud de texto.
_INVESTIGACION_TAG_PENALTY = 0.85


def _embedding_text(title: str, content: str, tags: list[str], category: str = "") -> str:
    return f"{title}\n{category}\n{' '.join(tags)}\n{content}"


@dataclass
class VaultNote:
    id: str  # "<author>/<slug>", único, también nombre de archivo relativo al vault
    title: str
    author: str
    tags: list[str] = field(default_factory=list)
    # Categoría principal del tema -- a diferencia de `tags` (múltiples,
    # intersección libre), esto es UN solo valor por nota (partición
    # estricta, el equivalente en properties a "en qué carpeta viviría esta
    # nota"). Se guarda como property de frontmatter en vez de una carpeta
    # física nueva porque la carpeta de primer nivel (jarvis/human) ya está
    # comprometida a nivel de diseño con la separación de autoría (ver
    # docstring del módulo) -- no se puede reusar ese mismo nivel para dos
    # particiones distintas a la vez sin ambigüedad.
    category: str = ""
    created: str = ""
    updated: str = ""
    content: str = ""

    @property
    def links(self) -> list[str]:
        return _WIKILINK_RE.findall(self.content)

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "tags": self.tags,
            "category": self.category,
            "created": self.created,
            "updated": self.updated,
        }

    def to_dict(self) -> dict:
        return {**self.to_summary_dict(), "content": self.content, "links": self.links}


def _vault_root() -> Path:
    # Respeta el override de perfil activo (ver app/obsidian/profile.py) si
    # hay uno seteado para esta tarea de asyncio -- por default (sin
    # perfil activo) sigue siendo el vault de siempre, sin cambios de
    # comportamiento.
    root = Path(_profile.current_vault_path(settings.obsidian_vault_path))
    for author in AUTHORS:
        (root / author).mkdir(parents=True, exist_ok=True)
    return root


def _slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "nota"


# Carpetas de primer nivel que el lector del vault IGNORA: las que empiezan con
# "." (sistema de Obsidian: .obsidian/.trash) o "_" (plantillas), más cualquiera
# que el usuario quiera dejar afuera (ver settings.obsidian_excluded_dirs).
def _excluded_dirs() -> set[str]:
    extra = {d.strip() for d in str(getattr(settings, "obsidian_excluded_dirs", "")).split(",") if d.strip()}
    return extra


def _note_path(note_id: str) -> Path:
    # id = ruta relativa al vault SIN .md (ej. "jarvis/mi-nota" o
    # "10-Raphael-Seguridad/attack/foo"). Se generaliza del esquema viejo
    # "<author>/<slug>" (que sigue valiendo igual) para soportar las carpetas
    # temáticas del vault, no solo jarvis/human.
    if not note_id or note_id.startswith("/") or ".." in note_id.split("/"):
        raise ValueError(f"id de nota inválido: '{note_id}'")
    root = _vault_root().resolve()
    path = (root / f"{note_id}.md").resolve()
    if root != path and root not in path.parents:
        raise ValueError(f"id de nota fuera del vault: '{note_id}'")
    return path


def _note_from_path(path: Path, author: str | None = None) -> VaultNote:
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    note_id = path.resolve().relative_to(_vault_root().resolve()).with_suffix("").as_posix()
    # Autor: la carpeta de primer nivel si es jarvis/human; si no (carpeta
    # temática), lo que diga el frontmatter, o "human" por default (son notas
    # curadas por Damian). Raphael solo ESCRIBE en jarvis/.
    first = note_id.split("/", 1)[0]
    default_author = first if first in AUTHORS else "human"
    return VaultNote(
        id=note_id,
        title=post.get("title", path.stem),
        author=post.get("author", author or default_author),
        tags=list(post.get("tags", []) or []),
        category=post.get("category", "") or "",
        created=post.get("created", ""),
        updated=post.get("updated", ""),
        content=post.content,
    )


def save_note(
    title: str,
    content: str,
    author: str,
    tags: list[str] | None = None,
    category: str = "",
    note_id: str | None = None,
    extra: dict | None = None,
) -> VaultNote:
    # `extra` (agregado 2026-08-18): properties de frontmatter adicionales,
    # opcionales, para metadata que no encaja en el modelo fijo (title/author/
    # tags/category/created/updated). Nace del pipeline de YouTube, que necesita
    # persistir `relevancia`/`relevancia_score` en el frontmatter sin sumar
    # campos al dataclass VaultNote ni tocar a los demás callers. Default None =
    # comportamiento idéntico al de antes. `_note_from_path` ignora las keys que
    # no conoce, así que estas properties viven en el .md pero no afectan la
    # lectura ni los embeddings.
    if author not in AUTHORS:
        raise ValueError(f"author debe ser uno de {AUTHORS}, recibido '{author}'")

    now = datetime.now(timezone.utc).isoformat()
    tags = tags or []

    if note_id is not None:
        note_id_author = note_id.split("/", 1)[0]
        # Guarda SOLO entre carpetas de autor (jarvis/human): no se puede escribir
        # una nota de otro autor-folder. Una nota TEMÁTICA (prefijo no-autor) se
        # edita en su propia ubicación -- ahí no aplica el cruce de autoría.
        if note_id_author in AUTHORS and note_id_author != author:
            raise ValueError(f"note_id '{note_id}' pertenece al autor '{note_id_author}', no a '{author}'")
        path = _note_path(note_id)
        created = now
        if path.is_file():
            existing = _note_from_path(path, author)
            created = existing.created or now
    else:
        slug = _slugify(title)
        path = _vault_root() / author / f"{slug}.md"
        # Evita pisar una nota existente con el mismo título -- le agrega un
        # sufijo numérico hasta encontrar un nombre libre.
        counter = 2
        while path.is_file():
            path = _vault_root() / author / f"{slug}-{counter}.md"
            counter += 1
        created = now

    metadata = dict(extra or {})
    post = frontmatter.Post(
        content, title=title, author=author, tags=tags, category=category, created=created, updated=now, **metadata
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    note_id = path.resolve().relative_to(_vault_root().resolve()).with_suffix("").as_posix()
    embeddings.update_note_embedding(note_id, _embedding_text(title, content, tags, category))

    return VaultNote(
        id=note_id, title=title, author=author, tags=tags, category=category, created=created, updated=now, content=content
    )


def read_note(note_id: str) -> VaultNote:
    path = _note_path(note_id)
    if not path.is_file():
        raise FileNotFoundError(f"Nota '{note_id}' no existe")
    return _note_from_path(path)


def _iter_topical_notes(root: Path):
    """Todas las .md de las carpetas TEMÁTICAS del vault (recursivo), es decir todo
    menos jarvis/, human/ y las carpetas excluidas (. / _ / settings). Son las notas
    curadas por Damian (seguridad, conciencia, biotec, etc.), que se leen como autor
    'human'. Un archivo que no se puede leer se saltea (no tumba la lista entera)."""
    excluded = _excluded_dirs()
    # Modo prueba: NO tocar material personal -> además de lo excluido, saca las carpetas
    # sensibles (Fénix), así las pruebas corren solo sobre lo técnico/público.
    from .. import testmode

    if testmode.is_on():
        excluded = excluded | {d.strip() for d in str(settings.obsidian_sensitive_dirs).split(",") if d.strip()}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name in AUTHORS or name.startswith(".") or name.startswith("_") or name in excluded:
            continue
        for path in sorted(child.rglob("*.md")):
            yield path


def list_notes(author: str | None = None, tag: str | None = None) -> list[VaultNote]:
    root = _vault_root()
    authors = [author] if author else list(AUTHORS)
    notes = []
    for a in authors:
        for path in sorted((root / a).glob("*.md")):
            notes.append(_note_from_path(path, a))
    # Notas temáticas del vault (autor 'human'): se incluyen salvo que se pida
    # explícitamente otro autor. Vault único de verdad: Raphael lee TODO (2026-10-05).
    if author in (None, "human"):
        for path in _iter_topical_notes(root):
            try:
                notes.append(_note_from_path(path))
            except Exception:  # noqa: BLE001 -- un .md ilegible no debe romper la lista
                continue
    if tag:
        notes = [n for n in notes if tag in n.tags]
    notes.sort(key=lambda n: n.updated, reverse=True)
    return notes


def _keyword_score(query_words: set[str], note: VaultNote) -> int:
    haystack = f"{note.title} {note.content} {' '.join(note.tags)}".lower()
    haystack_words = set(haystack.split())
    return len(query_words & haystack_words)


logger = logging.getLogger("jarvis.obsidian.vault")

# Bonus por overlap de palabras clave sumado al score semántico: una nota que
# coincide en significado Y en las palabras exactas de la query debe rankear por
# encima de una que solo coincide en significado. Chico a propósito (el semántico
# manda); satura a 3 palabras para que un título que repite la query no domine.
_KEYWORD_BONUS_PER_WORD = 0.03
_KEYWORD_BONUS_CAP = 3


@dataclass
class SearchDiagnostics:
    """Metadata de una búsqueda del vault, para que el caller pueda avisar cuando
    la búsqueda corrió en modo DEGRADADO (keyword-only, sin embeddings) en vez de
    fingir que todo anduvo. Motivado por el bug real 2026-09-04: con LM Studio
    caído, `search_notes` degradaba a keyword SIN avisar (ver QW-5 en el roadmap)."""

    embeddings_available: bool  # ¿respondió el server de embeddings?
    index_populated: bool  # ¿el índice de vectores tiene algo?
    mode: str  # "semantic" | "keyword-only"
    degraded_reason: str | None  # por qué cayó a keyword, si aplica
    total_matched: int
    returned: int


def search_notes_ranked(
    query: str, author: str | None = None, limit: int = 10
) -> tuple[list[VaultNote], SearchDiagnostics]:
    """Como `search_notes`, pero además devuelve un `SearchDiagnostics` con si la
    búsqueda fue semántica o cayó a keyword-only (y por qué). Ranking híbrido:
    dentro del nivel semántico, el score es coseno + un bonus acotado por
    coincidencia de palabras, así una nota fuerte en AMBAS señales rankea arriba.
    Los dos niveles (semántico > keyword-only) se mantienen: una nota sin embedding
    disponible no desaparece, sigue apareciendo por keyword."""
    query_words = set(query.lower().split())
    query_vector = embeddings.get_embedding(query)
    embeddings_available = query_vector is not None
    index = embeddings.load_index() if embeddings_available else {}
    index_populated = bool(index)

    degraded_reason: str | None = None
    if not embeddings_available:
        degraded_reason = (
            f"el server de embeddings (LM Studio en {settings.embedding_base_url}) no respondió"
        )
        logger.warning(
            "Búsqueda del vault en MODO DEGRADADO (keyword-only): %s. Los resultados pueden ser "
            "peores que con búsqueda semántica -- prendé LM Studio con el modelo de embeddings cargado.",
            degraded_reason,
        )
    elif not index_populated:
        degraded_reason = (
            "el índice de embeddings está vacío -- corré un reindex (vault.reindex_all) "
            "para habilitar la búsqueda semántica"
        )
        logger.warning("Búsqueda del vault en MODO DEGRADADO (keyword-only): %s.", degraded_reason)

    semantic_tier: list[tuple[float, int, VaultNote]] = []
    keyword_tier: list[tuple[int, VaultNote]] = []
    for note in list_notes(author=author):
        kw_score = _keyword_score(query_words, note)
        note_vector = index.get(note.id)
        if query_vector is not None and note_vector is not None:
            sem_score = embeddings.cosine_similarity(query_vector, note_vector)
            if "investigacion" in note.tags:
                sem_score *= _INVESTIGACION_TAG_PENALTY
            if sem_score >= _SEMANTIC_MIN_SCORE or kw_score > 0:
                # Score híbrido: semántico + bonus acotado por coincidencia de palabras.
                combined = sem_score + min(kw_score, _KEYWORD_BONUS_CAP) * _KEYWORD_BONUS_PER_WORD
                semantic_tier.append((combined, kw_score, note))
        elif kw_score > 0:
            keyword_tier.append((kw_score, note))

    semantic_tier.sort(key=lambda item: (item[0], item[1]), reverse=True)
    keyword_tier.sort(key=lambda item: item[0], reverse=True)

    ranked = [note for _, _, note in semantic_tier] + [note for _, note in keyword_tier]
    results = ranked[:limit]
    used_semantic = embeddings_available and index_populated and bool(semantic_tier)
    diagnostics = SearchDiagnostics(
        embeddings_available=embeddings_available,
        index_populated=index_populated,
        mode="semantic" if used_semantic else "keyword-only",
        degraded_reason=degraded_reason,
        total_matched=len(ranked),
        returned=len(results),
    )
    return results, diagnostics


def search_notes(query: str, author: str | None = None, limit: int = 10) -> list[VaultNote]:
    """Busca notas por similitud semántica (coseno sobre embeddings locales,
    ver `app/obsidian/embeddings.py`) con keyword overlap como fallback y
    complemento. Wrapper de `search_notes_ranked` que devuelve solo la lista
    (para los callers que no necesitan el diagnóstico de modo degradado).

    Ranking: cada nota queda en uno de dos niveles, semántico por encima de
    keyword-only, así una nota sin relación textual pero con el mismo
    significado (ej. "falla de auth" vs "bug de login") aparece, mientras
    que una nota con overlap de palabras pero embedding no disponible (LM
    Studio caído, nota nunca indexada) no desaparece de los resultados.
    """
    return search_notes_ranked(query, author=author, limit=limit)[0]


def find_related_notes(query: str, author: str | None = None, limit: int = 5) -> list[tuple[VaultNote, float]]:
    """Como `search_notes`, pero devuelve también el score de similitud
    semántica de cada nota (0.0 cuando el match viene solo de keyword
    overlap -- sin embedding de query o de la nota). Pensado para
    `research_topic` (app/tools/research.py), que necesita el score real
    para decidir si un tema ya está bien cubierto en el vault, algo que la
    lista plana de `search_notes` no expone."""
    query_words = set(query.lower().split())
    query_vector = embeddings.get_embedding(query)
    index = embeddings.load_index() if query_vector is not None else {}

    scored: list[tuple[float, int, VaultNote]] = []
    for note in list_notes(author=author):
        kw_score = _keyword_score(query_words, note)
        note_vector = index.get(note.id)
        sem_score = 0.0
        if query_vector is not None and note_vector is not None:
            sem_score = embeddings.cosine_similarity(query_vector, note_vector)
        if sem_score >= _SEMANTIC_MIN_SCORE or kw_score > 0:
            scored.append((sem_score, kw_score, note))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [(note, sem_score) for sem_score, _, note in scored[:limit]]


def link_note_to_category_index(note_title: str, category: str, author: str = "jarvis") -> VaultNote:
    """Mantiene una nota "índice" tipo MOC (map of content) por categoría --
    mismo patrón que la nota humana ya presente en este vault,
    `jarvis/ciberseguridad-indice-y-mapa-de-contenidos`, generalizado para
    que cualquier categoría tenga la suya. La crea si es la primera nota de
    esa categoría, o le agrega un wikilink a `note_title` si no lo tiene ya.

    Pensado para que ninguna nota nueva quede huérfana o aislada del resto
    del grafo (ver app/tools/research.py) aunque sea la primera de su
    categoría: en vez de depender de encontrar una nota semánticamente
    parecida (que puede no existir todavía), toda nota queda conectada como
    mínimo al hub de su categoría, y el hub queda conectado a todas las
    notas de esa categoría."""
    index_title = f"Índice: {category}"
    index_id = f"{author}/{_slugify(index_title)}"
    link_line = f"- [[{note_title}]]"

    try:
        index_note = read_note(index_id)
    except FileNotFoundError:
        content = f"Notas de la categoría **{category}**.\n\n{link_line}"
        return save_note(title=index_title, content=content, author=author, tags=["indice"], category=category)

    if link_line in index_note.content:
        return index_note

    content = index_note.content.rstrip("\n") + f"\n{link_line}\n"
    return save_note(
        title=index_title, content=content, author=author, tags=index_note.tags, category=category, note_id=index_note.id
    )


def delete_note(note_id: str) -> None:
    path = _note_path(note_id)
    if not path.is_file():
        raise FileNotFoundError(f"Nota '{note_id}' no existe")
    path.unlink()
    embeddings.remove_note_embedding(note_id)


def reindex_all() -> dict[str, int]:
    """Recalcula el embedding de TODAS las notas del vault -- backfill para
    notas creadas antes de que este módulo existiera, o para recuperarse de
    un índice corrupto/vacío. Ver `app/obsidian/embeddings.py::reindex_all`."""
    notes = list_notes()
    pairs = [(note.id, _embedding_text(note.title, note.content, note.tags, note.category)) for note in notes]
    return embeddings.reindex_all(pairs)


def build_graph() -> dict:
    """Nodos = todas las notas; edges = wikilinks resueltos por título (igual
    que el grafo real de Obsidian). Un link a un título que no existe se
    ignora -- no fabricamos un nodo fantasma para él."""
    notes = list_notes()
    by_title = {note.title.strip().lower(): note.id for note in notes}

    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for note in notes:
        for link_title in note.links:
            target_id = by_title.get(link_title.strip().lower())
            if target_id is None or target_id == note.id:
                continue
            key = tuple(sorted((note.id, target_id)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": note.id, "target": target_id})

    return {"nodes": [n.to_summary_dict() for n in notes], "edges": edges}
