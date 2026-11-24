"""Interfaz común de los proveedores de búsqueda web de Scout.

Un proveedor recibe una consulta y devuelve resultados (url + título + snippet); nada más. Qué
proveedores hay, en qué orden y si se combinan lo decide `chain.py` desde el `.env`. Para sumar uno
nuevo alcanza con una clase `SearchProvider` y registrarla en `chain.REGISTRY`.

Regla de seguridad: los secretos (API keys) viven SOLO en el entorno/`.env`; ningún mensaje de error,
log ni resultado los incluye.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    provider: str = ""


class SearchProviderError(Exception):
    """Falla de un proveedor (key rechazada, límite de uso, red). El mensaje es apto para mostrar:
    nunca contiene headers ni la key."""


class SearchProvider(abc.ABC):
    name: str = ""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """¿Tiene todo lo necesario (key / URL de instancia) para buscar?"""

    @abc.abstractmethod
    def missing_config_hint(self) -> str:
        """Qué variable del .env falta, para el mensaje al usuario."""

    @abc.abstractmethod
    async def search(self, query: str, count: int) -> list[SearchResult]:
        """Busca `query` y devuelve hasta `count` resultados. Lanza SearchProviderError si falla."""


@dataclass(frozen=True)
class Attempt:
    provider: str
    status: str  # "ok (3 resultados)" | "sin resultados" | "no configurado: ..." | "error: ..."


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
