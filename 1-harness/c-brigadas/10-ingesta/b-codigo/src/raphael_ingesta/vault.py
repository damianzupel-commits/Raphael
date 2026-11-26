"""El vault: notas en Markdown (compatibles con Obsidian). Toda nota guarda su origen (URL y fecha). Si no hay carpeta
configurada (`RAPHAEL_VAULT_DIR`), la nota queda igual en el almacén de la brigada y se publica el evento `nota.ingerida`
para que la pieza Memoria la tome por el harness; nunca se importa a Memoria."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from .model import Item
from .summary import Summary
from .text import one_line

LABELS = {"youtube": "YouTube", "web": "Web", "arxiv": "arXiv", "fuentes": "Fuentes públicas"}


def slug(text: str, n: int = 70) -> str:
    d = unicodedata.normalize("NFKD", text or "")
    s = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in d if not unicodedata.combining(c)).lower()).strip("-")
    return s[:n].strip("-") or "nota"


def note_id(item: Item) -> str:
    return f"{item.source}:{item.source_id}"


def build_note(item: Item, s: Summary, when: datetime) -> str:
    """El Markdown de la nota: frontmatter + ## Fuente / ## Resumen / ## Temas clave / ## Relevancia / ## Notas relacionadas."""
    authors = ", ".join(one_line(a, 80) for a in item.authors[:8]) or "desconocidos"
    tags = (
        ["ingesta", item.source, s.category]
        + ([item.extra["ficha"]] if item.extra.get("ficha") else [])
        + (["baja-relevancia"] if s.low else [])
    )
    label = LABELS.get(item.source, item.source)
    fm = [
        "---",
        f'title: "{s.title.replace(chr(34), chr(39))}"',
        f"fuente: {item.source}",
        f"origen: {item.url}",
        f"id_fuente: {item.source_id}",
        f"fecha_ingesta: {when.isoformat(timespec='seconds')}",
        f"generado_con: {s.by}",
        f"tags: [{', '.join(tags)}]",
        "---",
        "",
    ]
    body = [
        f"Resumen automático de una fuente de {label}.",
        "",
        "## Fuente",
        f"- Origen: {item.url}",
        f"- Fecha de ingesta: {when.date().isoformat()}",
        f"- Autores o canal: {authors}",
        f"- Publicado: {item.published or 's/f'}",
        *([f"- Crédito: {item.extra['credito']}"] if item.extra.get("credito") else []),
        f"- Generado con: {'modelo' if s.by == 'modelo' else 'reglas (sin modelo: resumen extractivo, sin evaluar)'}",
        "",
        "## Resumen",
        s.summary,
        "",
        "## Temas clave",
        *([f"- {t}" for t in s.key_topics] or ["- (no se extrajeron temas clave)"]),
    ]
    if s.verdict:
        body += ["", "## Relevancia"]
        if s.low:
            body.append("⚠️ Marcada como baja relevancia: se guarda igual, nada se descarta.")
        body += [f"- Veredicto: {s.verdict}", f"- Puntaje: {s.score}/5", f"- Razón: {s.reason}"]
    body += ["", "## Notas relacionadas", f"- [[Índice: {s.category}]]", f"- [[Ingesta: {label}]]"]
    return "\n".join(fm + body) + "\n"


class FileVault:
    """Escribe `<raíz>/Ingesta/<fuente>/<slug>-<id>.md`. Nunca sale de la raíz."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser()

    def path_for(self, item: Item, title: str) -> Path:
        name = f"{slug(title)}-{slug(item.source_id, 24)}.md"
        target = (self.root / "Ingesta" / item.source / name).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ValueError("la nota quedaría fuera del vault")
        return target

    def save(self, item: Item, title: str, content: str) -> str:
        target = self.path_for(item, title)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def delete(self, path: str) -> bool:
        p = Path(path).resolve()
        if not p.is_relative_to(self.root.resolve()) or not p.is_file():
            return False
        p.unlink()
        return True
