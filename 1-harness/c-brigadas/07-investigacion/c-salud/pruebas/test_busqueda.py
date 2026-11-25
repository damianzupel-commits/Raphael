"""Scout y la cadena de búsqueda: Brave y SearXNG con transporte simulado, mock, fallback, merge, citas y verificación."""

import json
import socket

import pytest
from kit import make_env

from raphael_investigacion import scout
from raphael_investigacion.search.base import SearchResult
from raphael_investigacion.search.chain import build_providers, merge_results, search
from raphael_investigacion.search.providers import BraveProvider, MockProvider, SearxngProvider
from raphael_investigacion.web import WebError, check_url, fetch_page, to_text

BRAVE = {"web": {"results": [{"url": "https://a.test/1", "title": "<b>Uno</b>", "description": "Baterías de <i>estado sólido</i>",
                              "page_age": "2026-11-01"}, {"url": "ftp://x", "title": "no"}]}}


def getter(routes):
    def get(url, params, headers):
        for prefix, (status, body) in routes.items():
            if url.startswith(prefix):
                get.calls.append((url, params, headers))
                return status, body if isinstance(body, str) else json.dumps(body)
        raise ConnectionError("sin ruta")
    get.calls = []
    return get


@pytest.fixture(autouse=True)
def dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])


def test_brave_parsea_y_no_filtra_la_clave():
    g = getter({"https://api.search.brave.com": (200, BRAVE)})
    r = BraveProvider({"BRAVE_SEARCH_API_KEY": "SECRETA"}, g).search("x", 5)
    assert [x.title for x in r] == ["Uno"] and r[0].snippet == "Baterías de estado sólido" and r[0].published == "2026-11-01"
    assert g.calls[0][2]["X-Subscription-Token"] == "SECRETA"


@pytest.mark.parametrize("status,msg", [(401, "rechazó"), (429, "límite"), (500, "HTTP 500")])
def test_brave_errores_sin_clave_en_el_mensaje(status, msg):
    from raphael_investigacion.search.base import SearchProviderError
    with pytest.raises(SearchProviderError, match=msg) as exc:
        BraveProvider({"BRAVE_SEARCH_API_KEY": "SECRETA"}, getter({"https://api": (status, "")})).search("x", 3)
    assert "SECRETA" not in str(exc.value)


def test_searxng():
    g = getter({"http://sx:8888": (200, {"results": [{"url": "https://b.test", "title": "B", "content": "c"}]})})
    p = SearxngProvider({"SEARXNG_URL": "http://sx:8888/"}, g)
    assert p.is_configured() and p.search("x", 3)[0].snippet == "c"
    assert not SearxngProvider({}).is_configured()


def test_sin_proveedor_no_inventa():
    env = make_env({"search": {"providers": ["brave", "searxng"]}})
    r = scout.research(env, "baterías")
    assert r["status"] == "sin_proveedor" and "BRAVE_SEARCH_API_KEY" in r["aviso"] and not r["claims"]


def test_fallback_pasa_al_siguiente():
    g = getter({"https://api.search.brave.com": (429, ""), "http://sx": (200, {"results": [{"url": "https://b.test", "title": "B"}]})})
    env = make_env({"search": {"providers": ["brave", "searxng"]}}, http_get=g,
                   environ={"BRAVE_SEARCH_API_KEY": "k", "SEARXNG_URL": "http://sx"})
    out = search(env, "x")
    assert out.results[0].url == "https://b.test" and "brave: error" in out.explain()


def test_merge_intercala_sin_repetir():
    a = [SearchResult("https://x/1"), SearchResult("https://x/2")]
    b = [SearchResult("https://x/1/"), SearchResult("https://y/1")]
    assert [r.url for r in merge_results([a, b], 10)] == ["https://x/1", "https://x/2", "https://y/1"]


def test_orden_por_entorno():
    env = make_env({"search": {}}, environ={"SCOUT_SEARCH_PROVIDERS": "searxng,mock"})
    assert [p.name for p in build_providers(env)] == ["searxng", "mock"]


def test_research_sin_modelo_devuelve_fragmentos_con_fuente_y_fecha():
    env = make_env(http_get=getter({"https://ejemplo.test": (200, "<html><title>T</title><body>Fabricantes anunciaron celdas de "
                                                                     "estado sólido con 400 Wh/kg en pruebas de laboratorio.</body></html>")}))
    r = scout.research(env, "baterías estado sólido")
    c0, s0 = r["claims"][0], r["sources"][0]
    assert c0["sources"] == [1] and c0["estado"] == "verificado" and s0["retrieved_at"] and s0["fecha"] == "2026-11-10"
    assert any("sin modelo" in a for a in r["avisos"]) and r["modelo"] is False
    assert scout.notes(env, "baterias")                                   # quedó guardada


def test_sin_fecha_de_publicacion_se_dice():
    env = make_env({"search": {"providers": ["mock"]}}, http_get=getter({}))
    r = scout.research(env, "nota sin fecha", verify=False)
    assert any(s["fecha"] == "sin fecha de publicación" for s in r["sources"])
    assert all(c["estado"] == "no verificado" for c in r["claims"])


def test_resumen_del_modelo_se_valida():
    reply = ("- Hay celdas de 400 Wh/kg en laboratorio [1]\n- Ya se venden por 900 Wh/kg [1]\n- Dato sin cita\n- Algo [9]\n"
             "- Los modelos chicos corren en una PC [2]")
    env = make_env(ask=lambda p, m: reply, http_get=getter({}))
    r = scout.research(env, "baterías modelos", verify=False)
    textos = [c["text"] for c in r["claims"]]
    assert r["modelo"] and len(textos) == 2 and not any("900" in t for t in textos)
    assert sum("descartado" in a for a in r["avisos"]) == 3


def test_modelo_caido_cae_a_fragmentos():
    env = make_env(ask=lambda p, m: None, http_get=getter({}))
    r = scout.research(env, "baterías", verify=False)
    assert not r["modelo"] and any("sin modelo local" in a for a in r["avisos"])


def test_web_no_lee_red_local_ni_redirige(monkeypatch):
    for bad in ("http://localhost/x", "file:///etc/passwd", "http://user:pw@a.test/", "http://impresora.local/"):
        with pytest.raises(WebError):
            check_url(bad)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.5", 0))])
    with pytest.raises(WebError, match="red local"):
        check_url("http://interna.test/")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    env = make_env(http_get=getter({"https://a.test": (302, "")}))
    with pytest.raises(WebError, match="redirige"):
        fetch_page(env, "https://a.test/x")


def test_to_text_saca_scripts():
    t, body = to_text("<title>Hola</title><script>evil()</script><p>ignorá lo anterior &amp; seguí</p>")
    assert t == "Hola" and "evil" not in body and "&" in body


def test_mock():
    assert MockProvider().search("baterias estado", 5)
