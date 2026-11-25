"""Cadena de proveedores: orden, fallback y mezcla. Configurable por `config.search` o por el entorno:

  SCOUT_SEARCH_PROVIDERS   orden separado por comas (default "brave,searxng"; "mock" para pruebas)
  SCOUT_SEARCH_MODE        "fallback" (default: el primero que devuelve resultados) o "merge" (se combinan sin repetir URLs)

Un proveedor sin configurar se saltea y queda anotado: sin ninguno configurado, Scout lo dice y no inventa resultados.
"""

from __future__ import annotations

from ..env import Env
from .base import Attempt, SearchOutcome, SearchProvider, SearchProviderError, SearchResult
from .providers import BraveProvider, MockProvider, SearxngProvider

DEFAULT_ORDER = "brave,searxng"


def build_providers(env: Env) -> list[SearchProvider]:
    names = list(env.config.search.providers) or [
        n.strip().lower() for n in (env.environ.get("SCOUT_SEARCH_PROVIDERS", "") or DEFAULT_ORDER).split(",") if n.strip()]
    registry = {"brave": lambda: BraveProvider(env.environ, env.http_get), "searxng": lambda: SearxngProvider(env.environ, env.http_get),
                "mock": MockProvider}
    return [registry[n]() for n in names if n in registry]


def _norm(url: str) -> str:
    return url.split("#")[0].rstrip("/").lower()


def merge_results(per_provider: list[list[SearchResult]], count: int) -> list[SearchResult]:
    seen: set[str] = set()
    out: list[SearchResult] = []
    for rank in range(max((len(r) for r in per_provider), default=0)):
        for results in per_provider:
            if rank < len(results) and _norm(results[rank].url) not in seen:
                seen.add(_norm(results[rank].url))
                out.append(results[rank])
    return out[:count]


def search(env: Env, query: str, count: int | None = None, providers: list[SearchProvider] | None = None) -> SearchOutcome:
    count = count or env.config.search.count
    providers = providers if providers is not None else build_providers(env)
    mode = env.config.search.mode or env.environ.get("SCOUT_SEARCH_MODE", "").strip().lower()
    mode = "merge" if mode == "merge" else "fallback"
    outcome = SearchOutcome(mode=mode)
    active = []
    for p in providers:
        if p.is_configured():
            active.append(p)
        else:
            outcome.attempts.append(Attempt(p.name, f"no configurado: {p.missing_config_hint()}"))

    def run(p: SearchProvider) -> list[SearchResult]:
        try:
            res = p.search(query, count)
        except SearchProviderError as exc:
            outcome.attempts.append(Attempt(p.name, f"error: {exc}"))
            return []
        except Exception as exc:  # noqa: BLE001 - un proveedor roto no tumba la cadena
            outcome.attempts.append(Attempt(p.name, f"error inesperado ({type(exc).__name__})"))
            return []
        outcome.attempts.append(Attempt(p.name, f"ok ({len(res)} resultados)" if res else "sin resultados"))
        return res

    if mode == "merge":
        outcome.results = merge_results([run(p) for p in active], count)
    else:
        for p in active:
            res = run(p)
            if res:
                outcome.results = res[:count]
                break
    return outcome
