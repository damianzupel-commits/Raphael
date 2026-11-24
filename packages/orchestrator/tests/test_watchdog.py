"""Watchdog del orquestador: puerta de O2 (parte 1).

Portado de JarvisRemote `tests/test_watchdog.py` a los eventos del motor v2 (`delegation`, `tool`/`tool_result` con
`helper`, `helper_result`, `heartbeat`, `report`). Lo del servidor HTTP y la UI no se porta: es de la pieza 03.
"""

from __future__ import annotations

import asyncio
import json

from kit import Script, call, emitter, msg
from raphael_core.context import OrchestratorContext
from raphael_core.engine import WatchSpec
from raphael_core.store import Store

from raphael_orchestrator import config_from
from raphael_orchestrator.watchdog import Limits, Log, RunMonitor, limits_for, supervise

FAST = Limits(max_seconds=5.0, stall_seconds=0.4, max_repeats=3, max_errors=3, poll=0.02)


def run(coro):
    return asyncio.run(coro)


# --- detector --------------------------------------------------------------------------------------------------------------
def _call(m, name="fs_read", args="{}", helper=None):
    m.observe({"type": "tool", "name": name, "args": args, **({"helper": helper} if helper else {})})


def test_monitor_corrida_sana_no_dispara():
    t = [0.0]
    m = RunMonitor(FAST, clock=lambda: t[0])
    for i in range(6):
        _call(m, args=json.dumps({"i": i}))
        m.observe({"type": "tool_result", "name": "fs_read", "ok": True, "summary": f"ok {i}"})
    assert m.check() is None


def test_monitor_loop_de_llamadas_identicas_y_alternadas():
    m = RunMonitor(FAST)
    for _ in range(3):
        _call(m, args='{"q": "x"}')
    v = m.check()
    assert v and v.kind == "loop" and "fs_read" in v.detail
    m2 = RunMonitor(FAST)
    for _ in range(3):
        _call(m2, "a")
        _call(m2, "b")
    assert m2.check().kind == "loop"


def test_monitor_casi_la_misma_llamada_es_loop_pero_numeros_distintos_no():
    m = RunMonitor(FAST)
    for q in ('{"q": "Rust"}', '{"q": "rust "}', '{"q": "RUST."}'):
        _call(m, "search", q)
    assert m.check().kind == "loop" and "casi la misma" in m.check().detail
    m2 = RunMonitor(FAST)
    for i in range(3):
        _call(m2, "read", f'{{"n": "nota_{i}"}}')
    assert m2.check() is None


def test_la_misma_llamada_de_dos_efimeros_en_paralelo_no_es_loop():
    m = RunMonitor(Limits(5, 5, 3, 3))
    for h in ("a-web", "b-web"):
        _call(m, "search", "x", helper=h)
    _call(m, "search", "x", helper="a-web")
    assert m.check() is None


def test_monitor_respuesta_larga_repetida_es_loop_pero_corta_no():
    m = RunMonitor(FAST)
    for _ in range(5):
        m.observe({"type": "tool_result", "name": "t", "ok": True, "summary": "status: ok"})
    assert m.check() is None
    for _ in range(3):
        m.observe({"type": "tool_result", "name": "t", "ok": True, "summary": "x" * 60})
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
    assert m.check().kind == "errors"


def test_monitor_sin_progreso_y_timeout_con_reloj_falso():
    t = [0.0]
    m = RunMonitor(Limits(max_seconds=100, stall_seconds=10, max_repeats=3, max_errors=3), clock=lambda: t[0])
    t[0] = 9
    assert m.check() is None
    t[0] = 11
    assert m.check().kind == "stall"
    _call(m, "x", "1")
    t[0] = 20
    assert m.check() is None
    for i in range(1, 9):
        t[0] = 20 + i * 9
        _call(m, "x", str(i + 1))
        if i < 8:
            assert m.check() is None
    t[0] = 101
    assert m.check().kind == "timeout"


def test_con_latidos_el_motor_tiene_mas_aire_pero_no_infinito():
    t = [0.0]
    m = RunMonitor(Limits(max_seconds=1000, stall_seconds=30, max_repeats=3, max_errors=3), clock=lambda: t[0])
    t[0] = 50
    m.observe({"type": "heartbeat", "phase": "synthesis"})
    assert m.check() is None                       # 50 s sin eventos, pero late: sigue
    t[0] = 95
    assert m.check().kind == "stall"               # 95 > 30 * 3


