"""H7 (decisiones de Damián del 22 nov 2026):
  1. jefe sin tope de turno; caído tras 5 errores seguidos (un reporte degradado no cuenta); vuelve a mano o al re-montar;
  2. el orquestador solo corre comandos declarados de lectura; uno no declarado lo corre la persona, con aviso;
  3. healthcheck al montar y cada 5 min; 3 malos seguidos -> la brigada deja de recibir; vuelve sola al dar bien;
  4. `setup` del manifiesto registra las tools sin `entry`; una no declarada se acepta con aviso y pide aprobación
     (en la nube se rechaza)."""

from __future__ import annotations

import textwrap
from datetime import timedelta

import pytest
from test_loader import EJEMPLOS, brigade, runtime

from raphael_core import Loader
from raphael_core.context import OrchestratorContext
from raphael_core.contract import ActionError, Health, Level
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.runtime import CHIEF_MAX_FAILURES, Runtime
from raphael_core.testing import Clock
from raphael_core.testing.contract import run_contract_suite


def _saludo(active=("saludo",), edition="personal"):
    rt = runtime(active=active, edition=edition)
    rep = rt.run(Loader(rt, [EJEMPLOS], installed=False).apply())
    return rt, rep


# --- 1. jefe caído -------------------------------------------------------------------------------------------------------
def _boom_chief(rt, brigade="saludo", fail=True):
    calls = []

    async def run(request, on_event=None, context=""):
        calls.append(request)
        if fail:
            raise RuntimeError("se rompió el jefe")
        return await original(request, on_event=on_event, context=context)

    chief = rt.brigades[brigade].chief
    original = chief.run
    chief.run = run
    return calls


def test_el_jefe_queda_caido_tras_5_errores_seguidos_y_no_corre_mas():
    rt, _ = _saludo()
    calls = _boom_chief(rt)
    for i in range(CHIEF_MAX_FAILURES):
        rep = rt.run(rt.ask("saludo", f"pedido {i}"))
        assert rep.degraded and "el jefe falló" in rep.summary
    assert CHIEF_MAX_FAILURES == 5 and len(calls) == 5
    rep = rt.run(rt.ask("saludo", "uno más"))
    assert len(calls) == 5 and "el jefe está caído" in rep.summary and "revivilo" in rep.summary
    st = rt.status()["brigades"]["saludo"]
    assert st["chief_down"].startswith("5 errores seguidos") and st["chief_failures"] == 5
    assert any(e["who"] == "saludo/jefe" for e in rt.audit.entries("pieza_caida"))
    assert any(ev == "brigada.jefe_caido" for ev, _ in rt.bus.history)
    assert rt.is_down("saludo") is False          # tiene cocinero: sigue recibiendo mensajes


def test_un_exito_resetea_el_contador_y_un_reporte_degradado_no_cuenta():
    rt, _ = _saludo()
    m = rt.brigades["saludo"]
    calls = _boom_chief(rt)
    for _ in range(4):
        rt.run(rt.ask("saludo", "x"))
    assert m.chief_failures == 4
    del m.chief.run                                      # vuelve el run real del jefe
    for _ in range(6):                                   # sin modelo: reportes degradados, pero el jefe no revienta
        assert rt.run(rt.ask("saludo", "¿qué hay en la agenda?")).degraded
    assert m.chief_failures == 0 and m.chief_down is None and len(calls) == 4


def test_vuelve_a_mano_o_al_re_montar():
    rt, _ = _saludo()
    _boom_chief(rt)
    for _ in range(5):
        rt.run(rt.ask("saludo", "x"))
    rt.revive_chief("saludo")
    assert rt.brigades["saludo"].chief_down is None and rt.audit.entries("pieza_revivida")
    with pytest.raises(ActionError):
        rt.revive_chief("no-montada")
    _boom_chief(rt)
    for _ in range(5):
        rt.run(rt.ask("saludo", "x"))
    ld = Loader(rt, [EJEMPLOS], installed=False)
    rt.run(rt.unmount("saludo"))
    rt.run(ld.mount("saludo"))
    assert rt.brigades["saludo"].chief_down is None and rt.brigades["saludo"].chief_failures == 0


def test_una_brigada_que_solo_tiene_jefe_figura_caida_si_su_jefe_cae(tmp_path):
    from test_engine_runtime import MANIFEST, SPEC, TOOLS
    rt = Runtime(installation_from({"id": "t", "edition": "personal"}), clock=Clock())
    rt.run(rt.mount(manifest_from(MANIFEST), chief=SPEC, tools=TOOLS))
    _boom_chief(rt, "osint")
    for _ in range(5):
        rt.run(rt.ask("osint", "web: x"))
    assert rt.is_down("osint") is True
    rt.revive_chief("osint")
    assert rt.is_down("osint") is False


