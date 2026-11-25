"""Cumplimiento: checklist, fuentes simuladas, cambios de la fuente, modos y tick."""

from datetime import datetime, timedelta

import pytest
from kit import FULL, MINIMAL, System
from raphael_core import ActionError

from raphael_legales import sources
from raphael_legales.config import legales_config
from raphael_legales.norms import NORMS
from raphael_legales.sources import HttpSources, MockSources, OffSources, build_sources

NOW = datetime(2026, 11, 25, 10, 0)


def item(check, i):
    return next(x for x in check["items"] if x["id"] == i)


def test_checklist_deduce_del_archivo_y_de_la_config():
    cfg = {**FULL, "checklist": {"respuestas": {"dp-derechos": "cumple", "wa-baja": "no_aplica"}}}
    x = System(cfg)
    c = x.cmd("cumplimiento", "checklist")
    assert item(c, "dp-derechos")["state"] == "cumple" and item(c, "wa-baja")["state"] == "no_aplica"
    assert item(c, "fa-cuit")["state"] == "cumple" and item(c, "dp-politica")["state"] == "pendiente"
    assert "no es asesoramiento legal" in c["aviso"] or "No es asesoramiento legal" in c["aviso"]
    # emitir la política y un consentimiento de WhatsApp mueve los ítems solos
    d = x.cmd("documentos", "borrador", {"kind": "politica_privacidad"})
    x.cmd("archivo", "emitir", {"doc_id": d["id"], "text": "Política final"})
    x.approve(x.pending("emitir_documento")[0]["id"])
    x.cmd("archivo", "consentimiento", {"contact": "whatsapp:1", "purpose": "avisos", "channel": "whatsapp"})
    c = x.cmd("cumplimiento", "checklist")
    assert all(item(c, i)["state"] == "cumple" and item(c, i)["auto"] for i in ("dp-politica", "dp-ia-terceros", "wa-optin", "dp-consentimiento"))
    done, total = map(int, c["score"].split("/"))
    assert done >= 6 and total == 14                                              # 15 ítems menos 1 no aplica


def test_sin_datos_del_negocio_los_items_quedan_pendientes():
    c = System(MINIMAL).cmd("cumplimiento", "checklist")
    assert item(c, "fa-cuit")["state"] == "pendiente" and item(c, "co-reclamos")["state"] == "pendiente"


def test_sin_verificar_hasta_que_se_consulta_y_despues_consultada():
    x = System()
    assert all(i["source"]["state"] == "sin_verificar" for i in x.cmd("cumplimiento", "checklist")["items"])
    out = x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326"]})
    n = next(o for o in out if o["id"] == "ley-25326")
    assert n["state"] == "consultada" and n["mode"] == "mock" and n["checked_at"].startswith("2026-11-25")
    assert item(x.cmd("cumplimiento", "checklist"), "dp-politica")["source"]["state"] == "consultada"
    assert x.events("norma.verificada")


def test_el_borrador_cita_si_la_fuente_esta_verificada():
    x = System()
    d = x.cmd("documentos", "borrador", {"kind": "politica_privacidad"})
    assert d["sources"]["ley-25326"]["state"] == "sin_verificar" and any("sin verificar" in w for w in d["warnings"])
    x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326"]})
    d2 = x.cmd("documentos", "borrador", {"kind": "politica_privacidad"})
    assert d2["sources"]["ley-25326"]["state"] == "consultada" and not d2["warnings"]


def test_vencida_a_los_dias_de_vigencia():
    x = System()
    x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-24240"]})
    x.clock.advance(days=29)
    assert next(n for n in x.cmd("cumplimiento", "normas") if n["id"] == "ley-24240")["state"] == "consultada"
    x.clock.advance(days=2)
    assert next(n for n in x.cmd("cumplimiento", "normas") if n["id"] == "ley-24240")["state"] == "vencida"


