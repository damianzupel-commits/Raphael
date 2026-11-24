"""El turno simple de punta a punta sobre el harness real: puerta de O2 (parte 3).

Portado de la sección 6 de JarvisRemote `tests/test_flujo_decidido.py` (turno completo, todos fallan, memoria entre
turnos y brigadas) y de lo que resolvía `server.py` (charla, autoconocimiento, errores). El único `final` es del
orquestador; lo de código (errores, watchdog) sale literal.
"""

from __future__ import annotations

import asyncio

from kit import Script, call, emitter, msg, owner, runtime
from raphael_core.context import OrchestratorContext

from raphael_orchestrator import config_from
from raphael_orchestrator.routing import Route
from raphael_orchestrator.turn import conversation_of, decide, run_brigade, run_chat, run_route, run_self

CFG = config_from({"watchdog": {"poll_seconds": 0.01}, "routing": {"classifier": False}})
FAITHFUL = "Rust 2.0 salió el 3 de marzo, según Página A."


def run(coro):
    return asyncio.run(coro)


def good_script(voice=FAITHFUL):
    return Script(helper=[msg(calls=[call("search_osint", {"query": "rust"})]), msg("Rust 2.0 salió el 3 de marzo (Página A).")],
                  chief=[{"summary": "Rust 2.0 salió el 3 de marzo.", "confidence": "high",
                          "findings": [{"text": "Salió el 3 de marzo.", "helper": "osint-web", "sources": ["Página A"]}]}],
                  voice=[voice])


def test_turno_completo_efimero_jefe_orquestador_persona():
    script = good_script()
    rt = runtime(script)
    evs = []
    t = run(run_brigade(owner(rt), "osint", "buscá en la web cuándo salió Rust 2.0", emitter(evs), CFG))
    assert t.via == "llm" and t.text == FAITHFUL and t.fidelity["ok"] and t.report.brigade == "osint"
    types = [e["type"] for e in evs]
    assert {"delegation", "tool", "helper_result", "report", "communicating", "final"} <= set(types)
    finals = [e for e in evs if e["type"] == "final"]
    assert len(finals) == 1 and finals[0]["origin"] == "orchestrator" and finals[0]["reply"] == FAITHFUL
    assert finals[0]["fidelity"]["ok"] and "chief" in finals[0]["timings"] and "voice" in finals[0]["timings"]
    voice_body = script.of("voice")[0]
    assert "REPORTE INTERNO DEL JEFE" in voice_body["messages"][1]["content"] and "Damián" in voice_body["messages"][0]["content"]


def test_si_la_voz_no_es_fiel_sale_la_plantilla_y_nunca_un_texto_del_jefe():
    rt = runtime(good_script(voice="Rust 3.0 salió ayer, me dijeron."))
    t = run(run_brigade(owner(rt), "osint", "buscá en la web Rust", emitter([]), CFG))
    assert t.via == "template" and "Rust 2.0 salió el 3 de marzo" in t.text and t.fidelity["ok"]


def test_sin_modelos_el_jefe_degrada_y_el_orquestador_igual_comunica_fiel():
    rt = runtime(models=False)
    t = run(run_brigade(owner(rt), "osint", "buscá en la web Rust", emitter([]), CFG))
    assert t.via == "template" and t.report.degraded and "no pudo sintetizar" in t.text and t.fidelity["ok"]


def test_lo_de_una_brigada_privada_no_sale_a_la_voz_en_la_nube():
    script = good_script()
    rt = runtime(script, private=("osint",))
    t = run(run_brigade(owner(rt), "osint", "buscá en mis cosas", emitter([]), CFG))
    assert t.via == "template" and script.of("voice") == []        # sin modelo local: plantilla, nada a la nube
    assert all(not b.get("tools") for b in script.of("voice"))


