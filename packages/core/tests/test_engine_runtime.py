"""El motor montado en el runtime: pasarela de modelos (transporte falso), caja de tools, compuerta de política,
pendientes de tipo "tool", ediciones y desmontaje. Sin red."""

from __future__ import annotations

import json

import pytest

from raphael_core import MountError, Runtime
from raphael_core.contract import ActionError
from raphael_core.engine import BrigadeSpec, HelperSpec, RouteRule, Routing
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock
from raphael_core.tools import Tool, ToolError, ToolRegistry

MODELS = {
    "providers": {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"},
                  "casa": {"base_url": "http://127.0.0.1:11434/v1", "model": "chico"}},
    "tiers": {"pago": [], "gratis": ["nube"], "local": []},
    "roles": {"jefe": ["gratis"], "efimero": ["gratis"], "mando": ["gratis"]},
}


def _msg(content="", calls=None):
    return {"choices": [{"message": {"content": content, "tool_calls": calls or []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def _call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Script:
    """Transporte falso: el jefe (sin tools en el body) y los efímeros (con tools) tienen cada uno su guion."""

    def __init__(self, helper: list, chief: list):
        self.helper, self.chief, self.bodies = list(helper), list(chief), []

    def __call__(self, url, body, headers):
        self.bodies.append(body)
        queue = self.helper if "tools" in body or body["messages"][0]["content"].startswith("EFIMERO") else self.chief
        r = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, dict) and "choices" in r else _msg(json.dumps(r, ensure_ascii=False))


SPEC = BrigadeSpec(
    id="osint", name="OSINT", purpose="buscar", prompt="JEFE-OSINT",
    helpers=(HelperSpec(mode="web", id="osint-web", description="sale a la web", prompt="EFIMERO web",
                        tools=frozenset({"search", "send_mail"})),
             HelperSpec(mode="notes", id="osint-notes", description="notas", prompt="EFIMERO notas", private=True,
                        tools=frozenset({"read_notes"}))),
    routing=Routing(rules=(RouteRule("web", r"\bweb\b"),), default="notes"))

MANIFEST = {"id": "osint", "name": "OSINT", "version": "1.0.0", "contract": ">=2.0,<3", "chief": "osint.spec:SPEC",
            "tools": [{"name": "search", "level": "automatico", "description": "busca en la web"},
                      {"name": "send_mail", "level": "aprobacion", "tags": ["external"]},
                      {"name": "read_notes", "level": "automatico"},
                      {"name": "nmap", "level": "aprobacion", "active_scan": True}]}

RESULTS = {"results": [{"url": "https://ejemplo.org/a", "title": "Página A", "snippet": "Rust 2.0 salió el 3 de marzo"}]}
SENT: list[dict] = []


def search(query: str) -> dict:
    return RESULTS


def send_mail(to: str, body: str) -> dict:
    SENT.append({"to": to, "body": body})
    return {"status": "sent"}


def read_notes() -> dict:
    return {"results": []}


async def nmap(target: str) -> dict:
    return {"open": []}


TOOLS = [Tool("search", search, parameters={"type": "object", "properties": {"query": {"type": "string"}}}),
         Tool("send_mail", send_mail), Tool("read_notes", read_notes), Tool("nmap", nmap)]


def armar(transport=None, edition="personal", models=True, autonomy=None, spec=SPEC):
    inst = installation_from({"id": "pc", "edition": edition, "identity": {"user": "Damián"}, "autonomy": autonomy or {}})
    gw = None
    if models:
        gw = ModelGateway(models_from(MODELS), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"},
                          edition=edition, transport=transport or Script([_msg("listo")], [{"summary": "ok",
                                                                                            "confidence": "low"}]))
    rt = Runtime(inst, clock=Clock(), models=gw)
    notes = rt.run(rt.mount(manifest_from(MANIFEST), chief=spec, tools=TOOLS))
    return rt, notes


def test_un_pedido_pasa_por_el_jefe_el_efimero_usa_su_tool_y_vuelve_un_reporte_con_la_fuente():
    t = Script(helper=[_msg(calls=[_call("search", {"query": "rust"})]), _msg("Rust 2.0 salió el 3 de marzo (Página A).")],
               chief=[{"summary": "Rust 2.0 salió el 3 de marzo.", "confidence": "high",
                       "findings": [{"text": "Salió el 3 de marzo.", "helper": "osint-web", "sources": ["Página A"]}]}])
    rt, _ = armar(t)
    events = []

    async def on_event(ev):
        events.append(ev)

    rep = rt.run(rt.ask("osint", "buscá en la web cuándo salió Rust 2.0", on_event=on_event))
    assert rep.degraded is False and [s.ref for s in rep.sources] == ["https://ejemplo.org/a"]
    tool_bodies = [b for b in t.bodies if "tools" in b]
    assert [f["function"]["name"] for f in tool_bodies[0]["tools"]] == ["search", "send_mail"]   # solo SU caja
    assert all("tools" not in b for b in t.bodies if b["messages"][0]["content"].startswith("JEFE"))
    assert {"tool", "tool_result", "helper_result", "report"} <= {e["type"] for e in events}
    assert any(e["what"] == "tool" and e.get("data_tool") in (None, "search") for e in rt.audit.entries())
    assert rt.live.snapshot()["recent"][0]["outcome"] == "ok" and rt.status()["brigades"]["osint"]["chief"]
    assert any(ev == "brigada.reporte" for ev, _ in rt.bus.history)


def test_una_tool_con_aprobacion_no_se_ejecuta_queda_pendiente_y_corre_al_aprobar():
    SENT.clear()
    t = Script(helper=[_msg(calls=[_call("send_mail", {"to": "x@y.z", "body": "hola"})]), _msg("Dejé el mail pendiente.")],
               chief=[{"summary": "Quedó un mail pendiente de aprobación.", "confidence": "medium"}])
    rt, _ = armar(t)
    rt.run(rt.ask("osint", "mandá por la web un mail"))
    assert SENT == []
    [p] = rt.approvals.list()
    assert p["kind"] == "tool" and p["data"]["tool"] == "send_mail" and p["level"] == "aprobacion"
    tool_reply = next(m for b in t.bodies for m in b["messages"] if m.get("role") == "tool")
    assert "pending_approval" in tool_reply["content"] and f"#{p['id']}" in tool_reply["content"]
    res = rt.run(rt.approve(p["id"], {"body": "hola, corregido"}))
    assert res["state"] == "executed" and SENT == [{"to": "x@y.z", "body": "hola, corregido"}]
    assert rt.approvals.list() == [] and any(ev == "tool.ejecutada" for ev, _ in rt.bus.history)


def test_rechazar_una_tool_sube_el_nivel_por_confianza():
    t = Script(helper=[_msg(calls=[_call("send_mail", {"to": "a", "body": "b"})]), _msg("pendiente")],
               chief=[{"summary": "pendiente", "confidence": "low"}])
    rt, _ = armar(t)
    rt.run(rt.ask("osint", "web: mandá un mail"))
    [p] = rt.approvals.list()
    rt.run(rt.reject(p["id"], "no"))
    assert rt.policy.level("osint", "tool_send_mail").value == "humano"


def test_la_autonomia_de_la_instalacion_tambien_gobierna_las_tools():
    t = Script(helper=[_msg(calls=[_call("search", {"query": "q"})]), _msg("listo")], chief=[{"summary": "ok",
                                                                                             "confidence": "low"}])
    rt, _ = armar(t, autonomy={"osint.tool_search": {"level": "aprobacion"}})
    rt.run(rt.ask("osint", "web: buscá"))
    assert [p["data"]["tool"] for p in rt.approvals.list()] == ["search"]


def test_pedir_una_tool_fuera_de_la_caja_no_ejecuta_nada_y_vuelve_como_error():
    t = Script(helper=[_msg(calls=[_call("read_notes", {})]), _msg("no pude")], chief=[{"summary": "no pudo",
                                                                                       "confidence": "low"}])
    rt, _ = armar(t)
    rep = rt.run(rt.ask("osint", "web: leé las notas"))
    tool_reply = next(m for b in t.bodies for m in b["messages"] if m.get("role") == "tool")
    assert "no está en la caja" in tool_reply["content"] and any("read_notes" in w for w in rep.warnings)


def test_en_la_nube_no_se_carga_lo_de_escaneo_activo():
    rt, notes = armar(edition="cloud")
    assert rt.tools.get("nmap") is None and any("nmap" in n and "cloud" in n for n in notes)
    with pytest.raises(ToolError, match="nube"):
        reg = ToolRegistry("cloud")
        reg.register(Tool("nmap", nmap, spec=manifest_from(MANIFEST).tools[3]))


def test_un_efimero_privado_sin_modelo_local_falla_explicito_y_el_jefe_igual_reporta():
    rt, _ = armar()
    rep = rt.run(rt.ask("osint", "¿qué dicen mis notas?"))          # cae en `notes` (privado): la nube no le sirve
    assert rep.helpers[0].ok is False and "no hay modelo" in rep.failures[0].detail and rep.degraded is True


def test_sin_pasarela_de_modelos_todo_degrada_sin_romper():
    rt, _ = armar(models=False)
    rep = rt.run(rt.ask("osint", "web: algo"))
    assert rep.degraded is True and rep.failures[0].helper == "osint-web"
    assert rt.status()["brigades"]["osint"]["chief"]["chief"]["model"] == "sin modelo"


def test_una_brigada_solo_con_jefe_no_figura_caida():
    rt, _ = armar()
    assert rt.is_down("osint") is False


def test_montar_exige_coherencia_entre_manifiesto_jefe_y_tools():
    inst = installation_from({"id": "pc", "edition": "personal"})
    rt = Runtime(inst, clock=Clock())
    with pytest.raises(MountError, match="se pasó su BrigadeSpec"):
        rt.run(rt.mount(manifest_from(MANIFEST)))
    with pytest.raises(MountError, match="no está declarada"):
        rt.run(rt.mount(manifest_from(MANIFEST), chief=SPEC, tools=[Tool("otra", search)]))
    spec_otro = BrigadeSpec(id="otro", name="x", purpose="x", prompt="x", helpers=SPEC.helpers, routing=SPEC.routing)
    with pytest.raises(MountError, match="es de 'otro'"):
        rt.run(rt.mount(manifest_from(MANIFEST), chief=spec_otro))
    assert rt.brigades == {} and rt.tools.names() == []


def test_avisa_si_un_efimero_tiene_tools_que_nadie_cargo():
    inst = installation_from({"id": "pc", "edition": "personal"})
    rt = Runtime(inst, clock=Clock())
    notes = rt.run(rt.mount(manifest_from(MANIFEST), chief=SPEC, tools=TOOLS[:1]))
    assert any("osint-web" in n and "send_mail" in n for n in notes)


def test_desmontar_saca_las_tools_y_exporta_la_memoria_del_jefe():
    t = Script(helper=[_msg("listo")], chief=[{"summary": "ok", "confidence": "low"}])
    rt, _ = armar(t)
    rt.run(rt.ask("osint", "web: algo"))
    exported = rt.run(rt.unmount("osint"))
    assert "chief" in exported["osint"] and rt.tools.names() == []
    with pytest.raises(ActionError):
        rt.run(rt.ask("osint", "algo"))


def test_una_tool_que_explota_vuelve_al_modelo_como_error():
    def broken(query: str):
        raise RuntimeError("se cayó la búsqueda")

    t = Script(helper=[_msg(calls=[_call("search", {"query": "q"})]), _msg("no anduvo")],
               chief=[{"summary": "no anduvo", "confidence": "low"}])
    inst = installation_from({"id": "pc", "edition": "personal"})
    gw = ModelGateway(models_from(MODELS), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"}, transport=t)
    rt = Runtime(inst, clock=Clock(), models=gw)
    rt.run(rt.mount(manifest_from(MANIFEST), chief=SPEC, tools=[Tool("search", broken)]))
    rep = rt.run(rt.ask("osint", "web: buscá"))
    assert rep.helpers[0].ok is True and any("osint-web" in w and "se cayó la búsqueda" in w for w in rep.warnings)


def test_la_pasarela_chat_devuelve_tool_calls_y_salta_respuestas_vacias():
    cfg = {**MODELS, "tiers": {"pago": [], "gratis": ["nube", "otra"], "local": []},
           "providers": {**MODELS["providers"], "otra": {"base_url": "https://otra.example/v1", "model": "m"}}}
    seen = []

    def transport(url, body, headers):
        seen.append(url)
        return _msg("") if "nube" in url else _msg(calls=[_call("search", {"query": "x"})])

    gw = ModelGateway(models_from(cfg), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"}, transport=transport)
    out = gw.chat("efimero", [{"role": "user", "content": "hola"}], tools=[{"type": "function"}])
    assert out["tool_calls"][0]["function"]["name"] == "search" and len(seen) == 2
    assert gw.label("efimero").startswith(("nube", "otra"))


def test_la_persona_puede_apagar_una_tool_y_ningun_efimero_la_ve_ni_la_usa():
    t = Script(helper=[_msg(calls=[_call("search", {"query": "q"})]), _msg("no pude buscar")],
               chief=[{"summary": "no pudo", "confidence": "low"}])
    rt, _ = armar(t)
    rt.tools.set_enabled("search", False)
    rt.run(rt.ask("osint", "web: buscá"))
    first = next(b for b in t.bodies if "tools" in b)
    assert [f["function"]["name"] for f in first["tools"]] == ["send_mail"]
    reply = next(m for b in t.bodies for m in b["messages"] if m.get("role") == "tool")
    assert "desactivada" in reply["content"]
    assert [x["enabled"] for x in rt.tools.list() if x["name"] == "search"] == [False]
    with pytest.raises(ToolError):
        rt.tools.set_enabled("no-existe", True)
