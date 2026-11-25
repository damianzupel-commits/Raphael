"""Los proveedores: Brave (real), SearXNG (real, para una instancia propia) y un simulado para pruebas y demos.

Brave:   BRAVE_SEARCH_API_KEY (clave gratis en https://brave.com/search/api/). BRAVE_SEARCH_ENDPOINT es opcional.
SearXNG: SEARXNG_URL, la instancia con `json` habilitado en `search.formats`.
Mock:    sin red ni clave; devuelve siempre los mismos resultados para poder probar Scout y las tendencias.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from .base import SearchProvider, SearchProviderError, SearchResult
from .http import default_get

_TAGS = re.compile(r"<[^>]+>")
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _clean(text: str) -> str:
    return _TAGS.sub("", text or "").strip()


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, environ: Mapping[str, str], http_get=None) -> None:
        self._env, self._get = environ, http_get or default_get

    def is_configured(self) -> bool:
        return bool(self._env.get("BRAVE_SEARCH_API_KEY", "").strip())

    def missing_config_hint(self) -> str:
        return "falta BRAVE_SEARCH_API_KEY (clave gratis en https://brave.com/search/api/)"

    def search(self, query: str, count: int) -> list[SearchResult]:
        endpoint = self._env.get("BRAVE_SEARCH_ENDPOINT", "").strip() or BRAVE_ENDPOINT
        try:
            status, body = self._get(endpoint, {"q": query, "count": str(max(1, min(count, 20)))},
                                     {"Accept": "application/json", "X-Subscription-Token": self._env["BRAVE_SEARCH_API_KEY"].strip()})
        except ConnectionError as exc:
            raise SearchProviderError(f"sin conexión con Brave ({exc})") from None
        if status in (401, 403, 422):
            raise SearchProviderError(f"Brave rechazó la clave (HTTP {status}): revisá BRAVE_SEARCH_API_KEY")
        if status == 429:
            raise SearchProviderError("Brave: límite de uso alcanzado (HTTP 429)")
        if status != 200:
            raise SearchProviderError(f"Brave respondió HTTP {status}")
        try:
            items = (json.loads(body).get("web") or {}).get("results") or []
        except ValueError:
            raise SearchProviderError("Brave devolvió algo que no es JSON") from None
        return [SearchResult(url=i["url"].strip(), title=_clean(i.get("title", "")), snippet=_clean(i.get("description", "")),
                             provider=self.name, published=str(i.get("page_age") or i.get("age") or ""))
                for i in items if str(i.get("url", "")).startswith(("http://", "https://"))][:count]


class SearxngProvider(SearchProvider):
    name = "searxng"

    def __init__(self, environ: Mapping[str, str], http_get=None) -> None:
        self._env, self._get = environ, http_get or default_get

    @property
    def _base(self) -> str:
        return self._env.get("SEARXNG_URL", "").strip().rstrip("/")

    def is_configured(self) -> bool:
        return self._base.startswith(("http://", "https://"))

    def missing_config_hint(self) -> str:
        return "falta SEARXNG_URL (la dirección de tu instancia, ej. http://localhost:8888)"

    def search(self, query: str, count: int) -> list[SearchResult]:
        try:
            status, body = self._get(f"{self._base}/search", {"q": query, "format": "json"}, {"Accept": "application/json"})
        except ConnectionError as exc:
            raise SearchProviderError(f"sin conexión con la instancia SearXNG ({exc})") from None
        if status == 403:
            raise SearchProviderError("SearXNG rechazó format=json (HTTP 403): habilitá 'json' en search.formats de su settings.yml")
        if status != 200:
            raise SearchProviderError(f"SearXNG respondió HTTP {status}")
        try:
            items = json.loads(body).get("results") or []
        except ValueError:
            raise SearchProviderError("SearXNG devolvió algo que no es JSON (¿formato json deshabilitado?)") from None
        return [SearchResult(url=i["url"], title=(i.get("title") or "").strip(), snippet=(i.get("content") or "").strip(),
                             provider=self.name, published=str(i.get("publishedDate") or ""))
                for i in items if str(i.get("url", "")).startswith(("http://", "https://"))][:count]


MOCK_RESULTS = (
    SearchResult("https://ejemplo.test/baterias-estado-solido", "Baterías de estado sólido: avances 2026",
                 "Fabricantes anunciaron celdas de estado sólido con 400 Wh/kg en pruebas de laboratorio.", "mock", "2026-11-10"),
    SearchResult("https://ejemplo.test/tendencias-ia-local", "IA local: modelos que corren en la PC",
                 "Los modelos pequeños corren en una PC común y evitan mandar datos a la nube.", "mock", "2026-11-12"),
    SearchResult("https://otro.test/nota-sin-fecha", "Nota sin fecha", "Una nota que no declara cuándo se publicó.", "mock", ""),
)


class MockProvider(SearchProvider):
    """Simulado: siempre configurado, sin red. Filtra por palabras de la consulta para parecerse a uno real."""

    name = "mock"

    def __init__(self, results: tuple[SearchResult, ...] = MOCK_RESULTS) -> None:
        self._results = results

    def is_configured(self) -> bool:
        return True

    def missing_config_hint(self) -> str:
        return ""

    def search(self, query: str, count: int) -> list[SearchResult]:
        words = [w for w in re.findall(r"\w{4,}", query.lower())]
        hits = [r for r in self._results if not words or any(w in (r.title + " " + r.snippet).lower() for w in words)]
        return list(hits or self._results)[:count]