def test_no_corta_despues_del_reporte_y_anota_el_efimero():
    t = [0.0]
    m = RunMonitor(FAST, clock=lambda: t[0])
    m.observe({"type": "delegation", "helper": "investigacion-forense", "mode": "forense"})
    assert m.helper == "investigacion-forense"
    m.observe({"type": "report", "report": {}})
    t[0] = 999
    assert m.check() is None


# --- límites ----------------------------------------------------------------------------------------------------------------
def test_los_limites_reusan_el_timeout_de_los_efimeros_y_los_del_jefe_ganan():
    cfg = config_from({}).watchdog
    lim = limits_for({"helper_timeout": 120}, cfg)
    assert lim.max_seconds == 120 + 30 + 600 and lim.stall_seconds == 300 and lim.max_repeats == 4 and lim.max_errors == 5
    assert limits_for(None, config_from({"watchdog": {"chief_seconds": 0}}).watchdog).max_seconds == 900 + 30
    lim = limits_for({"helper_timeout": 500, "max_seconds": 77, "stall_seconds": 12, "max_repeats": 2, "max_errors": 9},
                     cfg)
    assert (lim.max_seconds, lim.stall_seconds, lim.max_repeats, lim.max_errors) == (77, 12, 2, 9)


# --- supervise ------------------------------------------------------------------------------------------------------------
def _runner(script, cancelled=None):
    async def run_(feed):
        try:
            return await script(feed)
        except asyncio.CancelledError:
            if cancelled is not None:
                cancelled.append(True)
            raise
    return run_


def test_corrida_sana_pasa_intacta_y_sin_eventos_del_watchdog():
    async def script(cb):
        await cb({"type": "start"})
        await cb({"type": "tool", "name": "a", "args": "1"})
        await cb({"type": "tool_result", "name": "a", "ok": True, "summary": "ok"})
        await cb({"type": "report", "report": {}})
        return "REPORTE"

    evs = []
    log = Log(Store().space("_orchestrator"))
    out = run(supervise(_runner(script), emitter(evs), brigade="cerebro", limits=FAST, log=log))
    assert out == ("REPORTE", "") and [e["type"] for e in evs] == ["start", "tool", "tool_result", "report"]
    assert log.recent() == []


def test_corta_un_loop_lo_avisa_y_lo_registra():
    async def script(cb):
        while True:
            await cb({"type": "tool", "name": "fs_read", "args": '{"p": "a"}'})
            await asyncio.sleep(0.005)

    cancelled, evs = [], []
    log = Log(Store().space("_orchestrator"))
    out, warning = run(supervise(_runner(script, cancelled), emitter(evs), brigade="cerebro", brigade_name="Cerebro",
                                 limits=FAST, log=log))
    assert out is None and cancelled == [True]
    [wd] = [e for e in evs if e["type"] == "watchdog"]
    assert wd["action"] == "cut" and wd["reason"] == "loop" and "cortó al jefe de Cerebro por loop" in wd["message"]
    assert warning.startswith("El watchdog cortó") and "interrumpió" in warning
    assert log.recent()[0]["kind"] == "loop"


def test_corta_un_deadlock_nombrando_al_efimero():
    async def script(cb):
        await cb({"type": "delegation", "helper": "investigacion-scout", "mode": "scout"})
        await asyncio.sleep(60)

    evs = []
    out, _ = run(supervise(_runner(script), emitter(evs), brigade="investigacion", limits=FAST))
    wd = next(e for e in evs if e["type"] == "watchdog")
    assert out is None and wd["reason"] == "stall" and wd["target"] == "efímero investigacion-scout"
    assert "deadlock" in wd["message"]


def test_corta_por_timeout_aunque_haya_progreso_y_por_errores_seguidos():
    async def busy(cb):
        i = 0
        while True:
            i += 1
            await cb({"type": "tool", "name": "a", "args": str(i)})
            await asyncio.sleep(0.01)

    evs = []
    lim = Limits(max_seconds=0.2, stall_seconds=5, max_repeats=50, max_errors=50, poll=0.02)
    assert run(supervise(_runner(busy), emitter(evs), brigade="x", limits=lim))[0] is None
    assert next(e for e in evs if e["type"] == "watchdog")["reason"] == "timeout"

    async def failing(cb):
        while True:
            await cb({"type": "tool_result", "name": "t", "ok": False, "summary": "falló"})
            await asyncio.sleep(0.005)

    evs = []
    assert run(supervise(_runner(failing), emitter(evs), brigade="x", limits=FAST))[0] is None
    assert next(e for e in evs if e["type"] == "watchdog")["reason"] == "errors"


