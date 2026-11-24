"""Proveedor SearXNG (meta-buscador propio): listo para enchufar cuando exista una instancia.

Config (en `backend/.env`):
  SEARXNG_URL   URL base de la instancia, ej. http://localhost:8888. Sin ella queda "no configurado".

La instancia tiene que habilitar el formato JSON (`search.formats: [html, json]` en su settings.yml);
si no, responde 403 y el error lo explica. NOTA: implementado según la API documentada de SearXNG pero
todavía sin una instancia real contra la cual probarlo (hoy solo hay tests con transporte simulado).
"""

from __future__ import annotations

import os

import httpx

from .base import SearchProvider, SearchProviderError, SearchResult


class SearxngProvider(SearchProvider):
    name = "searxng"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    @property
    def _base(self) -> str:
        return os.environ.get("SEARXNG_URL", "").strip().rstrip("/")

    def is_configured(self) -> bool:
        return self._base.startswith(("http://", "https://"))

    def missing_config_hint(self) -> str:
        return "definí SEARXNG_URL en backend/.env apuntando a tu instancia (ej. http://localhost:8888)"

    async def search(self, query: str, count: int) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0, transport=self._transport, follow_redirects=True) as client:
                resp = await client.get(f"{self._base}/search", params={"q": query, "format": "json"})
        except httpx.HTTPError as exc:
            raise SearchProviderError(f"sin conexión con la instancia SearXNG ({type(exc).__name__})") from None
        if resp.status_code == 403:
            raise SearchProviderError("SearXNG rechazó format=json (HTTP 403): habilitá 'json' en search.formats de su settings.yml")
        if resp.status_code != 200:
            raise SearchProviderError(f"SearXNG respondió HTTP {resp.status_code}")
        try:
            items = resp.json().get("results") or []
        except ValueError:
            raise SearchProviderError("SearXNG devolvió una respuesta que no es JSON (¿formato json deshabilitado?)") from None
        out = [SearchResult(url=it["url"], title=(it.get("title") or "").strip(), snippet=(it.get("content") or "").strip(),
                            provider=self.name)
               for it in items if str(it.get("url", "")).startswith(("http://", "https://"))]
        return out[: max(1, count)]