def test_un_pendiente_real_llega_a_la_persona_con_su_numero():
    script = Script(helper=[msg(calls=[call("search_osint", {"query": "x"})]), msg("listo")],
                    chief=[{"summary": "Busqué y quedó una propuesta.", "confidence": "medium"}], voice=[None])
    rt = runtime(script)
    rt.policy.declare("osint", "tool_search_osint", __import__("raphael_core.manifest", fromlist=["ActionSpec"]).ActionSpec(
        level="aprobacion"))
    t = run(run_brigade(owner(rt), "osint", "buscá en la web x", emitter([]), CFG))
    [p] = rt.approvals.list()
    assert f"#{p['id']}" in t.text and "pendiente de tu aprobación" in t.text


def test_el_orquestador_recuerda_la_charla_por_sesion_y_no_se_la_pasa_al_jefe():
    script = good_script(voice=FAITHFUL)
    rt = runtime(script)
    run(run_brigade(owner(rt, session="app"), "osint", "¿qué salió de Rust?", emitter([]), CFG))
    run(run_brigade(owner(rt, session="app"), "osint", "¿y después?", emitter([]), CFG))
    second_voice = script.of("voice")[1]["messages"][1]["content"]
    assert "CONVERSACIÓN PREVIA" in second_voice and "¿qué salió de Rust?" in second_voice
    assert "CONVERSACIÓN PREVIA" not in script.of("voice")[0]["messages"][1]["content"]
    assert all(FAITHFUL not in m["content"] for b in script.of("helper") + script.of("chief") for m in b["messages"])
    ctx = OrchestratorContext(rt)
    assert len(conversation_of(ctx, CFG).turns("app")) == 2 and conversation_of(ctx, CFG).turns("whatsapp") == []


def test_sin_memoria_no_se_guarda_nada():
    rt = runtime(good_script())
    cfg = config_from({"memory": {"enabled": False}, "watchdog": {"poll_seconds": 0.01}})
    run(run_brigade(owner(rt), "osint", "x en la web", emitter([]), cfg))
    assert conversation_of(OrchestratorContext(rt), cfg).turns("app") == []


def test_charla_y_autoconocimiento_los_contesta_el_orquestador():
    script = Script(voice=["¡Hola, Damián! ¿Qué necesitás?", None])
    rt = runtime(script)
    evs = []
    t = run(run_chat(owner(rt), "hola", emitter(evs), CFG))
    assert t.via == "llm" and t.text.startswith("¡Hola") and evs[-1]["brigade"] == "orquestador"
    assert script.of("chief") == [] and script.of("helper") == []
    evs = []
    t = run(run_self(owner(rt), "¿qué brigadas tenés?", emitter(evs), CFG))
    assert t.report.brigade == "orquestador" and "Osint" in t.text and evs[0]["type"] == "report"


def test_las_decisiones_sin_brigada_salen_literales():
    rt = runtime(Script())
    evs = []
    t = run(run_route(owner(rt), Route("missing", "override", "la brigada 'x' no existe", "hola", brigade="x"),
                      emitter(evs), CFG))
    assert t.via == "literal" and "no existe" in t.text and evs[-1]["literal"] is True
    t = run(run_route(owner(rt), Route("none", "default", "sin señales", "hola"), emitter([]), CFG))
    assert "No tengo una brigada" in t.text
    t = run(run_brigade(owner(rt), "nada", "x", emitter([]), CFG))
    assert t.via == "literal" and "No pude mandarle el pedido" in t.text


def test_de_punta_a_punta_ruteo_y_turno_con_el_harness():
    script = good_script()
    rt = runtime(script, routing={"osint": {"safe_default": True, "signals": [{"pattern": "en la web", "weight": 2}]}})
    ctx = owner(rt)
    evs = []
    r = run(decide(ctx, "buscá en la web cuándo salió Rust 2.0", CFG))
    t = run(run_route(ctx, r, emitter(evs), CFG))
    assert evs[0]["type"] == "route" and evs[0]["brigade"] == "osint" and t.text == FAITHFUL
    r = run(decide(ctx, "hola", CFG))
    assert r.kind == "chat"