# --- 2. comandos ---------------------------------------------------------------------------------------------------------
def test_el_orquestador_solo_corre_comandos_declarados_de_lectura():
    rt, _ = _saludo()
    rt.run(rt.receive("prueba", "ana", "hola", name="Ana"))
    orq = OrchestratorContext(rt)
    assert rt.run(orq.query("saludo", "saludador", "visitas")) == {"prueba:ana": 1}
    assert rt.run(orq.query("saludo", "saludador", "olvidar", {"contact": "prueba:ana"})) is None    # escribe
    assert rt.run(orq.query("saludo", "saludador", "inventado")) is None                             # no declarado
    blocked = [e["comando"] for e in rt.audit.entries("comando_bloqueado")]
    assert blocked == ["olvidar", "inventado"]
    assert rt.run(orq.query("saludo", "saludador", "visitas")) == {"prueba:ana": 1}   # nada se borró
    with pytest.raises(ActionError, match="no es de lectura"):
        rt.run(rt.command("saludo", "saludador", "olvidar", {}, who="orquestador"))


def test_la_persona_corre_los_de_escritura_y_los_no_declarados_con_aviso():
    rt, _ = _saludo()
    rt.run(rt.receive("prueba", "ana", "hola", name="Ana"))
    assert rt.run(rt.command("saludo", "saludador", "olvidar", {"contact": "prueba:ana"}, who="Damián")) is True
    assert rt.run(rt.command("saludo", "saludador", "visitas", who="Damián")) == {}
    with pytest.raises(ActionError, match="no tiene el comando"):        # no declarado: corre (y el cocinero no lo tiene)
        rt.run(rt.command("saludo", "saludador", "magia", who="Damián"))
    assert "saludo: el comando 'magia' no está declarado en el manifiesto" in rt.warnings
    assert [e["comando"] for e in rt.audit.entries("comando_no_declarado")] == ["magia"]


def test_comandos_con_nombre_invalido_no_validan():
    with pytest.raises(ValueError, match="comando inválidos"):
        manifest_from({"id": "x", "name": "x", "version": "1.0.0", "contract": "^2.0",
                       "cooks": [{"id": "c", "entry": "m:C"}], "commands": {"Borrar Todo": {}}})


# --- 3. salud ------------------------------------------------------------------------------------------------------------

def _health_brigade(tmp_path, async_fn=False):
    code = textwrap.dedent(f"""
        from raphael_core import Cook, Health, Reply
        STATE = {{"ok": True, "boom": False, "calls": 0}}
        class One(Cook):
            def interest(self, msg, ctx): return 0.9
            def handle(self, msg, ctx): return Reply("uno")
        {"async " if async_fn else ""}def check(ctx):
            STATE["calls"] += 1
            if STATE["boom"]:
                raise ConnectionError("no hay base")
            return Health(STATE["ok"], "anda" if STATE["ok"] else "la base no responde")
    """)
    pkg = brigade(tmp_path, "sana", manifest={"health": "PKG:check"}, code=code)
    import importlib
    import sys
    sys.path.insert(0, str(tmp_path / "sana"))
    return importlib.import_module(pkg).STATE


@pytest.mark.parametrize("async_fn", [False, True])
def test_salud_al_montar_y_cada_5_minutos_3_malas_seguidas_la_bajan_y_vuelve_sola(tmp_path, async_fn):
    state = _health_brigade(tmp_path, async_fn)
    rt = runtime(active=["sana"])
    clock = rt.clock
    rt.run(Loader(rt, [tmp_path], installed=False).apply())
    m = rt.brigades["sana"]
    assert state["calls"] == 1 and m.health["ok"] is True                 # al montar
    state["ok"] = False
    clock.now += timedelta(minutes=1)
    rt.run(rt.tick())
    assert state["calls"] == 1                                             # todavía no pasaron 5 min
    for i in range(1, 3):
        clock.now += timedelta(minutes=5)
        rt.run(rt.tick())
        assert m.health["fails"] == i and m.health["down"] is False
    rt.run(rt.receive("prueba", "x", "hola"))
    assert rt.outgoing()[-1]["text"] == "uno"                              # con 2 malas sigue recibiendo
    clock.now += timedelta(minutes=5)
    state["boom"] = True
    rt.run(rt.tick())
    assert m.health["down"] is True and "no hay base" in m.health["detail"] and rt.is_down("sana")
    rt.run(rt.receive("prueba", "y", "hola"))
    assert rt.outgoing()[-1]["text"].startswith("¡Gracias por escribir!")  # ya no recibe: queda para una persona
    assert any(p["action"]["type"] == "responder_duda" for p in rt.approvals.list())
    assert rt.status()["brigades"]["sana"]["health"]["down"] is True
    state.update(ok=True, boom=False)
    clock.now += timedelta(minutes=5)
    rt.run(rt.tick())
    assert m.health == {**m.health, "ok": True, "fails": 0, "down": False} and rt.audit.entries("brigada_sana")
    rt.run(rt.receive("prueba", "z", "hola"))
    assert rt.outgoing()[-1]["text"] == "uno"


