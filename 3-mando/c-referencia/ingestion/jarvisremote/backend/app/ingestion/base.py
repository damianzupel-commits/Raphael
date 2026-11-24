"""Contrato reusable para Raphael Intel (ver docs/SPEC-RAPHAEL-INTEL.md, §3).

Generaliza el patrón que ya usa `youtube_playlist.py` (traer → resumir → guardar
nota → deduplicar) para CUALQUIER fuente pública. Una fuente implementa `fetch()`
devolviendo `IntelItem`s normalizados; el driver `ingest_source()` se encarga del
resto (dedup, resumen con LLM, guardado en el vault), igual para todas.

Testeable: `fetch`, `call_llm` y `save_note` se inyectan, así el driver completo se
prueba con fakes sin tocar red, LLM ni vault.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..config import settings
from ..llm_client import client
from ..obsidian import vault

# Tope de caracteres del texto (abstract/cuerpo) que se le manda al LLM, mismo
# criterio que el ingester de playlist: no reventar el presupuesto de contexto.
_MAX_TEXT_CHARS = 12000


@dataclass
class IntelItem:
    """Un ítem normalizado de cualquier fuente (paper, noticia, evento, etc.)."""

    source_id: str          # ID estable único DENTRO de la fuente (para dedup)
    title: str
    url: str
    source: str             # nombre de la fuente, ej. "arxiv"
    domain: str             # dominio, ej. "ciencia"
    text: str = ""          # abstract / cuerpo a resumir
    authors: list[str] = field(default_factory=list)
    published: str = ""     # fecha ISO si la hay
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntelResult:
    source: str
    domain: str
    total_fetched: int = 0
    already_present: list[str] = field(default_factory=list)  # source_ids ya en el vault
    created: list[dict] = field(default_factory=list)         # {source_id, note_id, title}
    errors: list[dict] = field(default_factory=list)          # {source_id, title, error}

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "domain": self.domain,
            "total_fetched": self.total_fetched,
            "created_count": len(self.created),
            "already_present_count": len(self.already_present),
            "errors_count": len(self.errors),
            "created": self.created,
            "already_present": self.already_present,
            "errors": self.errors,
        }


class SourceIngester(Protocol):
    """Una fuente de intel. Solo tiene que saber TRAER ítems nuevos ya normalizados;
    el resumen y el guardado los hace el driver, igual para todas."""

    name: str    # ej. "arxiv"
    domain: str  # ej. "ciencia"

    def fetch(self, query: str, limit: int) -> list[IntelItem]: ...


async def _default_call_llm(messages: list[dict]) -> str:
    """Único punto que le pega al LLM -- reusa el cliente/modelo ya configurados,
    no crea uno nuevo. Aislado para que los tests lo mockeen."""
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.reserved_response_tokens,
    )
    return response.choices[0].message.content or ""


def _summary_messages(item: IntelItem) -> list[dict]:
    system = (
        "Sos el asistente Raphael resumiendo una fuente de información para el vault de "
        "conocimiento de Damian. Respondé SOLO con un objeto JSON válido (sin texto extra, sin "
        "markdown, sin ```), con estas claves exactas:\n"
        '  "title": un título curado y descriptivo en español para la nota (que describa el CONTENIDO).\n'
        '  "category": una palabra/frase corta en minúsculas para la categoría temática '
        "(ej. ia, ciberseguridad, neurociencia, biotecnologia, economia, geopolitica).\n"
        '  "summary": un resumen denso de 3 a 5 oraciones, en español, en un solo párrafo, '
        "que capte el aporte real (qué se hizo, qué se encontró, por qué importa).\n"
        '  "key_topics": una lista de 3 a 6 strings con los temas clave (frases cortas).'
    )
    authors = ", ".join(item.authors[:8]) or "desconocidos"
    user = (
        f'Fuente: {item.source} ({item.domain})\n'
        f'Título original: "{item.title}"\n'
        f"Autores: {authors}\n\n"
        f"Texto:\n{item.text[:_MAX_TEXT_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_summary(raw: str, item: IntelItem) -> dict:
    """Parsea el JSON del LLM, tolerante a fences/ruido/claves faltantes. Nunca
    rompe: cae a defaults razonables."""
    text = raw.strip()
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if fence:
        text = fence.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}
    title = (data.get("title") or "").strip() or item.title
    category = (data.get("category") or "").strip().lower() or "general"
    summary = (data.get("summary") or "").strip() or "(sin resumen generado)"
    topics = data.get("key_topics") or []
    if not isinstance(topics, list):
        topics = []
    topics = [str(t).strip() for t in topics if str(t).strip()]
    return {"title": title, "category": category, "summary": summary, "key_topics": topics}


def build_note_content(item: IntelItem, summary: dict) -> str:
    """Markdown de la nota, mismo esqueleto que las notas del vault
    (## Fuente / ## Resumen / ## Temas clave / ## Notas relacionadas)."""
    authors = ", ".join(item.authors[:8]) or "desconocidos"
    published = item.published or "s/f"
    parts = [
        f"Resumen automático de una fuente de {item.domain} ({item.source}).",
        "",
        "## Fuente",
        f"- {item.source}: {item.url}",
        f"- Autores: {authors}",
        f"- Publicado: {published}",
        "- Generado con: resumen automático",
        "",
        "## Resumen",
        summary["summary"],
        "",
        "## Temas clave",
    ]
    if summary["key_topics"]:
        parts.extend(f"- {t}" for t in summary["key_topics"])
    else:
        parts.append("- (no se extrajeron temas clave)")
    parts.extend(
        [
            "",
            "## Notas relacionadas",
            f"- [[Índice: {summary['category']}]]",
            f"- [[Intel: {item.domain}]]",
        ]
    )
    return "\n".join(parts)


def existing_source_ids(id_regex: re.Pattern[str]) -> set[str]:
    """IDs de ítems que YA tienen nota en el vault, parseados del cuerpo de las
    notas del autor 'jarvis' con `id_regex` (grupo 1 = el id). Hace idempotente
    la ingesta: se detecta por ID de fuente, no por título."""
    ids: set[str] = set()
    for note in vault.list_notes(author="jarvis"):
        for match in id_regex.finditer(note.content):
            ids.add(match.group(1))
    return ids


async def ingest_source(
    ingester: SourceIngester,
    query: str,
    limit: int,
    *,
    already_ids: set[str],
    call_llm: Callable[[list[dict]], Awaitable[str]] | None = None,
    save_note: Callable[..., Any] | None = None,
    link_category: Callable[..., Any] | None = None,
) -> IntelResult:
    """Driver reusable: trae ítems de la fuente, saltea los que ya están, resume
    con el LLM y guarda la nota. Todo lo externo (LLM, vault) es inyectable para
    testear. Un ítem que falla se registra y NO tira abajo la corrida."""
    call_llm = call_llm or _default_call_llm
    save_note = save_note or vault.save_note
    link_category = link_category or vault.link_note_to_category_index

    items = ingester.fetch(query, limit)
    result = IntelResult(source=ingester.name, domain=ingester.domain, total_fetched=len(items))

    seen: set[str] = set()
    for item in items:
        if item.source_id in already_ids or item.source_id in seen:
            result.already_present.append(item.source_id)
            continue
        seen.add(item.source_id)
        try:
            raw = await call_llm(_summary_messages(item))
            summary = parse_summary(raw, item)
            content = build_note_content(item, summary)
            try:
                link_category(summary["title"], category=summary["category"], author="jarvis")
            except Exception:  # noqa: BLE001 -- el link al hub es best-effort, no debe romper la ingesta
                pass
            note = save_note(
                title=summary["title"],
                content=content,
                author="jarvis",
                tags=["intel", item.domain, item.source, summary["category"]],
                category=summary["category"],
                extra={"fuente": item.source, "dominio": item.domain, "url": item.url},
            )
            result.created.append(
                {"source_id": item.source_id, "note_id": getattr(note, "id", None), "title": getattr(note, "title", summary["title"])}
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(
                {"source_id": item.source_id, "title": item.title, "error": f"{type(exc).__name__}: {exc}"}
            )
    return result
