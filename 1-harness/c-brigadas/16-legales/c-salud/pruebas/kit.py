"""Utilería de los tests: la brigada montada por el cargador desde su manifest.yaml, con reloj controlable, fuentes
simuladas (sin red) y un modelo falso opcional."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"

FULL = {"negocio": {"nombre": "Taller Ejemplo", "cuit": "20-00000000-0", "domicilio": "Calle Falsa 123, Rosario",
                    "email": "hola@ejemplo.test", "telefono": "341 000-0000"},
        "fuentes": {"modo": "mock"}}
MINIMAL = {"fuentes": {"modo": "mock"}}


def answers(items, seen: list | None = None):
    it = iter(items)

    def transport(url, body, headers):
        if seen is not None:
            seen.append([m["content"] for m in body["messages"]])
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return {"choices": [{"message": {"content": a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
    return transport


def gateway(transport, clock):
    return ModelGateway(models_from({"providers": {"x": {"base_url": "https://ia.example/v1", "model": "m"}},
                                     "tiers": {"pago": [], "gratis": ["x"], "local": []},
                                     "roles": {r: ["gratis"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
                                     "error_cooldown_seconds": 0}),
                        Usage(Store().space("_uso"), 1000, clock), transport=transport)


class System:
    def __init__(self, config: dict | None = None, *, clock: Clock | None = None, transport=None,
                 edition: str = "cloud", autonomy: dict | None = None) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 25, 10, 0))
        inst: dict[str, Any] = {"id": "legales-test", "edition": edition, "identity": {"user": "Ana"},
                                "brigades": {"legales": {"active": True, "config": FULL if config is None else config}},
                                "autonomy": autonomy or {}, "trust": {"enabled": True}, "limits": {"messages_month": 3000}}
        models = gateway(transport, self.clock) if transport is not None else None
        self.rt = Runtime(installation_from(inst), clock=self.clock, models=models)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def pending(self, kind: str | None = None) -> list[dict]:
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int, changes: dict | None = None) -> dict:
        return self.rt.run(self.rt.approve(pid, changes, who="Ana"))

    def reject(self, pid: int, reason: str = "") -> dict:
        return self.rt.run(self.rt.reject(pid, reason, who="Ana"))

    def cmd(self, cook: str, name: str, data: dict | None = None):
        return self.rt.run(self.rt.command("legales", cook, name, data, who="Ana"))

    def tick(self, now: datetime | None = None) -> None:
        self.rt.run(self.rt.tick(now))

    def publish(self, event: str, data: dict) -> None:
        self.rt.run(self.rt.bus.apublish(event, data, source="otra/test"))

    def ctx(self, cid: str):
        return self.rt.context("legales", cid)

    def events(self, name: str | None = None) -> list[tuple[str, dict]]:
        return [(e, d) for e, d in self.rt.bus.history if name is None or e == name]
