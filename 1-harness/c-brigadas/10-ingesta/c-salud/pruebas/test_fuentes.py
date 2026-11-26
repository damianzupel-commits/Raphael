"""Fuentes públicas (OpenAlex, Crossref, GDELT, Fed, FRED, Banco Mundial, ReliefWeb, UCDP, MIT, Harvard): parsers con ejemplos
escritos a mano, cortesía con la fuente (pausa, claves, email), y el cocinero con el adaptador simulado. Sin red."""

from __future__ import annotations

import json

from kit import System

from raphael_ingesta.adapters.fuentes import (
    RealFuentes,
    parse_crossref,
    parse_fred,
    parse_gdelt,
    parse_openalex,
    parse_reliefweb,
    parse_rss,
    parse_ucdp,
    parse_worldbank,
)
from raphael_ingesta.fichas import FICHAS
from raphael_ingesta.model import SourceError

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Fed holds rates</title><link>https://www.federalreserve.gov/a.htm</link><guid>a</guid>
<description>&lt;p&gt;The Committee &lt;b&gt;decided&lt;/b&gt; to hold.&lt;/p&gt;</description>
<pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Segundo</title><link>https://www.federalreserve.gov/b.htm</link></item></channel></rss>"""


def test_rss_saca_el_html_la_fecha_y_respeta_el_tope():
    es = parse_rss(FICHAS["fed"], RSS, 1)
    assert len(es) == 1 and es[0].item.text == "The Committee decided to hold." and es[0].item.published == "2026-11-25"
    assert es[0].item.extra["credito"].startswith("Fuente: Board of Governors") and es[0].source_id == "fed/a"
    assert parse_rss(FICHAS["fed"], "no es xml", 5) == []


def test_openalex_rearma_el_abstract_y_los_autores():
    data = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "display_name": "War and trade",
                "publication_date": "2026-11-01",
                "doi": "https://doi.org/10.1/x",
                "abstract_inverted_index": {"Trade": [0], "falls": [1], "in": [2], "war": [3]},
                "authorships": [{"author": {"display_name": "Ana"}}],
            }
        ]
    }
    e = parse_openalex(FICHAS["openalex"], data)[0]
    assert (
        e.source_id == "openalex/W1"
        and e.item.text == "Trade falls in war"
        and e.item.authors == ["Ana"]
        and e.url == "https://doi.org/10.1/x"
    )


def test_crossref_gdelt_worldbank_fred_reliefweb_ucdp():
    c = parse_crossref(
        FICHAS["crossref"],
        {
            "message": {
                "items": [
                    {
                        "DOI": "10.1/y",
                        "title": ["T"],
                        "URL": "https://doi.org/10.1/y",
                        "issued": {"date-parts": [[2026, 3, 9]]},
                        "author": [{"given": "A", "family": "B"}],
                    }
                ]
            }
        },
    )[0]
    assert c.item.published == "2026-03-09" and c.item.authors == ["A B"]
    g = parse_gdelt(
        FICHAS["gdelt"],
        {
            "articles": [
                {
                    "url": "https://x.org/n",
                    "title": "Titular",
                    "seendate": "20261125T100000Z",
                    "domain": "x.org",
                    "sourcecountry": "US",
                    "language": "English",
                }
            ]
        },
    )[0]
    assert g.item.published == "2026-11-25" and "x.org" in g.item.text and g.item.extra["credito"].startswith("Fuente: GDELT")
    wb = parse_worldbank(
        FICHAS["bancomundial"],
        [
            {"page": 1},
            [
                {
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
                    "country": {"id": "WLD", "value": "World"},
                    "date": "2024",
                    "value": 1.0,
                },
                {
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"},
                    "country": {"id": "WLD", "value": "World"},
                    "date": "2023",
                    "value": None,
                },
            ],
        ],
    )
    assert len(wb) == 1 and "2024: 1.0" in wb[0].item.text and "2023" not in wb[0].item.text
    fr = parse_fred(
        FICHAS["fred"],
        {"observations": [{"date": "2026-10-01", "value": "4.1"}, {"date": "2026-09-01", "value": "."}]},
        "FEDFUNDS",
    )
    assert (
        "no está avalado" in fr[0].item.extra["credito"]
        and "2026-10-01: 4.1" in fr[0].item.text
        and "2026-09-01" not in fr[0].item.text
    )
    rw = parse_reliefweb(
        FICHAS["reliefweb"],
        {
            "data": [
                {
                    "id": 9,
                    "fields": {
                        "title": "Sitrep",
                        "url": "https://reliefweb.int/r/9",
                        "date": {"created": "2026-11-20T00:00:00+00:00"},
                        "body": "<p>Texto</p>",
                    },
                }
            ]
        },
    )[0]
    assert rw.item.published == "2026-11-20" and rw.item.text == "Texto"
    u = parse_ucdp(
        FICHAS["ucdp"],
        {"Result": [{"id": 5, "side_a": "A", "side_b": "B", "country": "X", "best": 3, "date_start": "2026-11-01"}]},
    )[0]
    assert u.source_id == "ucdp/5" and "A contra B" in u.item.text