def test_una_brigada_caida_por_salud_no_le_corre_el_jefe():
    rt, _ = _saludo()
    m = rt.brigades["saludo"]
    m.health_fn = lambda ctx: Health(False, "sin agenda")
    for _ in range(3):
        rt.run(rt.check_health("saludo"))
    calls = _boom_chief(rt, fail=False)
    rep = rt.run(rt.ask("saludo", "¿qué hay hoy?"))
    assert calls == [] and "chequeo de salud" in rep.summary and "sin agenda" in rep.summary


def test_la_suite_marca_una_brigada_que_nace_enferma(tmp_path):
    state = _health_brigade(tmp_path)
    state["ok"] = False
    r = run_contract_suite(tmp_path / "sana")
    assert {c.name for c in r.failed()} == {"salud"} and "la base no responde" in r.failed()[0].detail
    state["ok"] = True


# --- 4. setup ------------------------------------------------------------------------------------------------------------
def test_setup_registra_la_tool_declarada_sin_entry_con_su_nivel():
    rt, rep = _saludo()
    t = rt.tools.get("contar_visitas")
    assert t is not None and t.owner == "saludo" and t.spec is not None and t.level is Level.AUTO
    rt.run(rt.receive("prueba", "ana", "hola", name="Ana"))
    assert t.fn() == {"prueba:ana": 1}                                    # ve los mismos datos que el cocinero
    assert not [w for w in rep["warnings"] if "contar_visitas" in w]


SETUP_CODE = """
    from raphael_core import Cook
    class One(Cook): pass
    def setup(ctx):
        ctx.register_tool("declarada", lambda q="": {{"q": q}})
        {extra}
"""


def _setup_brigade(tmp_path, extra="", tools=None):
    tools = tools if tools is not None else [{"name": "declarada", "level": "aprobacion"}]
    brigade(tmp_path, "setupeada", manifest={"setup": "PKG:setup", "tools": tools},
            code=SETUP_CODE.format(extra=extra))


def test_una_tool_no_declarada_se_acepta_con_aviso_y_pide_aprobacion_en_cada_uso(tmp_path):
    _setup_brigade(tmp_path, extra='ctx.register_tool("extra", lambda: {"ok": True})')
    rt = runtime(active=["setupeada"])
    rep = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert rep["mounted"] == ["setupeada"]
    assert any("'extra' no está declarada" in w for w in rep["warnings"])
    assert rt.tools.get("extra").spec is None and rt.tools.get("declarada").level is Level.APPROVAL
    assert rt.policy.decide("setupeada", "tool_extra").level is Level.APPROVAL       # no declarada = aprobación
    r = run_contract_suite(tmp_path / "setupeada")
    assert r.ok and "tools no declaradas" in next(c.detail for c in r.checks if c.name == "comandos y tools declarados")


def test_en_la_nube_una_tool_no_declarada_se_rechaza(tmp_path):
    _setup_brigade(tmp_path, extra='ctx.register_tool("extra", lambda: {"ok": True})')
    rt = runtime(active=["setupeada"], edition="cloud")
    rep = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert rep["mounted"] == ["setupeada"] and rt.tools.get("extra") is None
    assert any("en la nube se rechaza" in w for w in rep["warnings"])


@pytest.mark.parametrize("extra,fragment", [
    ('raise RuntimeError("sin credenciales")', "su setup falló: RuntimeError: sin credenciales"),
    ('ctx.register_tool("Mal Nombre", print)', "tool inválida"),
])
def test_si_setup_falla_la_brigada_no_se_monta_ni_deja_nada(tmp_path, extra, fragment):
    _setup_brigade(tmp_path, extra=extra)
    rt = runtime(active=["setupeada"])
    rep = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert fragment in rep["errors"]["setupeada"]
    assert rt.brigades == {} and rt.tools.names() == []


def test_setup_no_puede_pisar_una_tool_que_ya_tiene_entry(tmp_path):
    brigade(tmp_path, "doble", manifest={"setup": "PKG:setup", "tools": [{"name": "t", "entry": "PKG:t"}]},
            code="from raphael_core import Cook\nclass One(Cook): pass\ndef t(): return 1\n"
                 "def setup(ctx): ctx.register_tool('t', t)\n")
    rt = runtime(active=["doble"])
    assert "ya se carga por su entry" in rt.run(Loader(rt, [tmp_path], installed=False).apply())["errors"]["doble"]


def test_una_tool_declarada_sin_entry_que_nadie_registra_queda_avisada(tmp_path):
    _setup_brigade(tmp_path, tools=[{"name": "declarada"}, {"name": "olvidada"}])
    rt = runtime(active=["setupeada"])
    rep = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert any("tools declaradas que nadie cargó: olvidada" in w for w in rep["warnings"])
    r = run_contract_suite(tmp_path / "setupeada")
    assert {c.name: c.detail for c in r.failed()} == {"setup registra sus tools": "faltan: olvidada"}
