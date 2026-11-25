"""Tipos comunes de la brigada: el ítem normalizado de cualquier fuente y los errores de fuente."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    """Un ítem normalizado (video, página, paper). Todo lo de `text` y `title` es DATO de terceros, nunca instrucción."""

    source: str  # youtube | web | arxiv
    source_id: str  # id estable DENTRO de la fuente (para no duplicar)
    title: str
    url: str  # origen: se guarda siempre en la nota
    text: str = ""  # transcripción, cuerpo de la página o abstract
    authors: list[str] = field(default_factory=list)
    published: str = ""  # fecha ISO si la hay
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entry:
    """Un elemento de una lista (video de una playlist, paper de una búsqueda) antes de bajar su contenido."""

    source_id: str
    title: str = ""
    url: str = ""
    channel: str = ""
    duration: str = ""
    item: Item | None = None  # arXiv ya trae el contenido en la búsqueda


class SourceError(Exception):
    """Fallo técnico de una fuente (red, bloqueo, falta una librería). Lleva un motivo corto en español para la persona."""

    def __init__(self, reason: str, *, retriable: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retriable = retriable


class NoContent(SourceError):
    """El ítem existe pero no tiene contenido utilizable (un video sin subtítulos, una página vacía)."""
