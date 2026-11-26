"""Vault de notas estilo Obsidian: archivos Markdown reales con frontmatter YAML, abribles con Obsidian de verdad.

Dos autores que no se mezclan: carpeta (`jarvis/` lo escribe Raphael, `human/` lo escribe Damián) y campo `author` en
el frontmatter. Las carpetas temáticas del vault (seguridad, biotec…) se leen como autor `human`; Raphael solo ESCRIBE
en `jarvis/`. Un archivo ilegible se saltea: no tumba la lista. Cada instalación tiene su propio vault (una carpeta).

Portado de `app/obsidian/vault.py` de JarvisRemote, sin estado global: el vault es un objeto con su carpeta.
"""

from __future__ import annotations

import re
import threading
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import yaml

from .textutil import slugify, tokens

AUTHORS = ("jarvis", "human")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
_FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)

# Cache de notas ya leídas, por (vault, archivo) y validada con la fecha de modificación y el tamaño: con un vault de cientos
# de notas (Vault-Fenix: ~900) releer y parsear todo en cada consulta es lo que más pesa. Es de módulo a propósito: las tools
# arman un Vault nuevo en cada llamada. Un archivo que cambia (por Obsidian o por otro programa) se vuelve a leer solo.
_CACHE: dict[tuple[str, str], tuple[int, int, Note]] = {}
_CACHE_LOCK = threading.Lock()


@dataclass
class Note:
    id: str                    # "<carpeta>/<slug>": ruta relativa al vault sin .md
    title: str
    author: str
    tags: list[str] = field(default_factory=list)
    category: str = ""
    created: str = ""
    updated: str = ""
    content: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def links(self) -> list[str]:
        return _WIKILINK.findall(self.content)

    @property
    def folder(self) -> str:
        return self.id.split("/", 1)[0]

    def summary(self) -> dict:
        return {"id": self.id, "title": self.title, "author": self.author, "tags": self.tags, "category": self.category,
                "created": self.created, "updated": self.updated}

    def to_dict(self) -> dict:
        return {**self.summary(), "content": self.content, "links": self.links}


