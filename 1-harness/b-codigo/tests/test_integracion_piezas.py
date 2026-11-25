"""Pedidos de las piezas 00, 11 y 13 al harness (integración del 25 nov 2026).

- `OrchestratorContext.publish`: el orquestador publica `memoria.turno` y nada más.
- Auditoría de tools con argumentos (sin secretos) y `conv_id`, y `OrchestratorContext.audit_entries` para leerla.
- `Context.action_level`: el nivel que rige hoy una acción de la brigada.
"""

from __future__ import annotations

import pytest
from test_engine_runtime import armar
from test_orchestrator_api import shop_runtime

from raphael_core import ActionError
from raphael_core.context import ORCHESTRATOR_EVENTS, OrchestratorContext
from raphael_core.contract import Level
from raphael_core.runtime import _conversation


def test_el_orquestador_publica_memoria_turno_y_queda_auditado():
    rt = shop_runtime()
    visto = []
    rt.bus.subscribe("memoria.turno", lambda ev, data: visto.append((ev, data)), "memoria")
    OrchestratorContext(rt).publish("memoria.turno", {"conv_id": "app", "history": []})
    assert visto == [("memoria.turno", {"conv_id": "app", "history": [], "_from": "orquestador"})]
    [e] = rt.audit.entries(what="evento", who="orquestador")
    assert e["evento"] == "memoria.turno"


@pytest.mark.parametrize("evento", ["pendiente.aprobado", "brigada.reporte", "malware.detectado", "*"])
def test_el_orquestador_no_puede_publicar_otros_eventos(evento):
    rt = shop_runtime()
    visto = []
    rt.bus.subscribe(evento, lambda ev, data: visto.append(ev), "espia")
    with pytest.raises(ActionError, match="solo puede publicar"):
        OrchestratorContext(rt).publish(evento, {})
    assert visto == [] and ORCHESTRATOR_EVENTS == {"memoria.turno"}


def test_la_auditoria_de_una_tool_guarda_argumentos_sin_secretos_y_la_charla():
    rt, _ = armar(models=False)
    token = _conversation.set("app-celular")
    try:
        rt.run(rt._tool_gate("osint")(rt.tools.get("search"), {"query": "rust", "api_key": "k-123456789"}))
    finally:
        _conversation.reset(token)
    [e] = rt.audit.entries(what="tool")
    assert e["tool"] == "search" and e["conv_id"] == "app-celular"
    assert e["arguments"]["query"] == "rust" and "k-123456789" not in str(e)


def test_una_tool_aprobada_o_fallida_tambien_deja_argumentos_y_charla():
    rt, _ = armar(models=False)
    token = _conversation.set("voz")
    try:
        rt.run(rt._tool_gate("osint")(rt.tools.get("send_mail"), {"to": "a@b.c", "body": "hola"}))   # queda pendiente
    finally:
        _conversation.reset(token)
    [p] = rt.approvals.list()
    assert p["data"]["conv_id"] == "voz"
    rt.run(rt.approve(p["id"], who="Damián"))
    [e] = rt.audit.entries(what="tool")
    assert e["tool"] == "send_mail" and e["conv_id"] == "voz" and e["arguments"]["to"] == "a@b.c"


def test_el_orquestador_lee_la_auditoria_pero_no_la_puede_editar():
    rt, _ = armar(models=False)
    rt.run(rt._tool_gate("osint")(rt.tools.get("search"), {"query": "rust"}))
    ctx = OrchestratorContext(rt)
    out = ctx.audit_entries(what="tool")
    assert [e["tool"] for e in out] == ["search"]
    out[0]["tool"] = "otra"
    out.clear()
    assert [e["tool"] for e in ctx.audit_entries(what="tool")] == ["search"]    # eran copias
    assert ctx.audit_entries(what="tool", last=1) and ctx.audit_entries(what="no-existe") == []


def test_un_cocinero_ve_el_nivel_vigente_de_su_accion():
    rt = shop_runtime()
    ctx = rt.context("tienda", "vendedor")
    assert ctx.action_level("regalar") in (Level.AUTO, Level.APPROVAL, Level.HUMAN)
    assert ctx.action_level("regalar") is rt.policy.level("tienda", "regalar")
