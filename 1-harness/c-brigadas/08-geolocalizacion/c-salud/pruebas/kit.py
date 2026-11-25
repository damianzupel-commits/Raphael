"""Utilería de los tests: el harness v2 real con esta brigada montada por el cargador desde su manifest.yaml.

Sin red: la config pone `modo: simulado` (datos de muestra) o los tests inyectan un transporte falso."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"   # donde está manifest.yaml
ID = "geolocalizacion"
C = "prueba:dami"


class System:
    def __init__(self, config: dict | None = None, *, autonomy: dict | None = None) -> None:
        self.clock = Clock(datetime(2026, 11, 25, 10, 0))
        inst = {"id": "damian-test", "edition": "personal", "identity": {"user": "Damian"},
                "brigades": {ID: {"active": True, "config": {"modo": "simulado", **(config or {})}}},
                "autonomy": autonomy or {}}
        self.rt = Runtime(installation_from(inst), clock=self.clock)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def chat(self, text: str, sender: str = "dami") -> list[str]:
        return self.rt.run(self.rt.receive("prueba", sender, text))

    def pending(self) -> list[dict]:
        return self.rt.approvals.list()

    def approve(self, pid, changes=None) -> dict:
        return self.rt.run(self.rt.approve(pid, changes, who="Damian"))

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "orquestador"):
        return self.rt.run(self.rt.command(ID, cook, name, data, who=who))

    def pins(self) -> list[dict]:
        return self.rt.store.space(ID).list("pines")