class Vault:
    def __init__(self, root: str | Path, *, now: Callable[[], datetime] = datetime.now,
                 excluded_dirs: tuple[str, ...] | list[str] = ()) -> None:
        self.root = Path(root)
        self._now = now
        self._excluded = {d.strip() for d in excluded_dirs if d.strip()}

    # --- rutas
    def ensure(self) -> Path:
        for a in AUTHORS:
            (self.root / a).mkdir(parents=True, exist_ok=True)
        return self.root

    def _path(self, note_id: str) -> Path:
        if not note_id or note_id.startswith("/") or ".." in note_id.replace("\\", "/").split("/"):
            raise ValueError(f"id de nota inválido: '{note_id}'")
        root = self.root.resolve()
        path = (root / f"{note_id}.md").resolve()
        if root not in path.parents:
            raise ValueError(f"id de nota fuera del vault: '{note_id}'")
        return path

    def _topical_dirs(self) -> Iterator[Path]:
        if not self.root.is_dir():
            return
        for child in sorted(self.root.iterdir()):
            n = child.name
            if child.is_dir() and n not in AUTHORS and not n.startswith((".", "_")) and n not in self._excluded:
                yield child

    # --- leer
    def _read(self, path: Path) -> Note:
        key = (str(self.root), str(path))
        st = path.stat()
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return replace(hit[2], tags=list(hit[2].tags), extra=dict(hit[2].extra))
        note = self._parse(path)
        with _CACHE_LOCK:
            _CACHE[key] = (st.st_mtime_ns, st.st_size, note)
        return replace(note, tags=list(note.tags), extra=dict(note.extra))

    def _forget(self, path: Path) -> None:
        with _CACHE_LOCK:
            _CACHE.pop((str(self.root), str(path)), None)

    def _parse(self, path: Path) -> Note:
        text = path.read_text(encoding="utf-8")
        m = _FRONT.match(text)
        meta: dict = {}
        body = text
        if m:
            try:
                loaded = yaml.safe_load(m.group(1)) or {}
                meta = loaded if isinstance(loaded, dict) else {}
            except yaml.YAMLError:
                meta = {}
            body = m.group(2)
        note_id = path.resolve().relative_to(self.root.resolve()).with_suffix("").as_posix()
        first = note_id.split("/", 1)[0]
        known = {"title", "author", "tags", "category", "created", "updated"}
        return Note(id=note_id, title=str(meta.get("title") or path.stem),
                    author=str(meta.get("author") or (first if first in AUTHORS else "human")),
                    tags=[str(t) for t in (meta.get("tags") or [])], category=str(meta.get("category") or ""),
                    created=str(meta.get("created") or ""), updated=str(meta.get("updated") or ""), content=body,
                    extra={k: v for k, v in meta.items() if k not in known})

    def read(self, note_id: str) -> Note:
        path = self._path(note_id)
        if not path.is_file():
            raise FileNotFoundError(f"la nota '{note_id}' no existe")
        return self._read(path)

    def exists(self, note_id: str) -> bool:
        try:
            return self._path(note_id).is_file()
        except ValueError:
            return False

    def list_notes(self, author: str | None = None, tag: str | None = None) -> list[Note]:
        notes: list[Note] = []
        for a in [author] if author in AUTHORS else (AUTHORS if author is None else ()):
            for p in sorted((self.root / a).glob("*.md")):
                notes.append(self._safe(p))
        if author in (None, "human"):
            for d in self._topical_dirs():
                notes.extend(self._safe(p) for p in sorted(d.rglob("*.md")))
        out = [n for n in notes if n is not None and (not tag or tag in n.tags)]
        out.sort(key=lambda n: n.updated, reverse=True)
        return out

    def _safe(self, path: Path) -> Note | None:
        try:
            return self._read(path)
        except (OSError, UnicodeDecodeError, ValueError):
            return None

    # --- escribir
    def save(self, title: str, content: str, author: str, tags: list[str] | None = None, category: str = "",
             note_id: str | None = None, extra: dict | None = None) -> Note:
        if author not in AUTHORS:
            raise ValueError(f"author debe ser uno de {AUTHORS}, recibido '{author}'")
        now = self._now().isoformat(timespec="seconds")
        self.ensure()
        created = now
        if note_id is not None:
            owner = note_id.split("/", 1)[0]
            if owner in AUTHORS and owner != author:
                raise ValueError(f"note_id '{note_id}' pertenece al autor '{owner}', no a '{author}'")
            path = self._path(note_id)
            if path.is_file():
                created = self._read(path).created or now
        else:
            path = self.root / author / f"{slugify(title)}.md"
            n = 2
            while path.exists():                       # no pisa una nota con el mismo título
                path = self.root / author / f"{slugify(title)}-{n}.md"
                n += 1
        meta = {"title": title, "author": author, "tags": list(tags or []), "category": category, "created": created,
                "updated": now, **(extra or {})}
        path.parent.mkdir(parents=True, exist_ok=True)
        head = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
        path.write_text(f"---\n{head}\n---\n{content}", encoding="utf-8")
        self._forget(path)                              # dos escrituras seguidas pueden compartir fecha y tamaño
        return self._read(path)

    def delete(self, note_id: str) -> None:
        path = self._path(note_id)
        if not path.is_file():
            raise FileNotFoundError(f"la nota '{note_id}' no existe")
        path.unlink()
        self._forget(path)

    # --- buscar y relacionar
    def keyword_score(self, query_words: set[str], note: Note) -> int:
        hay = set(tokens(f"{note.title} {note.content} {' '.join(note.tags)}"))
        return len(query_words & hay)

    def search_keyword(self, query: str, *, author: str | None = None, limit: int = 10) -> list[tuple[Note, int]]:
        words = set(tokens(query))
        scored = [(n, self.keyword_score(words, n)) for n in self.list_notes(author=author)]
        scored = [(n, s) for n, s in scored if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def graph(self, notes: list[Note] | None = None) -> dict:
        """Nodos = notas; aristas = wikilinks resueltos por título (como el grafo real de Obsidian). Un link a un título
        que no existe se ignora: no se fabrica un nodo fantasma."""
        notes = self.list_notes() if notes is None else notes
        by_title = {n.title.strip().lower(): n.id for n in notes}
        edges: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for n in notes:
            for lt in n.links:
                tgt = by_title.get(lt.strip().lower())
                if tgt is None or tgt == n.id:
                    continue
                key = (n.id, tgt) if n.id < tgt else (tgt, n.id)
                if key not in seen:
                    seen.add(key)
                    edges.append({"source": n.id, "target": tgt})
        return {"nodes": [n.summary() for n in notes], "edges": edges}

    def link_to_category_index(self, note_title: str, category: str, author: str = "jarvis") -> Note:
        """Nota índice (MOC) por categoría: toda nota nueva queda conectada al hub de su categoría y el hub a ella."""
        index_title = f"Índice: {category}"
        index_id = f"{author}/{slugify(index_title)}"
        line = f"- [[{note_title}]]"
        if not self.exists(index_id):
            return self.save(index_title, f"Notas de la categoría **{category}**.\n\n{line}", author, ["indice"], category)
        index = self.read(index_id)
        if line in index.content:
            return index
        return self.save(index_title, index.content.rstrip("\n") + f"\n{line}\n", author, index.tags, category, note_id=index_id)

    # --- exportar (al desmontar la brigada se ofrece llevarse el vault)
    def export_zip(self, dest: str | Path) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.root.rglob("*")):
                if p.resolve() == dest.resolve():
                    continue
                if p.is_file() and not any(part.startswith(".") for part in p.relative_to(self.root).parts):
                    z.write(p, p.relative_to(self.root).as_posix())
        return dest
