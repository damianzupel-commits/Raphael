"""Proveedores de búsqueda web enchufables para Scout (Brave primario, SearXNG combinable).

    from app import search_providers
    outcome = await search_providers.search("tema", count=8)   # outcome.results / outcome.attempts

Ver chain.py para la configuración por .env (orden, fallback, merge) y base.py para la interfaz.
"""

from .base import Attempt, SearchOutcome, SearchProvider, SearchProviderError, SearchResult
from .chain import REGISTRY, build_providers, merge_results, provider_order, search, search_mode

__all__ = ["Attempt", "SearchOutcome", "SearchProvider", "SearchProviderError", "SearchResult", "REGISTRY",
           "build_providers", "merge_results", "provider_order", "search", "search_mode"]