def _real(env, log):
    def get(url, headers):
        log.append((url, headers))
        return json.dumps({"results": []})

    return RealFuentes(get=get, env=env, sleep=lambda s: log.append(("pausa", round(s, 2))), clock=lambda: 100.0)


def test_sin_clave_no_se_toca_la_red():
    log: list = []
    for ref, var in (("fred:FEDFUNDS", "FRED_API_KEY"), ("reliefweb:war", "RELIEFWEB_APPNAME"), ("ucdp:x", "UCDP_TOKEN")):
        try:
            _real({}, log).search(ref, 5)
            raise AssertionError("tenía que fallar")
        except SourceError as exc:
            assert var in exc.reason
    assert log == []


def test_el_email_va_en_el_pedido_solo_donde_lo_piden_y_hay_pausa_entre_pedidos():
    log: list = []
    r = _real({"INGESTA_CONTACTO_EMAIL": "yo@ejemplo.org"}, log)
    r.search("openalex:war", 99)
    url, headers = log[0]
    assert "mailto=yo%40ejemplo.org" in url and "per-page=50" in url and "yo@ejemplo.org" in headers["User-Agent"]
    r.search("openalex:war", 5)
    assert ("pausa", 0.2) in log  # segundo pedido dentro de la pausa de la ficha
    log.clear()
    _real({}, log).search("gdelt:war", 5)
    assert "mailto" not in log[0][0]


def test_las_fuentes_sin_adaptador_se_dicen_y_los_feeds_no_arman_url_con_texto_libre():
    log: list = []
    try:
        _real({}, log).search("oecd:x", 3)
    except SourceError as exc:
        assert "adaptador" in exc.reason
    r = RealFuentes(get=lambda u, h: log.append(u) or RSS, env={}, sleep=lambda s: None)
    r.search("fed:../../etc/passwd?x=1", 3)
    assert (
        log[0].startswith("https://www.federalreserve.gov/feeds/") and "?" not in log[0] and ".." not in log[0].replace("...", "")
    )


# --- el cocinero ------------------------------------------------------------------------------------------------------
def test_buscar_en_una_fuente_encola_ingiere_con_credito_y_no_repite(tmp_path):
    x = System(vault=tmp_path)
    out = x.owner("buscame lo más nuevo en openalex")
    assert any("busco" in o.lower() for o in out)
    x.tick()
    x.tick()
    x.tick()
    ids = sorted(n["id"] for n in x.notes())
    assert ids == [f"fuentes:openalex/MOCK{i}" for i in range(3)]
    nota = next((tmp_path / "Ingesta" / "fuentes").glob("*.md")).read_text(encoding="utf-8")
    assert "Crédito: Datos: OpenAlex (CC0)." in nota and "openalex" in nota
    assert x.act("fuentes", "buscar_fuente", {"ref": "openalex:armed conflict economics"})["text"].startswith("No hay nada nuevo")


def test_vigilar_una_fuente_pide_aprobacion_y_una_descartada_por_sus_terminos_no_existe():
    x = System()
    x.owner("vigilá la reserva federal todos los días")
    assert len(x.pending("vigilar")) == 1
    for descartada in ("aljazeera", "bbc", "fmi", "sipri"):
        r = x.act("fuentes", "buscar_fuente", {"ref": f"{descartada}:guerra"})
        assert r["state"] == "error" and "desconocida" in r["error"]


def test_un_tercero_no_dispara_ingestas_y_un_error_de_la_fuente_se_dice():
    x = System()
    x.stranger("buscame lo más nuevo en openalex")
    assert x.ctx("fuentes").shared.list("cola") == [] and x.pending("buscar_fuente") == []
    assert "falló" in x.act("fuentes", "buscar_fuente", {"ref": "gdelt:ERRORTECNI"})["text"]
