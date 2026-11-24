"""Trabajo conjunto de punta a punta sobre el harness real: puerta de O3 (parte 2).

Dos brigadas con jefe y efímeros (`notas` y `web`), el mando reparte, el DAG corre por niveles, el mando concluye y la voz
comunica UNA respuesta. Se prueba: paralelo, dependencia (la segunda ve el reporte de la primera como dato), falla
parcial, corte del watchdog en un nodo, presupuesto de tiempo, y que con una brigada privada nada sale a la nube.
"""

from __future__ import annotations

import asyncio
import json
import time

import kit
from kit import call, emitter, msg, owner
from raphael_core.engine import WatchSpec

from raphael_orchestrator import config_from
from raphael_orchestrator.turn import decide, run_route

ROUTING = {"notas": {"safe_default": True, "signals": [{"pattern": r"mis notas", "weight": 2}]},
           "web": {"signals": [{"pattern": r"en la web", "weight": 2}]}}
REQUEST = "Fijate en mis notas qué sé de Rust y buscá en la web cuándo salió Rust 2.0"
SPLIT = {"notas": "Fijate en mis notas qué sé de Rust", "web": "Buscá en la web cuándo salió Rust 2.0"}
SYNTH = {"notas": {"summary": "En tus notas dice que Rust 2.0 salió el 3 de marzo.", "confidence": "high"},
         "web": {"summary": "En la web: Rust 2.0 salió el 3 de marzo.", "confidence": "medium",
                 "findings": [{"text": "Salió el 3 de marzo.", "helper": "web-web", "sources": ["Página A"]}]}}
CONCLUSION = {"conclusion": "Tus notas y la web coinciden: Rust 2.0 salió el 3 de marzo.", "confidence": "medium"}
VOICE = "Tus notas y la web coinciden: Rust 2.0 salió el 3 de marzo, según Página A."


class World:
    """El modelo falso del mundo: responde según quién pregunta (mando, voz, jefe de cada brigada, efímero)."""

    def __init__(self, split=SPLIT, conclusion=CONCLUSION, voice=VOICE, loop_helper=None, broken_chief=None):
        self.split, self.conclusion, self.voice = split, conclusion, voice
        self.loop_helper, self.broken_chief = loop_helper, broken_chief
        self.bodies: list[dict] = []

    def who(self, body):
        first = body["messages"][0]["content"]
        if "REPARTIRLO" in first:
            return "split"
        if "CONCLUIR" in first:
            return "conclude"
        if "LA VOZ DEL ORQUESTADOR" in first:
            return "voice"
        if "tools" in body:
            return "helper:" + body["tools"][0]["function"]["name"].removeprefix("search_")
        for b in ("notas", "web"):
            if f"JEFE-{b}" in first:
                return "chief:" + b
        return "?"

    def __call__(self, url, body, headers):
        self.bodies.append(body)
        w = self.who(body)
        if w == "split":
            return msg(json.dumps(self.split, ensure_ascii=False))
        if w == "conclude":
            return msg(json.dumps(self.conclusion, ensure_ascii=False))
        if w == "voice":
            return msg(self.voice)
        if w.startswith("helper:"):
            b = w.split(":")[1]
            if b == self.loop_helper or not any(m.get("role") == "tool" for m in body["messages"]):
                return msg(calls=[call(f"search_{b}", {"query": "rust"})])
            return msg("Rust 2.0 salió el 3 de marzo (Página A).")
        if w.startswith("chief:"):
            b = w.split(":")[1]
            if b == self.broken_chief:
                raise RuntimeError("el modelo del jefe se cayó")
            return msg(json.dumps(SYNTH[b], ensure_ascii=False))
        raise AssertionError(f"pedido inesperado: {body['messages'][0]['content'][:80]}")

    def of(self, who):
        return [b for b in self.bodies if self.who(b) == who]


CFG = config_from({"watchdog": {"poll_seconds": 0.01}, "routing": {"classifier": False}})


def run(coro):
    return asyncio.run(coro)


def turn(world, cfg=CFG, private=(), **kw):
    rt = kit.runtime(world, brigades=("notas", "web"), routing=ROUTING, private=private, **kw)
    ctx = owner(rt)
    evs = []
    r = run(decide(ctx, REQUEST, cfg))
    t = run(run_route(ctx, r, emitter(evs), cfg))
    return rt, r, t, evs


def test_dos_brigadas_en_paralelo_el_mando_concluye_y_la_voz_comunica_una_sola_respuesta():
    world = World()
    rt, r, t, evs = turn(world)
    assert r.kind == "joint" and set(r.brigades) == {"notas", "web"}
    plan = next(e for e in evs if e["type"] == "plan")
    assert plan["via"] == "model" and plan["levels"] == [["notas", "web"]] and plan["after"] == {}
    assert t.text == VOICE and t.via == "llm" and t.fidelity["ok"]
    assert t.report.summary.startswith("[Conclusión del orquestador] Tus notas y la web coinciden")
    assert "[Notas]" in t.report.summary and "[Web]" in t.report.summary and t.report.confidence == "medium"
    finals = [e for e in evs if e["type"] == "final"]
    assert len(finals) == 1 and finals[0]["brigades"] == ["notas", "web"]
    tagged = {e.get("brigade") for e in evs if e["type"] in ("delegation", "helper_result")}
    assert tagged == {"notas", "web"}                                  # el feed dice de qué brigada es cada evento
    helper_bodies = world.of("helper:web")
    assert all("Rust 2.0" in b["messages"][1]["content"] for b in helper_bodies[:1])   # recibió SU sub-tarea


