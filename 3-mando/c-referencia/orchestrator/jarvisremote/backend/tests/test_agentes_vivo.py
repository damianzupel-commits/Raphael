"""Cocineros (agentes permanentes por brigada) y Efímeros en vivo (registro de ayudantes que corren ahora). Sin modelos ni red."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from brigades import live
from brigades.chief import ChiefConfig
from brigades.engine import GenericChief
from brigades.spec import AyudanteSpec, BrigadeSpec, RouteRule, Routing
from orquestador import agentes, routing, watchdog
from orquestador.server import create_app

PORT = 8014
HOST = {"host": f"127.0.0.1:{PORT}"}
AUTH = {"Authorization": "Bearer tok", **HOST}


@pytest.fixture(autouse=True)
def _limpio():
    live.reset()
    yield
    live.reset()


def _ayudante(modo, persistent=False):
    return AyudanteSpec(
        modo=modo, id=f"demo-{modo}", descripcion=f"hace {modo}", donde="x",
        config=lambda: ChiefConfig(id=f"demo-{modo}", name=modo, tool_names=frozenset({"t"}), system_prompt="p", persistent=persistent),
        client_model=lambda: (SimpleNamespace(base_url="https://integrate.api.nvidia.com/v1/"), "nvidia/nemotron-x"),
        tool_names=lambda: frozenset({"t"}))


def _spec(**kw):
    base = dict(id="demo", name="Demo", purpose="probar", prompt="p", ayudantes=(_ayudante("a"), _ayudante("b")),
                routing=Routing(reglas=(RouteRule("a", r"\bfoo\b"),), default="b"))
    base.update(kw)
    return BrigadeSpec(**base)


# --- registro vivo -------------------------------------------------------------------------------------------------
def test_registro_start_touch_finish():
    t = live.start("inv", "Investigación", "inv-scout", "scout", "gpt (Groq)", "investigá\nalgo " + "x" * 300)
    snap = live.snapshot()
    assert [a["ayudante"] for a in snap["activos"]] == ["inv-scout"] and len(snap["activos"][0]["tarea"]) <= 140
    assert "\n" not in snap["activos"][0]["tarea"]
    live.touch(t, {"type": "tool", "name": "research_topic", "args": '{"q": 1}'})
    a = live.snapshot()["activos"][0]
    assert (a["tool"], a["pasos"]) == ("research_topic", 1)
    live.touch(t, {"type": "tool_result", "name": "research_topic", "ok": True})
    assert live.snapshot()["activos"][0]["tool"] is None  # volvió a "pensando"
    live.finish(t, "ok")
    s = live.snapshot()
    assert s["activos"] == [] and s["recientes"][0]["resultado"] == "ok" and s["recientes"][0]["segundos"] >= 0


def test_recientes_acotados_y_finish_es_idempotente():
    for i in range(20):
        t = live.start("b", "B", f"h{i}", "m", "x", "t")
        live.finish(t, "ok")
        live.finish(t, "ok")  # segunda vez: no duplica ni rompe
    assert len(live.snapshot()["recientes"]) == 12


def test_mark_cut_anota_el_motivo_en_el_reciente_de_esa_brigada():
    t1 = live.start("a", "A", "h", "m", "x", "t")
    live.finish(t1, "cancelado")
    t2 = live.start("b", "B", "h", "m", "x", "t")
    live.finish(t2, "ok")
    live.mark_cut("a", "loop: lo mismo 4 veces")
    r = {x["brigada"]: x for x in live.snapshot()["recientes"]}
    assert r["a"]["resultado"] == "cortado por el watchdog" and "loop" in r["a"]["detalle"] and r["b"]["resultado"] == "ok"


# --- integración con el motor ---------------------------------------------------------------------------------------
class _Helper:
    def __init__(self, script):
        self.script = script

    async def run(self, task, on_event=None):
        return await self.script(on_event)


def _chief(spec, script, tmp_path, monkeypatch):
    from brigades import chief as chief_mod

    monkeypatch.setattr(chief_mod, "_STATE_DIR", tmp_path)
    c = GenericChief(spec.chief_config(), None, "m", spec=spec)
    monkeypatch.setattr(c, "_spawn", lambda modo: _Helper(script))
    return c


def test_el_motor_registra_al_efimero_mientras_corre_y_lo_quita_al_terminar(tmp_path, monkeypatch):
    vistos = {}

    async def script(cb):
        await cb({"type": "start", "topic": "x"})
        await cb({"type": "tool", "name": "research_topic", "args": "{}"})
        vistos["durante"] = live.snapshot()["activos"]
        await cb({"type": "final", "reply": "listo"})
        return "listo", []

    async def on_event(ev):
        pass

    c = _chief(_spec(), script, tmp_path, monkeypatch)
    asyncio.run(c.run("pedido de prueba", on_event=on_event))
    a = vistos["durante"][0]
    assert (a["brigada"], a["ayudante"], a["modo"], a["tool"]) == ("demo", "demo-b", "b", "research_topic")
    assert a["modelo"] == "nemotron-x (NVIDIA)" and a["tarea"] == "pedido de prueba"
    s = live.snapshot()
    assert s["activos"] == [] and s["recientes"][0]["resultado"] == "ok"


def test_timeout_error_y_cancelacion_quedan_registrados(tmp_path, monkeypatch):
    async def colgado(cb):
        await asyncio.sleep(60)

    async def roto(cb):
        raise RuntimeError("boom")

    async def on_event(ev):
        pass

    c = _chief(_spec(helper_timeout=lambda: 0.1), colgado, tmp_path, monkeypatch)
    asyncio.run(c.run("x", on_event=on_event))
    assert live.snapshot()["recientes"][0]["resultado"] == "timeout"

    c = _chief(_spec(), roto, tmp_path, monkeypatch)
    asyncio.run(c.run("x", on_event=on_event))
    assert live.snapshot()["recientes"][0]["resultado"] == "error"

    async def main():  # cortado desde afuera (como hace el watchdog)
        c2 = _chief(_spec(), colgado, tmp_path, monkeypatch)
        t = asyncio.create_task(c2.run("x", on_event=on_event))
        await asyncio.sleep(0.2)
        assert len(live.snapshot()["activos"]) == 1
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)

    asyncio.run(main())
    s = live.snapshot()
    assert s["activos"] == [] and s["recientes"][0]["resultado"] == "cancelado"


def test_el_watchdog_anota_por_que_corto_al_efimero(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "_LOG", tmp_path / "wd.jsonl")

    async def loop(cb):
        while True:
            await cb({"type": "tool", "name": "fs_read", "args": "igual"})
            await asyncio.sleep(0.005)

    async def on_event(ev):
        pass

    c = _chief(_spec(), loop, tmp_path, monkeypatch)
    lim = watchdog.Limits(5, 5, 3, 3, 0.05)
    assert asyncio.run(watchdog.supervise(c, "x", on_event, brigade="demo", limits=lim)) is None
    r = live.snapshot()["recientes"][0]
    assert r["resultado"] == "cortado por el watchdog" and "loop" in r["detalle"]


# --- cocineros --------------------------------------------------------------------------------------------------------
def test_el_jefe_es_cocinero_con_su_modelo_efectivo_propio(monkeypatch):
    monkeypatch.setattr(BrigadeSpec, "load_client_model", lambda self: (SimpleNamespace(base_url="https://api.groq.com/openai/v1"), "openai/gpt-oss-120b"))
    d = agentes.cocineros(_spec())
    c = d["cocineros"][0]
    # todo jefe tiene LLM PROPIO (planifica y sintetiza): se muestra el suyo, distinto del de sus ayudantes
    assert (c["rol"], c["modelo"], c["memoria"], c["tools"]) == ("jefe", "gpt-oss-120b (Groq)", True, 1)
    assert "sintetiza" in c["detalle"] and "orquestador" in c["detalle"]


def test_cocineros_de_una_brigada_lista_al_jefe_y_deja_a_los_efimeros_aparte(monkeypatch):
    monkeypatch.setattr(BrigadeSpec, "load_client_model", lambda self: (SimpleNamespace(base_url="https://integrate.api.nvidia.com/v1"), "nvidia/nemotron-x"))
    d = agentes.cocineros(_spec())
    assert [c["rol"] for c in d["cocineros"]] == ["jefe"] and "sin LLM propio" not in d["cocineros"][0]["modelo"]
    assert {e["modo"] for e in d["efimeros"]} == {"a", "b"}  # no son cocineros: nacen y mueren por tarea
    assert all(e["modelo"] == "nemotron-x (NVIDIA)" for e in d["efimeros"])


def test_un_ayudante_persistente_cuenta_como_cocinero():
    d = agentes.cocineros(_spec(ayudantes=(_ayudante("a", persistent=True), _ayudante("b")),
                                routing=Routing(reglas=(RouteRule("a", "x"),), default="b")))
    assert [c["rol"] for c in d["cocineros"]] == ["jefe", "ayudante «a»"]
    assert [e["modo"] for e in d["efimeros"]] == ["b"]


def test_las_brigadas_reales_dan_cocineros_con_modelo_resuelto():
    out = agentes.todas(["cerebro", "investigacion", "seguridad", "no-existe"])
    assert set(out) == {"cerebro", "investigacion", "seguridad"}  # una que no resuelve se omite sin romper las demás
    assert out["cerebro"]["cocineros"][0]["rol"] == "jefe"
    assert {e["modo"] for e in out["investigacion"]["efimeros"]} == {"scout", "forense"}
    assert {e["modo"] for e in out["seguridad"]["efimeros"]} == {"escaneo", "reporte"}


# --- API y UI --------------------------------------------------------------------------------------------------------
def test_endpoints_exigen_token_y_devuelven_lo_esperado(monkeypatch):
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    assert c.get("/api/efimeros").status_code in (401, 403) and c.get("/api/cocineros").status_code in (401, 403)
    t = live.start("investigacion", "Raphael Investigación", "investigacion-forense", "forense", "nemo (NVIDIA)", "creá un caso")
    live.touch(t, {"type": "tool", "name": "investigation_create_case", "args": "{}"})
    j = c.get("/api/efimeros", headers=AUTH).json()
    assert j["activos"][0]["ayudante"] == "investigacion-forense" and j["activos"][0]["tool"] == "investigation_create_case"
    assert "ahora" in j and j["recientes"] == []
    k = c.get("/api/cocineros", headers=AUTH).json()["brigadas"]
    assert "cerebro" in k and "cocineros" in k["cerebro"]


def test_la_ui_tiene_el_panel_de_cocineros_y_el_tablero_en_vivo_escapados():
    ui = (Path(__file__).resolve().parent.parent / "orquestador" / "ui.html").read_text(encoding="utf-8")
    for pieza in ('id="cocineros"', "/api/cocineros", "/api/efimeros", 'id:"vivo"', "buildVivoPane", 'id="vivochip"'):
        assert pieza in ui, pieza
    assert "esc(a.brigada_nombre" in ui and "esc(a.tarea" in ui and "esc(c.modelo" in ui  # todo lo que viene de datos, escapado


def test_una_brigada_creada_tambien_tiene_sus_cocineros():
    from brigades import factory
    from brigades.ejemplos import EJEMPLO_DELEGA, EJEMPLO_UN_AYUDANTE

    una = factory.compile_spec(factory.validate_draft(EJEMPLO_UN_AYUDANTE, frozenset())[0])
    d = agentes.cocineros(una)
    assert [c["rol"] for c in d["cocineros"]] == ["jefe"] and [e["modo"] for e in d["efimeros"]] == ["consulta"]
    delega = factory.compile_spec(factory.validate_draft(EJEMPLO_DELEGA, frozenset())[0])
    d = agentes.cocineros(delega)
    assert d["cocineros"][0]["rol"] == "jefe" and len(d["efimeros"]) == len(delega.ayudantes)
