"""Utilería de los tests: la instalación de la clienta de verdad (harness v2 + orquestador `secretary` + esta brigada,
montada por el cargador desde su manifest.yaml), con reloj controlable y sin red."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_empresas.sample import MINIMAL, PILOT

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"   # donde está manifest.yaml
ORCH = "raphael_orchestrator.orchestrator:RaphaelOrchestrator"
W = ("whatsapp", "549341")


def merge(base: dict, extra: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def answers(items, seen: list | None = None):
    """Transporte falso del modelo: devuelve las respuestas en orden (una Exception = el modelo falla)."""
    it = iter(items)

    def transport(url, body, headers):
        if seen is not None:
            seen.append(body["messages"][0]["content"])
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return {"choices": [{"message": {"content": a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
    return transport


def gateway(transport, clock):
    return ModelGateway(models_from({"providers": {"x": {"base_url": "https://ia.example/v1", "model": "m"}},
                                     "tiers": {"pago": [], "gratis": ["x"], "local": []},
                                     "roles": {r: ["gratis"] for r in ("mando", "voz", "ruteo", "jefe", "efimero")},
                                     "error_cooldown_seconds": 0}),
                        Usage(Store().space("_uso"), 1000, clock), transport=transport)


class System:
    """La instalación armada, con atajos sync para los tests."""

    def __init__(self, config: dict | None = None, *, pilot: bool = False, clock: Clock | None = None, transport=None,
                 orchestrator: bool = True, edition: str = "cloud", user: str = "Ana", autonomy: dict | None = None,
                 trust: dict | None = None, limits: dict | None = None, classifier: bool = False,
                 orch_config: dict | None = None) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 18, 10, 0))
        cfg = merge(PILOT if pilot else MINIMAL, config)
        inst: dict[str, Any] = {"id": "clienta-test", "edition": edition, "identity": {"user": user},
                                "brigades": {"empresas": {"active": True, "config": cfg}},
                                "autonomy": autonomy or {}, "trust": trust or {"enabled": True},
                                "limits": limits or {"messages_month": 3000}}
        if orchestrator:
            inst["orchestrator"] = {"entry": ORCH, "config": merge(
                {"mode": "secretary", "routing": {"fallback_cook": "empresas/atencion", "classifier": classifier}},
                orch_config)}
        models = gateway(transport, self.clock) if transport is not None else None
        self.rt = Runtime(installation_from(inst), clock=self.clock, models=models)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    # --- clientes
    def receive(self, text: str, channel: str = W[0], sender: str = W[1], name: str = "", attachment: bool = False):
        return self.rt.run(self.rt.receive(channel, sender, text, name, attachment))

    def chat(self, *texts: str, **kw) -> list[str]:
        out: list[str] = []
        for t in texts:
            out = self.receive(t, **kw)
        return out

    def out(self, contact: str | None = None) -> list[str]:
        return [x["text"] for x in self.rt.outgoing(contact)]

    # --- la dueña
    def pending(self, kind: str | None = None) -> list[dict]:
        ps = self.rt.approvals.list()
        return [p for p in ps if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int, changes: dict | None = None) -> dict:
        return self.rt.run(self.rt.approve(pid, changes, who="Ana"))

    def reject(self, pid: int, reason: str = "") -> dict:
        return self.rt.run(self.rt.reject(pid, reason, who="Ana"))

    def resolve(self, pid: int, reply: str | None = None) -> dict:
        return self.rt.run(self.rt.resolve(pid, reply, who="Ana"))

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "Ana"):
        return self.rt.run(self.rt.command("empresas", cook, name, data, who=who))

    def say(self, text: str, session: str = "app"):
        return self.rt.run(self.rt.talk_to_owner(text, session=session))

    def tick(self, now: datetime | None = None) -> None:
        self.rt.run(self.rt.tick(now))

    def publish(self, event: str, data: dict) -> None:
        """Un evento como si lo publicara otro cocinero de la brigada (para probar un cocinero solo)."""
        self.rt.run(self.rt.bus.apublish(event, data, source="empresas/test"))

    def cook(self, cid: str):
        return self.rt.brigades["empresas"].cooks[cid]

    def ctx(self, cid: str):
        return self.rt.context("empresas", cid)

    def events(self, name: str | None = None) -> list[tuple[str, dict]]:
        return [(e, d) for e, d in self.rt.bus.history if name is None or e == name]