def test_reporta_sin_cortar_cuando_el_jefe_ya_perdio_al_efimero():
    async def script(cb):
        await cb({"type": "delegation", "helper": "investigacion-scout"})
        await cb({"type": "helper_result", "helper": "investigacion-scout", "ok": False,
                  "errors": ["El efímero investigacion-scout no terminó en 900s y se lo cortó."]})
        await cb({"type": "report", "report": {}})
        return "R"

    evs = []
    assert run(supervise(_runner(script), emitter(evs), brigade="investigacion", limits=FAST)) == ("R", "")
    [wd] = [e for e in evs if e["type"] == "watchdog"]
    assert wd["action"] == "reported" and wd["reason"] == "timeout" and wd["target"] == "efímero investigacion-scout"


def test_una_excepcion_de_la_corrida_se_propaga_y_apagado_no_vigila():
    async def boom(cb):
        raise RuntimeError("modelo apagado")

    try:
        run(supervise(_runner(boom), emitter([]), brigade="x", limits=FAST))
        raise AssertionError("tenía que propagarse")
    except RuntimeError as exc:
        assert "modelo apagado" in str(exc)

    async def loop(cb):
        for _ in range(10):
            await cb({"type": "tool", "name": "a", "args": "igual"})
        return "ok"

    assert run(supervise(_runner(loop), emitter([]), brigade="x", limits=FAST, enabled=False)) == ("ok", "")


def test_si_se_cancela_el_turno_no_queda_la_corrida_huerfana():
    cancelled = []

    async def script(cb):
        await asyncio.sleep(60)

    async def main():
        t = asyncio.create_task(supervise(_runner(script, cancelled), emitter([]), brigade="x",
                                          limits=Limits(60, 60, 4, 5, 0.02)))
        await asyncio.sleep(0.1)
        t.cancel()
        await asyncio.gather(t, return_exceptions=True)
        await asyncio.sleep(0.05)

    run(main())
    assert cancelled == [True]


def test_el_registro_de_intervenciones_queda_acotado():
    from raphael_orchestrator.watchdog import Intervention

    log = Log(Store().space("_orchestrator"), keep=3)
    for i in range(7):
        log.add(Intervention(float(i), "b", "jefe", "loop", "cut", f"d{i}"))
    assert [r["detail"] for r in log.recent()] == ["d6", "d5", "d4"]


# --- con el runtime de verdad ------------------------------------------------------------------------------------------------
def test_con_el_harness_el_watchdog_corta_al_efimero_en_loop_audita_y_marca_el_tablero(monkeypatch):
    import time

    import kit

    from raphael_orchestrator.turn import run_brigade

    def slow_search(query: str) -> dict:   # como una búsqueda real: tarda; así el tope de pasos del efímero no gana
        time.sleep(0.05)
        return kit.RESULTS

    monkeypatch.setattr(kit, "search", slow_search)
    loop = [msg(calls=[call("search_osint", {"query": "rust"}, cid=f"c{i}")]) for i in range(40)]
    script = Script(helper=loop)
    rt = kit.runtime(script, watch=WatchSpec(max_repeats=3, stall_seconds=5))
    cfg = config_from({"watchdog": {"poll_seconds": 0.01}})
    ctx = OrchestratorContext(rt)
    evs = []
    turn = run(run_brigade(ctx, "osint", "buscá en la web rust", emitter(evs), cfg))
    assert turn.via == "watchdog" and "El watchdog cortó al efímero osint-web por loop" in turn.text
    final = evs[-1]
    assert final["type"] == "final" and final["literal"] is True and final["origin"] == "watchdog"
    assert any(e["what"] == "watchdog" and e["who"] == "orquestador" for e in rt.audit.entries())
    assert any(e["what"] == "corte_orquestador" for e in rt.audit.entries())
    assert not script.of("voice")                  # el aviso no pasa por la voz
