"""Proveedor Brave Search API (primario de Scout).

Config (en `backend/.env`):
  BRAVE_SEARCH_API_KEY    la key (se consigue gratis en https://brave.com/search/api/). Sin ella el
                          proveedor queda "no configurado".
  BRAVE_SEARCH_ENDPOINT   opcional; default https://api.search.brave.com/res/v1/web/search
"""

from __future__ import annotations

import os
import re

import httpx

from .base import SearchProvider, SearchProviderError, SearchResult

_DEFAULT_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_MAX_COUNT = 20  # tope de la API
_TAGS = re.compile(r"<[^>]+>")


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport  # inyectable para tests (httpx.MockTransport)

    @property
    def _key(self) -> str:
        return os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self._key)

    def missing_config_hint(self) -> str:
        return "definí BRAVE_SEARCH_API_KEY en backend/.env (key gratis en https://brave.com/search/api/)"

    async def search(self, query: str, count: int) -> list[SearchResult]:
        endpoint = os.environ.get("BRAVE_SEARCH_ENDPOINT", "").strip() or _DEFAULT_ENDPOINT
        try:
            async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as client:
                resp = await client.get(
                    endpoint,
                    params={"q": query, "count": max(1, min(count, _MAX_COUNT))},
                    headers={"Accept": "application/json", "X-Subscription-Token": self._key},
                )
        except httpx.HTTPError as exc:
            raise SearchProviderError(f"sin conexión con Brave ({type(exc).__name__})") from None
        if resp.status_code in (401, 403, 422):
            raise SearchProviderError(f"Brave rechazó la API key (HTTP {resp.status_code}): revisá BRAVE_SEARCH_API_KEY")
        if resp.status_code == 429:
            raise SearchProviderError("Brave: límite de uso alcanzado (HTTP 429)")
        if resp.status_code != 200:
            raise SearchProviderError(f"Brave respondió HTTP {resp.status_code}")
        try:
            items = (resp.json().get("web") or {}).get("results") or []
        except ValueError:
            raise SearchProviderError("Brave devolvió una respuesta que no es JSON") from None
        out: list[SearchResult] = []
        for it in items:
            url = (it.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                out.append(SearchResult(url=url, title=_TAGS.sub("", it.get("title") or "").strip(),
                                        snippet=_TAGS.sub("", it.get("description") or "").strip(), provider=self.name))
        return out