def test_fuente_que_cae_o_no_es_la_norma_queda_sin_verificar(monkeypatch):
    bad = MockSources({NORMS["ley-25326"].url: ConnectionError("sin red"), NORMS["ley-24240"].url: "una receta de cocina"})
    monkeypatch.setattr("raphael_legales.cooks.compliance.build_sources", lambda *_: bad)
    x = System()
    out = {n["id"]: n for n in x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326", "ley-24240"]})}
    assert out["ley-25326"]["state"] == "sin_verificar" and "ConnectionError" in out["ley-25326"]["detail"]
    assert out["ley-24240"]["state"] == "sin_verificar" and "no parece" in out["ley-24240"]["detail"]
    assert len(x.events("norma.sin_verificar")) == 2


def test_aviso_si_la_fuente_cambia(monkeypatch):
    pages = {NORMS["ley-25326"].url: "Ley 25.326 datos personales versión uno"}
    monkeypatch.setattr("raphael_legales.cooks.compliance.build_sources", lambda *_: MockSources(pages))
    x = System()
    x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326"]})
    assert not x.events("norma.cambio_detectado")
    pages[NORMS["ley-25326"].url] = "Ley 25.326 datos personales versión DOS"
    x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326"]})
    assert x.events("norma.cambio_detectado")


def test_modo_off_todo_sin_verificar():
    x = System({**FULL, "fuentes": {"modo": "off"}})
    out = x.cmd("cumplimiento", "verificar_normas", {"ids": ["ley-25326"]})
    assert next(n for n in out if n["id"] == "ley-25326")["state"] == "sin_verificar"


def test_norma_desconocida_es_error():
    with pytest.raises(ActionError):
        System().cmd("cumplimiento", "verificar_normas", {"ids": ["ley-inventada"]})


def test_tick_verifica_solo_en_modo_real_y_una_vez_por_dia(monkeypatch):
    calls = MockSources()
    monkeypatch.setattr("raphael_legales.cooks.compliance.build_sources", lambda *_: calls)
    x = System({**FULL, "fuentes": {"modo": "real"}})
    x.tick(NOW)
    n = len(calls.calls)
    assert n == len(NORMS)
    x.tick(NOW + timedelta(hours=1))
    assert len(calls.calls) == n
    y = System({**FULL, "fuentes": {"modo": "mock"}})
    y.tick(NOW)                                                                   # fuera de real, el tick no consulta
    assert y.cmd("cumplimiento", "normas")[0]["state"] == "sin_verificar"


def test_http_real_con_fetch_inyectado_sin_red():
    ok = HttpSources(fetch=lambda url, t: "<html><script>x</script><h1>Ley 25.326</h1> Datos Personales</html>")
    r = ok.check(NORMS["ley-25326"], "https://x.test/ley", NOW)
    assert r.ok and r.mode == "real" and len(r.sha256) == 64
    assert not HttpSources(fetch=lambda u, t: "otra cosa").check(NORMS["ley-25326"], "https://x.test", NOW).ok
    assert "https" in HttpSources(fetch=lambda u, t: "x").check(NORMS["ley-25326"], "http://x.test", NOW).error

    def boom(url, t):
        raise TimeoutError

    assert "TimeoutError" in HttpSources(fetch=boom).check(NORMS["ley-25326"], "https://x.test", NOW).error


def test_adaptadores_y_urls_oficiales_https():
    assert isinstance(build_sources("real"), HttpSources) and isinstance(build_sources("mock"), MockSources)
    assert isinstance(build_sources("off"), OffSources) and sources.OffSources().check(NORMS["ley-24240"], "u", NOW).error
    assert all(n.url.startswith("https://") for n in NORMS.values())


def test_config_lee_el_entorno_y_la_config_gana():
    env = {"LEGALES_NEGOCIO_NOMBRE": "Desde Env", "LEGALES_NEGOCIO_CUIT": "20-1-1", "LEGALES_FUENTES_MODO": "off",
           "LEGALES_FUENTES_TIMEOUT": "5"}
    cfg = legales_config({"negocio": {"nombre": "Desde Config"}}, env)
    assert cfg.negocio.nombre == "Desde Config" and cfg.negocio.cuit == "20-1-1"
    assert cfg.fuentes.modo == "off" and cfg.fuentes.timeout == 5.0
    assert legales_config({}, {}).fuentes.modo == "real"


def test_salud_ok_aunque_falten_datos_y_avisa():
    x = System(MINIMAL)
    h = x.rt.run(x.rt.check_health("legales"))
    assert h["ok"] and "faltan datos del negocio" in h["detail"] and "fuentes en modo mock" in h["detail"]
    assert System().rt.run(System().rt.check_health("legales"))["ok"]


def test_config_invalida_no_monta():
    with pytest.raises(AssertionError):
        System({"fuentes": {"modo": "otro"}})
    with pytest.raises(ValueError):
        legales_config({"fuentes": {"modo": "otro"}})
