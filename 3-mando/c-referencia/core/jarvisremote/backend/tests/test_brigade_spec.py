"""Tests del esquema declarativo de brigadas (brigades/spec.py) y del motor genérico (brigades/engine.py).
Sin LLM ni red: los ayudantes se fakean y el LLM del jefe no existe (conftest), así que el plan sale de las reglas y la
síntesis se DEGRADA de forma explícita. El flujo con LLM (plan, paralelismo, síntesis) está en test_flujo_decidido.py."""

from __future__ import annotations

import asyncio

import pytest

from brigades import chief as chief_mod
from brigades.chief import ChiefConfig
from brigades.engine import GenericChief
from brigades.spec import AyudanteSpec, BrigadeSpec, Criterion, RouteRule, Routing, StepSpec, ValidationSpec


def _ayudante(modo: str, tools=frozenset({"t_" + "x"})) -> AyudanteSpec:
    return AyudanteSpec(
        modo=modo, id=f"b-{modo}", descripcion=modo, donde="local",
        config=lambda: ChiefConfig(id=f"b-{modo}", name=modo, tool_names=frozenset(tools), system_prompt="p", persistent=False),
        client_model=lambda: (None, f"modelo-{modo}"),
        tool_names=lambda: frozenset(tools),
    )


def _spec(**kw) -> BrigadeSpec:
    base = dict(
        id="demo", name="Demo", purpose="probar", prompt="sos demo",
        ayudantes=(_ayudante("a", {"t1"}), _ayudante("b", {"t2"})),
        routing=Routing(reglas=(RouteRule("a", r"\bfoo\b"), RouteRule("b", r"\bbar\b")), default="b"),
    )
    base.update(kw)
    return BrigadeSpec(**base)


# --- esquema ------------------------------------------------------------------
def test_ruteo_primera_regla_gana_y_default():
    r = _spec().routing
    assert r.clasificar("hay FOO y bar") == "a"  # orden = prioridad
    assert r.clasificar("solo bar") == "b"
    assert r.clasificar("nada") == "b"  # default
    assert r.clasificar("") == "b"


def test_techo_de_tools_es_la_union_de_los_ayudantes():
    assert _spec().tool_names() == frozenset({"t1", "t2"})
    assert _spec(tools=frozenset({"solo"})).tool_names() == frozenset({"solo"})


def test_chief_config_sale_del_spec():
    cfg = _spec().chief_config()
    assert (cfg.id, cfg.name, cfg.persistent) == ("demo", "Demo", True)
    assert cfg.system_prompt == "sos demo"


def test_spec_invalido_se_rechaza():
    with pytest.raises(ValueError):
        BrigadeSpec(id="x", name="x", purpose="x", prompt="x", ayudantes=(_ayudante("a"),))  # sin ruteo
    with pytest.raises(ValueError):
        _spec(routing=Routing(reglas=(RouteRule("zzz", "x"),), default="a"))  # modo sin ayudante
    with pytest.raises(ValueError):
        _spec(client="nube")
    with pytest.raises(ValueError, match="al menos un ayudante"):  # no existe la brigada "directa" (decisión 2026-11-16)
        BrigadeSpec(id="d", name="D", purpose="p", prompt="p", tools=frozenset({"t"}))


def test_scene_hash_depende_solo_de_la_escena():
    def vs(scene, facts=None):
        return ValidationSpec(title="t", scene=scene, steps=(StepSpec("s", "S", "m:f"),), criterion=Criterion("c"),
                              baseline_keys=(), facts=facts or {})

    a = vs({"x": ["1"], "y": "2"})
    assert a.scene_hash == vs({"x": ["1"], "y": "2"}, facts={"otro": 1}).scene_hash  # facts no entra al hash
    assert a.scene_hash != vs({"x": ["1"], "y": "3"}).scene_hash


def test_describe_skills_es_una_por_ayudante():
    skills = _spec().describe_skills()
    assert {s["modo"] for s in skills} == {"a", "b"} and all(s["efimero"] for s in skills)


def test_coincidencias_devuelve_todos_los_modos_que_matchean_en_orden_de_prioridad():
    r = _spec().routing
    assert r.coincidencias("hay bar y también FOO") == ("a", "b")  # el orden lo fijan las reglas, no el texto
    assert r.coincidencias("solo bar") == ("b",) and r.coincidencias("nada") == ()


# --- motor --------------------------------------------------------------------
class _FakeHelper:
    def __init__(self, tag):
        self.tag = tag

    async def run(self, message, on_event=None):
        await on_event({"type": "start", "topic": message})
        await on_event({"type": "final", "reply": f"ok-{self.tag}"})
        return f"ok-{self.tag}", []