def test_una_brigada_que_depende_de_otra_arranca_despues_y_ve_su_reporte_como_dato():
    world = World(split={**SPLIT, "after": {"web": ["notas"]}})
    rt, r, t, evs = turn(world)
    plan = next(e for e in evs if e["type"] == "plan")
    assert plan["levels"] == [["notas"], ["web"]] and plan["after"] == {"web": ["notas"]}
    stage = next(e for e in evs if e["type"] == "stage")
    assert stage == {"type": "stage", "brigade": "web", "after": ["notas"]}
    first_web = world.of("helper:web")[0]["messages"][1]["content"]
    assert "En tus notas dice que Rust 2.0" in first_web and "<<<DATO" in first_web
    order = [world.who(b) for b in world.bodies if world.who(b).startswith("chief:")]
    assert order == ["chief:notas", "chief:web"]                      # web sintetiza después de notas
    assert t.text == VOICE


def test_si_una_brigada_falla_las_otras_siguen_y_el_fallo_se_dice():
    world = World(voice="sin cifras ni nada")
    rt = kit.runtime(world, brigades=("notas", "web"), routing=ROUTING)

    async def boom(request, on_event=None, context=""):
        raise RuntimeError("se rompió el jefe de web")

    rt.brigades["web"].chief.run = boom
    ctx = owner(rt)
    t = run(run_route(ctx, run(decide(ctx, REQUEST, CFG)), emitter([]), CFG))
    assert t.via == "template" and t.report.degraded and "[Web]" in t.report.summary and "el jefe falló" in t.report.summary
    assert "[Notas] En tus notas dice que Rust 2.0 salió el 3 de marzo." in t.report.summary
    assert t.fidelity["ok"]


def test_si_el_proveedor_falla_la_pasarela_lo_pausa_para_todos_y_todas_degradan_sin_romper():
    world = World(broken_chief="web", voice="x")
    rt, r, t, evs = turn(world)
    assert t.report.degraded and "[Notas]" in t.report.summary and "[Web]" in t.report.summary and t.fidelity["ok"]


def test_el_watchdog_corta_un_nodo_sin_tumbar_el_turno(monkeypatch):
    def slow_search(query: str) -> dict:
        time.sleep(0.03)
        return kit.RESULTS

    monkeypatch.setattr(kit, "search", slow_search)
    world = World(loop_helper="web", voice="x")
    rt, r, t, evs = turn(world, watch=WatchSpec(max_repeats=3, stall_seconds=5))
    wd = [e for e in evs if e["type"] == "watchdog" and e["action"] == "cut"]
    assert wd and wd[0]["brigade"] == "web" and "loop" in wd[0]["message"]
    assert "cortó" in t.report.summary and "[Notas] En tus notas" in t.report.summary
    assert len([e for e in evs if e["type"] == "final"]) == 1


def test_el_presupuesto_de_tiempo_corta_lo_que_no_termino():
    def very_slow(query: str) -> dict:
        time.sleep(0.6)
        return kit.RESULTS

    world = World(voice="x")
    rt = kit.runtime(world, brigades=("notas", "web"), routing=ROUTING, tools={"web": very_slow})
    cfg = config_from({"watchdog": {"poll_seconds": 0.01}, "routing": {"classifier": False},
                       "joint": {"max_seconds": 0.3}})
    ctx = owner(rt)
    t = run(run_route(ctx, run(decide(ctx, REQUEST, cfg)), emitter([]), cfg))
    assert "se pasó el presupuesto del turno" in t.report.summary and "[Notas] En tus notas" in t.report.summary


def test_con_una_brigada_privada_ni_el_mando_ni_la_voz_salen_a_la_nube():
    world = World()
    rt, r, t, evs = turn(world, private=("notas",))
    assert world.of("split") == [] and world.of("conclude") == [] and world.of("voice") == []
    plan = next(e for e in evs if e["type"] == "plan")
    assert plan["private"] is True and plan["via"] == "request"         # sin modelo local: cada una, el pedido entero
    assert t.via == "template" and "sin conclusión del orquestador" in " ".join(t.report.warnings)


def test_sin_modelo_del_mando_igual_hay_respuesta_fiel():
    world = World(split="nada", conclusion="nada", voice="nada")
    rt, r, t, evs = turn(world)
    assert next(e for e in evs if e["type"] == "plan")["via"] == "request"
    assert t.via == "template" and t.fidelity["ok"] and not t.report.summary.startswith("[Conclusión")


def test_en_modo_secretaria_el_conjunto_esta_apagado_salvo_que_se_prenda():
    world = World()
    rt = kit.runtime(world, brigades=("notas", "web"), routing=ROUTING)
    ctx = owner(rt)
    sec = config_from({"mode": "secretary", "routing": {"classifier": False}})
    assert run(decide(ctx, REQUEST, sec)).kind == "brigade"
    on = config_from({"mode": "secretary", "joint": {"enabled": True}, "routing": {"classifier": False}})
    assert run(decide(ctx, REQUEST, on)).kind == "joint"
    assert run(decide(ctx, REQUEST, config_from({"joint": {"enabled": False}}))).kind == "brigade"
