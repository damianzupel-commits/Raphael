"""Cadena de proveedores de búsqueda: orden, fallback y merge, todo configurable por `.env`.

  SCOUT_SEARCH_PROVIDERS   orden de la cadena, separado por comas. Default "brave,searxng".
                           Un proveedor sin configurar (sin key / sin URL) se saltea y queda anotado.
  SCOUT_SEARCH_MODE        "fallback" (default): se usa el primer proveedor que devuelve resultados; si
                           falla o viene vacío, se prueba el siguiente.
                           "merge": se consultan TODOS los configurados y se combinan (intercalando por
                           ranking y sin URLs repetidas).

Ejemplos:  Brave solo ................ SCOUT_SEARCH_PROVIDERS=brave
           Brave y, si falla, SearXNG  SCOUT_SEARCH_PROVIDERS=brave,searxng  (+ SEARXNG_URL=...)
           Brave + SearXNG combinados  SCOUT_SEARCH_PROVIDERS=brave,searxng  SCOUT_SEARCH_MODE=merge
"""

from __future__ import annotations

import asyncio
import logging
import os

from .. import config  # noqa: F401  (carga el .env con las keys)
from .base import Attempt, SearchOutcome, SearchProvider, SearchProviderError, SearchResult
from .brave import BraveProvider
from .searxng import SearxngProvider

logger = logging.getLogger("search_providers")

# Para sumar un proveedor: una clase SearchProvider y una línea acá.
REGISTRY: dict[str, type[SearchProvider]] = {"brave": BraveProvider, "searxng": SearxngProvider}
DEFAULT_ORDER = "brave,searxng"


def provider_order() -> list[str]:
    raw = os.environ.get("SCOUT_SEARCH_PROVIDERS", "").strip() or DEFAULT_ORDER
    return [n.strip().lower() for n in raw.split(",") if n.strip()]


def search_mode() -> str:
    return "merge" if os.environ.get("SCOUT_SEARCH_MODE", "").strip().lower() == "merge" else "fallback"


def build_providers(names: list[str] | None = None) -> list[SearchProvider]:
    out: list[SearchProvider] = []
    for n in names or provider_order():
        cls = REGISTRY.get(n)
        if cls is None:
            logger.warning("proveedor de búsqueda desconocido en SCOUT_SEARCH_PROVIDERS: %r", n)
            continue
        out.append(cls())
    return out


def _norm_url(url: str) -> str:
    return url.split("#")[0].rstrip("/").lower()


def merge_results(per_provider: list[list[SearchResult]], count: int) -> list[SearchResult]:
    """Intercala por ranking (1º de cada uno, 2º de cada uno...) sin repetir URLs."""
    seen: set[str] = set()
    out: list[SearchResult] = []
    for rank in range(max((len(r) for r in per_provider), default=0)):
        for results in per_provider:
            if rank < len(results) and _norm_url(results[rank].url) not in seen:
                seen.add(_norm_url(results[rank].url))
                out.append(results[rank])
    return out[:count]


async def search(query: str, count: int = 8, providers: list[SearchProvider] | None = None,
                 mode: str | None = None) -> SearchOutcome:
    """Busca con la cadena configurada. `providers`/`mode` permiten inyectar otra (tests)."""
    providers = providers if providers is not None else build_providers()
    mode = mode or search_mode()
    outcome = SearchOutcome(mode=mode)

    active: list[SearchProvider] = []
    for p in providers:
        if p.is_configured():
            active.append(p)
        else:
            outcome.attempts.append(Attempt(p.name, f"no configurado: {p.missing_config_hint()}"))

    async def run_one(p: SearchProvider) -> list[SearchResult]:
        try:
            res = await p.search(query, count)
        except SearchProviderError as exc:
            outcome.attempts.append(Attempt(p.name, f"error: {exc}"))
            return []
        except Exception as exc:  # noqa: BLE001 — un proveedor roto no tumba la cadena
            logger.warning("proveedor %s falló con %s", p.name, type(exc).__name__)
            outcome.attempts.append(Attempt(p.name, f"error inesperado ({type(exc).__name__})"))
            return []
        outcome.attempts.append(Attempt(p.name, f"ok ({len(res)} resultados)" if res else "sin resultados"))
        return res

    if mode == "merge":
        per = await asyncio.gather(*(run_one(p) for p in active))
        outcome.results = merge_results(list(per), count)
    else:
        for p in active:
            res = await run_one(p)
            if res:
                outcome.results = res[:count]
                break
    return outcome
