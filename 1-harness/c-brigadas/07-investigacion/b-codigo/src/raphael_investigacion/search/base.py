"""Interfaz común de los proveedores de búsqueda web de Scout. Un proveedor busca y devuelve resultados (url, título,
fragmento); nada más. Las claves viven solo en el entorno: ningún error, log ni resultado las incluye."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    provider: str = ""
    published: str = ""    # fecha de publicación que declara el proveedor, si la trae (no se inventa)

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "title": self.title, "snippet": self.snippet, "provider": self.provider,
                "published": self.published}


class SearchProviderError(Exception):
    """Falla de un proveedor (clave rechazada, límite, red). El mensaje se puede mostrar: nunca lleva headers ni la clave."""


class SearchProvider(abc.ABC):
    name: str = ""

    @abc.abstractmethod
    def is_configured(self) -> bool: ...

    @abc.abstractmethod
    def missing_config_hint(self) -> str: ...

    @abc.abstractmethod
    def search(self, query: str, count: int) -> list[SearchResult]: ...


@dataclass(frozen=True)
class Attempt:
    provider: str
    status: str


@dataclass
class SearchOutcome:
    results: list[SearchResult] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    mode: str = "fallback"

    @property
    def any_configured(self) -> bool:
        return any(not a.status.startswith("no configurado") for a in self.attempts)

    def explain(self) -> str:
        return "; ".join(f"{a.provider}: {a.status}" for a in self.attempts) or "ningún proveedor"
