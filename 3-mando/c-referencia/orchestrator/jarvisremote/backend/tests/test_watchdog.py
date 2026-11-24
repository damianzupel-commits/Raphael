"""Tests del watchdog del orquestador (orquestador/watchdog.py): detección (loop, sin progreso, timeout, errores),
corte + aviso en el feed, límites desde el spec, y que NO molesta a una corrida sana. Sin LLM, sin red, sin modelos."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from brigades.spec import WatchSpec
from orquestador import routing, watchdog
from orquestador.server import create_app
from orquestador.watchdog import Limits, RunMonitor, supervise

FAST = Limits(max_seconds=5.0, stall_seconds=0.4, max_repeats=3, max_errors=3, poll=0.05)


@pytest.fixture(autouse=True)
def _aislar(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "_LOG", tmp_path / "wd.jsonl")  # nunca escribe el registro real
    watchdog._RECENT.clear()
    monkeypatch.delenv("WATCHDOG_ENABLED", raising=False)


class Fake:
    """Jefe falso: `script` es una corrutina que emite eventos."""

    def __init__(self, script, name="Raphael Test"):
        self.config = SimpleNamespace(name=name)
        self.script = script
        self.cancelled = False

    async def run(self, message, on_event=None):
        try:
            return await self.script(on_event)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def collect():
    evs: list[dict] = []

    async def cb(ev):
        evs.append(ev)

    return evs, cb


def run(coro):
    return asyncio.run(coro)


# --- detector (puro, sin asyncio) ----------------------------------------------
def _call(m, name="fs_read", args="{}"):
    m.observe({"type": "tool", "name": name, "args": args})


def test_monitor_corrida_sana_no_dispara():
    t = [0.0]
    m = RunMonitor(FAST, clock=lambda: t[0])
    for i in range(6):
        _call(m, args=json.dumps({"i": i}))  # distintas: no es loop
        m.observe({"type": "tool_result", "name": "fs_read", "ok": True, "summary": f"ok {i}"})
    assert m.check() is None


def test_monitor_loop_de_llamadas_identicas():
    m = RunMonitor(FAST)
    for _ in range(3):
        _call(m, args='{"q": "x"}')
    v = m.check()
    assert v and v.kind == "loop" and "fs_read" in v.detail


def test_monitor_loop_alternado_ABAB():
    m = RunMonitor(FAST)
    for _ in range(3):
        _call(m, "a", "{}")
        _call(m, "b", "{}")
    assert m.check().kind == "loop"


def test_monitor_respuesta_larga_repetida_es_loop_pero_corta_no():
    m = RunMonitor(FAST)
    for i in range(5):
        m.observe({"type": "tool_result", "name": "t", "ok": True, "summary": "status: ok"})  # corta: legítima
    assert m.check() is None
    long = "x" * 60
    for _ in range(3):
        m.observe({"type": "tool_result", "name": "t", "ok": True, "summary": long})
    assert m.check().kind == "loop"


def test_monitor_errores_seguidos_y_se_resetean_con_un_exito():
    m = RunMonitor(FAST)
    for _ in range(2):
        m.observe({"type": "tool_result", "name": "t", "ok": False, "summary": "boom"})
    m.observe({"type": "tool_result", "name": "t", "ok": True, "summary": "bien"})
    for _ in range(2):
        m.observe({"type": "tool_result", "name": "t", "ok": False, "summary": "boom"})
    assert m.check() is None
    m.observe({"type": "tool_result", "name": "t", "ok": False, "summary": "boom"})
    assert m.check().kind == "errores"


def test_monitor_sin_progreso_y_timeout_con_reloj_falso():
    t = [0.0]
    m = RunMonitor(Limits(max_seconds=100, stall_seconds=10, max_repeats=3, max_errors=3), clock=lambda: t[0])
    t[0] = 9
    assert m.check() is None
    t[0] = 11
    assert m.check().kind == "sin_progreso"
    m.observe({"type": "tool", "name": "x", "args": "1"})  # progreso: reinicia la ventana de stall
    t[0] = 20
    assert m.check() is None
    for i in range(1, 9):  # sigue habiendo progreso pero el turno es largo
        t[0] = 20 + i * 9
        m.observe({"type": "tool", "name": "x", "args": str(i + 1)})
        if i < 8:
            assert m.check() is None
    t[0] = 101
    assert m.check().kind == "timeout"


def test_monitor_no_corta_despues_del_final():
    t = [0.0]
    m = RunMonitor(FAST, clock=lambda: t[0])
    m.observe({"type": "final", "reply": "listo"})
    t[0] = 999
    assert m.check() is None


def test_delegar_no_cuenta_como_loop_y_se_anota_el_ayudante():
    m = RunMonitor(FAST)
    for _ in range(5):
        m.observe({"type": "tool", "name": "delegar:investigacion-forense", "args": "modo=forense"})
    assert m.check() is None and m.helper == "investigacion-forense"


# --- límites desde el spec -----------------------------------------------------
def test_limites_default_reusan_el_timeout_de_ayudante(monkeypatch):
    monkeypatch.setenv("BRIGADE_AYUDANTE_TIMEOUT_SECONDS", "120")
    monkeypatch.delenv("WATCHDOG_MARGIN_SECONDS", raising=False)
    monkeypatch.delenv("WATCHDOG_JEFE_SECONDS", raising=False)
    lim = watchdog.limits_for(None)
    # 120 del ayudante + 30 de margen + 600 para el LLM del jefe (planificar y sintetizar): si un ayudante agota su tiempo,
    # el jefe todavía tiene que poder reportar ese fallo sin que lo corten a él
    assert lim.max_seconds == 750
    monkeypatch.setenv("WATCHDOG_JEFE_SECONDS", "0")
    assert watchdog.limits_for(None).max_seconds == 150
    assert lim.stall_seconds == 300 and lim.max_repeats == 4 and lim.max_errors == 5


def test_limites_del_spec_ganan_a_los_defaults():
    spec = SimpleNamespace(watch=WatchSpec(max_seconds=77, stall_seconds=12, max_repeats=2, max_errors=9),
                           helper_timeout=lambda: 500)
    lim = watchdog.limits_for(spec)
    assert (lim.max_seconds, lim.stall_seconds, lim.max_repeats, lim.max_errors) == (77, 12, 2, 9)


def test_el_timeout_del_spec_se_reusa_para_la_duracion_esperada(monkeypatch):
    monkeypatch.delenv("WATCHDOG_MARGIN_SECONDS", raising=False)
    monkeypatch.setenv("WATCHDOG_JEFE_SECONDS", "0")
    lim = watchdog.limits_for(SimpleNamespace(watch=None, helper_timeout=lambda: 600))
    assert lim.max_seconds == 630


def test_seguridad_declara_su_vigilancia():
    from brigades.seguridad import SPEC

    assert SPEC.watch and SPEC.watch.stall_seconds == 900


# --- supervise: corta y avisa --------------------------------------------------
def test_corrida_sana_pasa_intacta_y_sin_eventos_del_watchdog():
    async def script(cb):
        await cb({"type": "start", "topic": "x"})
        await cb({"type": "tool", "name": "a", "args": "1"})
        await cb({"type": "tool_result", "name": "a", "ok": True, "summary": "ok"})
        await cb({"type": "final", "reply": "listo"})
        return "listo", []

    evs, cb = collect()
    out = run(supervise(Fake(script), "hola", cb, brigade="cerebro", limits=FAST))
    assert out == ("listo", [])
    assert [e["type"] for e in evs] == ["start", "tool", "tool_result", "final"]
    assert watchdog.recent() == []


def test_corta_un_loop_y_lo_avisa_en_el_feed():
    async def script(cb):
        await cb({"type": "start", "topic": "x"})
        while True:
            await cb({"type": "tool", "name": "fs_read", "args": '{"p": "a"}'})
            await asyncio.sleep(0.01)

    jefe = Fake(script)
    evs, cb = collect()
    out = run(supervise(jefe, "hola", cb, brigade="cerebro", limits=FAST))
    assert out is None and jefe.cancelled
    wd = [e for e in evs if e["type"] == "watchdog"]
    assert len(wd) == 1 and wd[0]["action"] == "cut" and wd[0]["reason"] == "loop"
    assert "el watchdog cortó al jefe Raphael Test por loop" in wd[0]["message"]
    assert evs[-1]["type"] == "final" and "interrumpió" in evs[-1]["reply"]  # el feed queda cerrado
    assert watchdog.recent()[0]["kind"] == "loop"
    assert (watchdog._LOG).read_text(encoding="utf-8").count("\n") == 1  # quedó en su registro


def test_corta_un_deadlock_sin_progreso_nombrando_al_ayudante():
    async def script(cb):
        await cb({"type": "start", "topic": "x"})
        await cb({"type": "tool", "name": "delegar:investigacion-scout", "args": "modo=scout"})
        await asyncio.sleep(60)  # cuelgue

    jefe = Fake(script)
    evs, cb = collect()
    out = run(supervise(jefe, "hola", cb, brigade="investigacion", limits=FAST))
    assert out is None and jefe.cancelled
    wd = next(e for e in evs if e["type"] == "watchdog")
    assert wd["reason"] == "sin_progreso" and wd["target"] == "ayudante investigacion-scout"
    assert "ayudante investigacion-scout" in wd["message"] and "deadlock" in wd["message"]


def test_corta_por_timeout_aunque_haya_progreso():
    lim = Limits(max_seconds=0.3, stall_seconds=5, max_repeats=50, max_errors=50, poll=0.05)

    async def script(cb):
        i = 0
        while True:
            i += 1
            await cb({"type": "tool", "name": "a", "args": str(i)})
            await asyncio.sleep(0.02)

    evs, cb = collect()
    assert run(supervise(Fake(script), "x", cb, brigade="cerebro", limits=lim)) is None
    assert next(e for e in evs if e["type"] == "watchdog")["reason"] == "timeout"


def test_corta_por_errores_seguidos():
    async def script(cb):
        while True:
            await cb({"type": "tool_result", "name": "t", "ok": False, "summary": "falló"})
            await asyncio.sleep(0.01)

    evs, cb = collect()
    assert run(supervise(Fake(script), "x", cb, brigade="cerebro", limits=FAST)) is None
    assert next(e for e in evs if e["type"] == "watchdog")["reason"] == "errores"


def test_reporta_sin_cortar_cuando_el_jefe_ya_corto_al_ayudante():
    async def script(cb):
        await cb({"type": "tool", "name": "delegar:investigacion-scout", "args": "modo=scout"})
        await cb({"type": "tool_result", "name": "delegar:investigacion-scout", "ok": False,
                  "summary": "El ayudante investigacion-scout no terminó en 900s y se lo cortó."})
        await cb({"type": "final", "reply": "x"})
        return "x", []

    evs, cb = collect()
    assert run(supervise(Fake(script), "x", cb, brigade="investigacion", limits=FAST)) == ("x", [])
    wd = [e for e in evs if e["type"] == "watchdog"]
    assert len(wd) == 1 and wd[0]["action"] == "reported" and wd[0]["reason"] == "timeout"


def test_una_excepcion_del_jefe_se_propaga_igual_que_sin_watchdog():
    async def script(cb):
        raise RuntimeError("Ollama apagado")

    _, cb = collect()
    with pytest.raises(RuntimeError, match="Ollama apagado"):
        run(supervise(Fake(script), "x", cb, brigade="cerebro", limits=FAST))


def test_desactivado_por_env_no_vigila(monkeypatch):
    monkeypatch.setenv("WATCHDOG_ENABLED", "0")

    async def script(cb):
        for _ in range(10):
            await cb({"type": "tool", "name": "a", "args": "igual"})
        return "ok", []

    _, cb = collect()
    assert run(supervise(Fake(script), "x", cb, brigade="cerebro", limits=FAST)) == ("ok", [])
    assert watchdog.recent() == []


def test_si_se_cancela_el_turno_no_queda_la_corrida_huerfana():
    jefe_cancelado = []

    async def script(cb):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            jefe_cancelado.append(True)
            raise

    async def main():
        _, cb = collect()
        t = asyncio.create_task(supervise(Fake(script), "x", cb, brigade="cerebro", limits=Limits(60, 60, 4, 5, 0.05)))
        await asyncio.sleep(0.2)
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)
        await asyncio.sleep(0.1)

    run(main())
    assert jefe_cancelado == [True]


# --- integración con el servidor del orquestador --------------------------------
PORT = 8011
HOST = {"host": f"127.0.0.1:{PORT}"}


def test_el_servidor_corta_una_corrida_colgada_y_el_feed_lo_muestra(monkeypatch):
    async def colgado(cb):
        await cb({"type": "start", "topic": "x"})
        while True:
            await cb({"type": "tool", "name": "fs_read", "args": "igual"})
            await asyncio.sleep(0.005)

    jefe = Fake(colgado)
    jefe.model = "fake"
    monkeypatch.setattr("brigades.registry.get_chief", lambda b: jefe)
    monkeypatch.setattr(routing, "llm_classify", lambda m: asyncio.sleep(0, result=None))
    monkeypatch.setattr(watchdog, "limits_for", lambda spec: Limits(5, 5, 3, 3, 0.05))
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    r = c.post("/api/chat", json={"message": "¿qué sé de ransomware?"}, headers={"Authorization": "Bearer tok", **HOST})
    evs = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    types = [e["type"] for e in evs]
    assert types[0] == "route" and "watchdog" in types and types[-1] == "final"
    assert next(e for e in evs if e["type"] == "watchdog")["reason"] == "loop"
    st = c.get("/api/watchdog", headers={"Authorization": "Bearer tok", **HOST}).json()
    assert st["enabled"] and st["recent"][0]["kind"] == "loop"


def test_endpoint_watchdog_exige_token():
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    assert c.get("/api/watchdog").status_code in (401, 403)


def test_la_ui_muestra_las_intervenciones_del_watchdog():
    from pathlib import Path

    ui = (Path(__file__).resolve().parent.parent / "orquestador" / "ui.html").read_text(encoding="utf-8")
    assert 'ev.type === "watchdog"' in ui and "esc(ev.message" in ui  # escapado: el mensaje trae texto de tools
