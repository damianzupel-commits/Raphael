"""Utilería de los tests: la instalación de Damián (harness v2 + brigada Operaciones montada por el cargador desde su
manifest.yaml), con reloj controlable, carpeta segura temporal y adaptadores simulados."""

from __future__ import annotations

import json
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"   # donde está manifest.yaml


class Script:
    """Transporte falso del modelo: anota cada pedido (url y cuerpo) y contesta del guion.

    `helper` contesta a los efímeros (pedidos con tools) y `chief` al jefe. Una Exception en el guion = el modelo falla."""

    def __init__(self, helper=(), chief=()):
        self.helper, self.chief, self.calls = list(helper), list(chief), []

    def __call__(self, url, body, headers):
        self.calls.append({"url": url, "body": body})
        queue = self.helper if "tools" in body else self.chief
        r = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else {"summary": "ok", "confidence": "low"})
        if isinstance(r, Exception):
            raise r
        if isinstance(r, dict) and "choices" in r:
            return r
        return msg(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))


def msg(content="", calls=None):
    return {"choices": [{"message": {"content": content, "tool_calls": calls or []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


LOCAL = {"base_url": "http://127.0.0.1:11434/v1", "model": "chico"}
CLOUD = {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"}


def gateway(transport, *, local: bool = True, cloud: bool = True):
    """Una pasarela con un modelo en la nube y, si `local`, uno local en el escalón `local` (como pide la config)."""
    providers = {**({"casa": LOCAL} if local else {}), **({"nube": CLOUD} if cloud else {})}
    cfg = {"providers": providers,
           "tiers": {"pago": ["nube"] if cloud else [], "gratis": [], "local": ["casa"] if local else []},
           "roles": {r: ["pago", "local"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
           "private": ["operaciones"]}
    return ModelGateway(models_from(cfg), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"},
                        transport=transport)


class System:
    """Operaciones montada, con atajos sync para los tests."""

    def __init__(self, config: dict | None = None, *, transport=None, models: ModelGateway | None = None,
                 edition: str = "personal", sandbox: Path | None = None):
        cfg = {"carpeta_segura": str(sandbox) if sandbox else None, **(config or {})}
        cfg = {k: v for k, v in cfg.items() if v is not None}
        inst = installation_from({"id": "pc", "edition": edition, "identity": {"assistant": "Raphael", "user": "Damian"},
                                  "brigades": {"operaciones": {"active": True, "config": cfg}}})
        self.clock = Clock()
        self.transport = transport
        gw = models if models is not None else (gateway(transport) if transport is not None else None)
        self.rt = Runtime(inst, clock=self.clock, models=gw)
        self.loader = Loader(self.rt, [BRIGADE_DIR.parent], installed=False)
        self.report = self.rt.run(self.loader.apply())

    @property
    def ops(self):
        from raphael_operaciones.registry import peek
        return peek(self.rt.context("operaciones", "pc"))

    def pending(self):
        return self.rt.approvals.list()

    def run(self, coro):
        return self.rt.run(coro)

    def approve(self, pid, changes=None):
        return self.rt.run(self.rt.approve(pid, changes) if changes else self.rt.approve(pid))
