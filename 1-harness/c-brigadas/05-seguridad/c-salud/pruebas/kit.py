"""Utilería: la brigada montada de verdad por el cargador (harness v2), con reloj controlable, sin red y sin claves."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raphael_core import Loader, Message, Runtime, Trust
from raphael_core.installation import installation_from
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"   # donde está manifest.yaml
B = "seguridad"


class System:
    def __init__(self, config: dict | None = None, *, edition: str = "personal", clock: Clock | None = None) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 25, 10, 0))
        inst = {"id": "seg-test", "edition": edition, "identity": {"user": "Damian"},
                "brigades": {B: {"active": True, "config": config or {}}}, "trust": {"enabled": True}}
        self.rt = Runtime(installation_from(inst), clock=self.clock)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "Damian"):
        return self.rt.run(self.rt.command(B, cook, name, data, who=who))

    def pending(self, kind: str | None = None) -> list[dict]:
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int) -> dict:
        return self.rt.run(self.rt.approve(pid, None, who="Damian"))

    def ctx(self, cid: str):
        return self.rt.context(B, cid)

    def publish(self, event: str, data: dict) -> None:
        self.rt.run(self.rt.bus.apublish(event, data, source="servidor/test"))

    def events(self, name: str) -> list[dict]:
        return [d for e, d in self.rt.bus.history if e == name]

    def tick(self) -> None:
        self.rt.run(self.rt.tick(None))

    def tell(self, cook: str, text: str, trust: Trust):
        c = self.rt.brigades[B].cooks[cook]
        return c.handle(Message("panel", "x", text, trust=trust), self.ctx(cook))
