"""Tests de los proveedores de búsqueda de Scout (app/search_providers/): Brave, SearXNG y la cadena
(fallback / merge). Sin red: los proveedores usan httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from app import search_providers as sp
from app.search_providers.brave import BraveProvider
from app.search_providers.searxng import SearxngProvider

pytestmark = pytest.mark.anyio

KEY = "BSA-clave-super-secreta-123"


def _brave(handler):
    return BraveProvider(transport=httpx.MockTransport(handler))


def _searx(handler):
    return SearxngProvider(transport=httpx.MockTransport(handler))


BRAVE_OK = {"web": {"results": [
    {"url": "https://a.org/x", "title": "Titulo <strong>A</strong>", "description": "desc <b>uno</b>"},
    {"url": "ftp://raro.org/y", "title": "descartado"},
    {"url": "https://b.org/y", "title": "B", "description": "dos"},
]}}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("BRAVE_SEARCH_API_KEY", "BRAVE_SEARCH_ENDPOINT", "SEARXNG_URL", "SCOUT_SEARCH_PROVIDERS", "SCOUT_SEARCH_MODE"):
        monkeypatch.delenv(var, raising=False)


# --- Brave ---------------------------------------------------------------------
async def test_brave_sin_key_no_esta_configurado_y_dice_donde_ponerla():
    p = BraveProvider()
    assert not p.is_configured() and "BRAVE_SEARCH_API_KEY" in p.missing_config_hint()


async def test_brave_parsea_resultados_manda_la_key_por_header_y_descarta_lo_no_http(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", KEY)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("x-subscription-token")
        seen["q"] = request.url.params["q"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json=BRAVE_OK)

    res = await _brave(handler).search("activitypub", 5)
    assert [r.url for r in res] == ["https://a.org/x", "https://b.org/y"]
    assert res[0].title == "Titulo A" and res[0].snippet == "desc uno" and res[0].provider == "brave"
    assert seen["token"] == KEY and seen["q"] == "activitypub"
    assert KEY not in seen["url"]  # la key va en el header, nunca en la URL


@pytest.mark.parametrize("status,needle", [(401, "rechazó la API key"), (403, "rechazó la API key"), (429, "límite de uso"), (500, "HTTP 500")])
async def test_brave_errores_son_legibles_y_nunca_filtran_la_key(monkeypatch, status, needle):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", KEY)
    with pytest.raises(sp.SearchProviderError) as exc:
        await _brave(lambda r: httpx.Response(status, text=f"token {KEY} inválido")).search("x", 3)
    assert needle in str(exc.value) and KEY not in str(exc.value)


async def test_brave_error_de_red_no_expone_detalles(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", KEY)

    def boom(request):
        raise httpx.ConnectError(f"fallo con {KEY}")

    with pytest.raises(sp.SearchProviderError) as exc:
        await _brave(boom).search("x", 3)
    assert KEY not in str(exc.value) and "sin conexión" in str(exc.value)


# --- SearXNG -------------------------------------------------------------------
async def test_searxng_pide_json_y_parsea(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888/")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["fmt"] = request.url.path, request.url.params["format"]
        return httpx.Response(200, json={"results": [{"url": "https://c.org", "title": "C", "content": "texto"}]})

    p = _searx(handler)
    assert p.is_configured()
    res = await p.search("q", 5)
    assert seen == {"path": "/search", "fmt": "json"} and res[0].url == "https://c.org" and res[0].provider == "searxng"


async def test_searxng_sin_url_no_esta_configurado_y_403_explica_el_formato(monkeypatch):
    assert not SearxngProvider().is_configured()
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    with pytest.raises(sp.SearchProviderError, match="search.formats"):
        await _searx(lambda r: httpx.Response(403)).search("q", 3)


# --- cadena --------------------------------------------------------------------
class _Fake(sp.SearchProvider):
    def __init__(self, name, urls=(), error=None, configured=True):
        self.name, self._urls, self._error, self._cfg = name, urls, error, configured

    def is_configured(self):
        return self._cfg

    def missing_config_hint(self):
        return f"falta config de {self.name}"

    async def search(self, query, count):
        if self._error:
            raise sp.SearchProviderError(self._error)
        return [sp.SearchResult(url=u, title=u, provider=self.name) for u in self._urls]


async def test_fallback_usa_el_primero_que_devuelve_resultados():
    out = await sp.search("q", 5, providers=[_Fake("brave", ["https://1.org"]), _Fake("searxng", ["https://2.org"])], mode="fallback")
    assert [r.url for r in out.results] == ["https://1.org"]
    assert [a.provider for a in out.attempts] == ["brave"]  # ni siquiera consultó al segundo


async def test_fallback_pasa_al_siguiente_si_el_primario_falla_o_viene_vacio():
    out = await sp.search("q", 5, providers=[_Fake("brave", error="límite de uso (429)"), _Fake("searxng", ["https://2.org"])], mode="fallback")
    assert [r.url for r in out.results] == ["https://2.org"]
    assert out.attempts[0].status.startswith("error: límite") and out.attempts[1].status.startswith("ok")
    out = await sp.search("q", 5, providers=[_Fake("brave", []), _Fake("searxng", ["https://2.org"])], mode="fallback")
    assert out.attempts[0].status == "sin resultados" and out.results


async def test_merge_intercala_por_ranking_y_deduplica():
    out = await sp.search("q", 10, mode="merge", providers=[
        _Fake("brave", ["https://a.org", "https://b.org", "https://c.org"]),
        _Fake("searxng", ["https://A.org/", "https://d.org", "https://e.org"])])
    assert [r.url for r in out.results] == ["https://a.org", "https://b.org", "https://d.org", "https://c.org", "https://e.org"]  # A.org/ repetida se descarta
    assert {a.provider for a in out.attempts} == {"brave", "searxng"}


async def test_merge_aguanta_que_uno_falle():
    out = await sp.search("q", 5, mode="merge", providers=[_Fake("brave", error="HTTP 500"), _Fake("searxng", ["https://2.org"])])
    assert [r.url for r in out.results] == ["https://2.org"]


async def test_sin_ningun_proveedor_configurado_lo_informa():
    out = await sp.search("q", 5, providers=[_Fake("brave", configured=False), _Fake("searxng", configured=False)])
    assert out.results == [] and not out.any_configured
    assert "falta config de brave" in out.explain()


async def test_la_cadena_se_arma_desde_el_env(monkeypatch):
    assert [p.name for p in sp.build_providers()] == ["brave", "searxng"]  # default
    monkeypatch.setenv("SCOUT_SEARCH_PROVIDERS", "searxng, brave ,inexistente")
    assert [p.name for p in sp.build_providers()] == ["searxng", "brave"]
    assert sp.search_mode() == "fallback"
    monkeypatch.setenv("SCOUT_SEARCH_MODE", "merge")
    assert sp.search_mode() == "merge"


async def test_cadena_real_con_env_solo_brave(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", KEY)
    monkeypatch.setattr(BraveProvider, "__init__", lambda self, transport=None: setattr(self, "_transport", httpx.MockTransport(lambda r: httpx.Response(200, json=BRAVE_OK))))
    out = await sp.search("activitypub", 5)
    status = {a.provider: a.status for a in out.attempts}
    assert len(out.results) == 2 and status["brave"].startswith("ok") and status["searxng"].startswith("no configurado")
