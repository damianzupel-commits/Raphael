"""Utilería de los tests: un runtime de raphael-core con brigadas de verdad (jefe + efímeros) y un modelo falso, sin red."""

from __future__ import annotations

import json

from raphael_core import Runtime
from raphael_core.context import OwnerContext
from raphael_core.engine import BrigadeSpec, HelperSpec, RouteRule, Routing, WatchSpec
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock
from raphael_core.tools import Tool

# Señales equivalentes a las reglas fijas de JarvisRemote (routing.py), pasadas al formato del manifiesto 2.1. Son las
# que les quedan como pendiente a las piezas 07 (investigación) y 09 (memoria · cerebro) para su manifest.yaml.
CEREBRO_ROUTING = {"safe_default": True, "signals": [
    {"pattern": r"que se de|que sabes de|que sabemos|que tengo (?:sobre|de|guardado)|mis notas|mi vault|en el vault|"
                r"\bcerebro\b", "weight": 2},
    {"pattern": r"\bvault\b|memoria|\bnotas?\b|recorda|conclusion|conecta|asocia|segun mis|lo que guarde|\banote\b|apunt|"
                r"te acordas|decidimos|aprendiste|repasame|que hablamos", "weight": 1}]}
INVESTIGACION_ROUTING = {"signals": [
    {"pattern": r"en la web|en internet|\binternet\b|\bonline\b|en linea|\bgoogle|arxiv|https?://", "weight": 2},
    {"pattern": r"(?<!en )(?<!en que )(?<!en ese )(?<!en todo )(?<!en cualquier )\bcasos?\b(?! de que)|evidencia|forens|"
                r"\bexif\b|whatsapp|telegram|\bcsv\b|artefactos?|\.(?:pdf|docx|jpe?g|png|log)\b", "weight": 2},
    {"pattern": r"\binvestig|\bresearch\b|\bscout\b|noticias|novedades|ultimas? |ultimos? |se publico|estado del arte|"
                r"\bfusion(?:es)?\b|entidades", "weight": 1}]}
VIDEO_ROUTING = {"direct_only": True, "signals": [{"pattern": r"\bvideo", "weight": 2}]}


def catalog_entry(bid: str, routing: dict, *, name: str = "", chief: bool = True, mounted: bool = True,
                  down: bool = False, purpose: str = "") -> dict:
    return {"id": bid, "name": name or bid.title(), "description": purpose, "chief_purpose": purpose, "mounted": mounted,
            "chief": chief, "down": down, "down_reason": "su chequeo de salud dio mal" if down else None,
            "routing": routing, "actions": {}, "private": False}


JR_CATALOG = [catalog_entry("memoria-cerebro", CEREBRO_ROUTING, name="Cerebro", purpose="lo que ya está en tus notas"),
              catalog_entry("investigacion", INVESTIGACION_ROUTING, name="Investigación", purpose="web y casos"),
              catalog_entry("video", VIDEO_ROUTING, name="Video", purpose="edición de video")]


# --- modelo falso ----------------------------------------------------------------------------------------------------------
def msg(content="", calls=None):
    return {"choices": [{"message": {"content": content, "tool_calls": calls or []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Script:
    """Transporte falso por rol: el jefe ("JEFE"), los efímeros ("EFIMERO"/con tools), la voz y el ruteo tienen cada uno
    su guion. Una lista con un solo elemento se repite. Guarda todos los cuerpos que recibió."""

    def __init__(self, *, helper=None, chief=None, voice=None, routing=None):
        self.queues = {"helper": list(helper or [msg("listo")]), "chief": list(chief or [{"summary": "ok",
                                                                                          "confidence": "low"}]),
                       "voice": list(voice or [None]), "routing": list(routing or [None])}
        self.bodies: list[dict] = []

    def kind(self, body):
        first = body["messages"][0]["content"]
        if "tools" in body or first.startswith("EFIMERO"):
            return "helper"
        if "LA VOZ DEL ORQUESTADOR" in first or "SOLO charla social" in first:
            return "voice"
        if "Clasificá el pedido" in first or "qué área lo atiende" in first:
            return "routing"
        return "chief"

    def __call__(self, url, body, headers):
        self.bodies.append(body)
        q = self.queues[self.kind(body)]
        r = q.pop(0) if len(q) > 1 else q[0]
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise RuntimeError("sin respuesta en el guion")
        if isinstance(r, dict) and "choices" in r:
            return r
        return msg(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))

    def of(self, kind):
        return [b for b in self.bodies if self.kind(b) == kind]


MODELS = {
    "providers": {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"}},
    "tiers": {"pago": [], "gratis": ["nube"], "local": []},
    "roles": {r: ["gratis"] for r in ("mando", "voz", "ruteo", "jefe", "efimero")},
}

RESULTS = {"results": [{"url": "https://ejemplo.org/a", "title": "Página A", "snippet": "Rust 2.0 salió el 3 de marzo"}]}


def search(query: str) -> dict:
    return RESULTS


def spec(bid="osint", *, private=False, watch=None, helper_timeout=None):
    return BrigadeSpec(
        id=bid, name=bid.title(), purpose=f"buscar para {bid}", prompt=f"JEFE-{bid}",
        helpers=(HelperSpec(mode="web", id=f"{bid}-web", description="sale a la web", prompt="EFIMERO web",
                            tools=frozenset({f"search_{bid}"})),),
        routing=Routing(rules=(RouteRule("web", r"\bweb\b"),), default="web"), private=private,
        watch=watch, helper_timeout=helper_timeout)


def manifest(bid="osint", routing=None, description=""):
    return manifest_from({"id": bid, "name": bid.title(), "version": "1.0.0", "contract": ">=2.1,<3",
                          "description": description or f"brigada {bid}", "chief": f"{bid}.spec:SPEC",
                          "tools": [{"name": f"search_{bid}", "level": "automatico"}],
                          "routing": routing or {}})


def runtime(script: Script | None = None, *, brigades=("osint",), private=(), user="Damián", models=True,
            routing=None, watch=None, edition="personal", tools=None):
    inst = installation_from({"id": "pc", "edition": edition, "identity": {"user": user}})
    gw = None
    if models:
        gw = ModelGateway(models_from(MODELS), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"},
                          edition=edition, transport=script or Script())
    rt = Runtime(inst, clock=Clock(), models=gw)
    for b in brigades:
        rt.run(rt.mount(manifest(b, (routing or {}).get(b)), chief=spec(b, private=b in private, watch=watch),
                        tools=[Tool(f"search_{b}", (tools or {}).get(b, search),
                                    parameters={"type": "object", "properties": {"query": {"type": "string"}}})]))
    return rt


def owner(rt, events=None, session="app"):
    async def feed(ev):
        if events is not None:
            events.append(ev)

    return OwnerContext(rt, rt.installation.identity.user or "dueña", session=session, channel="app", on_event=feed)


def emitter(events):
    async def emit(ev):
        events.append(ev)

    return emit


__all__ = ["WatchSpec"]
