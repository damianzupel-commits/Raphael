"""Utilería de los tests: Trading montada por el cargador desde su manifest.yaml, con reloj controlable y sin red."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"


class System:
    def __init__(self, config: dict | None = None, *, autonomy: dict | None = None, trust: dict | None = None) -> None:
        self.clock = Clock(datetime(2026, 11, 25, 10, 0))
        inst = {"id": "damian-test", "edition": "personal", "identity": {"user": "Damián"},
                "brigades": {"trading": {"active": True, "config": config or {}}},
                "autonomy": autonomy or {}, "trust": trust or {"enabled": True}}
        self.rt = Runtime(installation_from(inst), clock=self.clock)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def cmd(self, cook: str, name: str, data: dict | None = None):
        return self.rt.run(self.rt.command("trading", cook, name, data, who="Damián"))

    def pending(self, kind: str | None = None) -> list[dict]:
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid, changes: dict | None = None):
        return self.rt.run(self.rt.approve(pid, changes, who="Damián"))

    def reject(self, pid, reason: str = ""):
        return self.rt.run(self.rt.reject(pid, reason, who="Damián"))

    def tick(self) -> None:
        self.rt.run(self.rt.tick(self.clock()))

    def events(self, name: str | None = None) -> list[tuple[str, dict]]:
        return [(e, d) for e, d in self.rt.bus.history if name is None or e == name]


def find_signal_config() -> dict:
    """Config con la que el simulado de USD/JPY (semilla 33) da una señal válida: LONG con R:R 4,19."""
    return {"risk": {"min_conf": 0.0}, "data": {"sim_seed": 33}}
