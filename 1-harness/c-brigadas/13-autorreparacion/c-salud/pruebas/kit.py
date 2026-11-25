"""Utilería de los tests: la instalación personal (harness v2 + esta brigada montada por el cargador desde su
manifest.yaml), con reloj controlable, sin red y con una carpeta de proyecto de juguete para reparar."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"   # donde está manifest.yaml
B = "autorreparacion"

BUGGY = "def total(items):\n    return sum(items) + 1\n\n\ndef name():\n    return 'raphael'\n"
FIX = {"file": "app/calc.py", "old_snippet": "    return sum(items) + 1\n", "new_snippet": "    return sum(items)\n",
       "rationale": "el total sumaba 1 de más"}


def make_project(root: Path, *, git: bool = False) -> Path:
    """Un proyecto de juguete: un archivo común y varios intocables."""
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "app" / "calc.py").write_text(BUGGY, encoding="utf-8")
    (root / "app" / "auth.py").write_text("SECRET_CHECK = True\n", encoding="utf-8")
    (root / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    if git:
        for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                    ["add", "."], ["commit", "-qm", "inicio"]):
            subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)
    return root


def answers(items):
    """Transporte falso del modelo: devuelve las respuestas en orden (una Exception = el modelo falla)."""
    it = iter(items)

    def transport(url, body, headers):
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


PY_OK = [sys.executable, "-c", "import sys; sys.exit(0)"]
PY_FAIL = [sys.executable, "-c", "import sys; print('rompió'); sys.exit(1)"]


class System:
    """La instalación armada, con atajos sync para los tests."""

    def __init__(self, root: Path | None, config: dict | None = None, *, transport=None, autonomy: dict | None = None,
                 trust: dict | None = None, clock: Clock | None = None) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 25, 10, 0))
        cfg = {**({"root": str(root)} if root else {}), "git_commit": False, **(config or {})}
        inst: dict[str, Any] = {"id": "pc-test", "edition": "personal", "identity": {"user": "Damian"},
                                "brigades": {B: {"active": True, "config": cfg}}, "autonomy": autonomy or {},
                                "trust": trust or {"enabled": True}}
        models = gateway(transport, self.clock) if transport is not None else None
        self.rt = Runtime(installation_from(inst), clock=self.clock, models=models)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "Damian"):
        return self.rt.run(self.rt.command(B, cook, name, data, who=who))

    def pending(self) -> list[dict]:
        return self.rt.approvals.list()

    def approve(self, pid: int, changes: dict | None = None) -> dict:
        return self.rt.run(self.rt.approve(pid, changes, who="Damian"))

    def reject(self, pid: int, reason: str = "") -> dict:
        return self.rt.run(self.rt.reject(pid, reason, who="Damian"))

    def tick(self, now: datetime | None = None) -> None:
        self.rt.run(self.rt.tick(now))

    def ctx(self, cid: str):
        return self.rt.context(B, cid)

    def events(self, name: str | None = None) -> list[tuple[str, dict]]:
        return [(e, d) for e, d in self.rt.bus.history if name is None or e == name]

    def proposal(self, pid: str) -> dict:
        return self.ctx("proponer").shared.get("proposals", pid)