def _chief(monkeypatch, tmp_path, **kw) -> GenericChief:
    monkeypatch.setattr(chief_mod, "_STATE_DIR", tmp_path)
    spec = _spec(**kw)
    jefe = GenericChief.from_spec(spec, client=None, model="x")
    jefe._spawn = lambda modo: _FakeHelper(modo)
    return jefe


def test_el_motor_delega_segun_el_ruteo_y_cierra_el_feed(monkeypatch, tmp_path):
    jefe = _chief(monkeypatch, tmp_path)
    events: list[dict] = []

    async def on_event(ev):
        events.append(ev)

    reply, _ = asyncio.run(jefe.run("hacé foo", on_event=on_event))
    tipos = [e["type"] for e in events]
    assert tipos == ["start", "plan", "delegacion", "tool", "resultado_ayudante", "sintesis", "reporte"]
    assert {"type": "tool", "name": "delegar:b-a", "args": "modo=a"} in events  # compat: la línea de delegación de siempre
    assert events[1]["via"] == "reglas" and [d["modo"] for d in events[1]["delegaciones"]] == ["a"]
    # el jefe NO emite `final` (eso es del orquestador) ni deja salir el `final` del ayudante: cierra con su REPORTE
    assert "final" not in tipos and events[-1]["reporte"]["brigada"] == "demo"
    rep = events[-1]["reporte"]
    assert rep["sintesis_degradada"] is True and rep["ayudantes"] == [{"id": "b-a", "ok": True, "resumen": "ok-a", "modo": "a",
                                                                         "duracion_s": rep["ayudantes"][0]["duracion_s"]}]
    assert "ok-a" in reply and reply == rep["resumen"]  # `run` devuelve el resumen del reporte, no un mensaje al usuario
    # el feed muestra el pedido, no el contexto
    assert [e for e in events if e["type"] == "start"][0]["topic"] == "hacé foo"


def test_el_jefe_recuerda_que_ayudante_resolvio(monkeypatch, tmp_path):
    jefe = _chief(monkeypatch, tmp_path)
    asyncio.run(jefe.run("hacé foo"))
    memoria = jefe._state_path().read_text(encoding="utf-8")
    assert "hacé foo" in memoria and "[b-a] " in memoria and "ok-a" in memoria  # qué se pidió, quién lo resolvió, la conclusión


def test_timeout_del_ayudante_no_tumba_al_jefe(monkeypatch, tmp_path):
    jefe = _chief(monkeypatch, tmp_path, helper_timeout=lambda: 0.05)

    class Cuelga:
        async def run(self, message, on_event=None):
            await asyncio.sleep(5)

    jefe._spawn = lambda modo: Cuelga()
    events: list[dict] = []

    async def on_event(ev):
        events.append(ev)

    reply, _ = asyncio.run(jefe.run("foo", on_event=on_event))
    rep = events[-1]["reporte"]
    assert "no terminó" in reply and events[-1]["type"] == "reporte"  # el jefe igual sintetiza/reporta: reporta el fallo
    assert rep["fallos"] == [{"ayudante": "b-a", "motivo": "timeout", "detalle": rep["fallos"][0]["detalle"]}]
    res = next(e for e in events if e["type"] == "resultado_ayudante")
    assert res["ok"] is False and "no terminó" in res["errores"][0]  # un resultado VÁLIDO (ok=false), no una excepción
    assert {"type": "tool_result", "name": "delegar:b-a", "ok": False, "summary": res["errores"][0][:200]} in events  # compat


def test_ayudante_que_falla_se_contiene(monkeypatch, tmp_path):
    jefe = _chief(monkeypatch, tmp_path)

    class Roto:
        async def run(self, message, on_event=None):
            raise RuntimeError("boom")

    jefe._spawn = lambda modo: Roto()
    reply, _ = asyncio.run(jefe.run("foo"))
    assert "falló: boom" in reply


def test_el_jefe_tiene_su_modelo_propio_e_informa_el_de_cada_rol(monkeypatch, tmp_path):
    jefe = GenericChief.from_spec(_spec(), client=None, model="m-jefe")
    assert jefe.model == "m-jefe"  # el LLM PROPIO del jefe (antes: "sin LLM propio", listaba los de sus ayudantes)
    roles = jefe.roles()
    assert roles["jefe"]["id"] == "demo" and [a["modo"] for a in roles["ayudantes"]] == ["a", "b"]
    assert jefe._tools is None  # menor privilegio: el jefe no tiene tools de dominio, aunque el techo de la brigada no sea vacío


def test_ensure_tool_modules_importa_los_modulos_declarados(monkeypatch):
    import importlib

    pedidos = []
    monkeypatch.setattr(importlib, "import_module", lambda name: pedidos.append(name))
    _spec(tool_modules=("uno", "dos")).ensure_tool_modules()
    assert pedidos == ["app.tools.uno", "app.tools.dos"]
    pedidos.clear()
    _spec().ensure_tool_modules()  # sin módulos declarados: no importa nada
    assert pedidos == []
