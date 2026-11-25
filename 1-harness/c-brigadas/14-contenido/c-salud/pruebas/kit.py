"""Utilería de los tests: la brigada montada por el cargador desde su manifest.yaml, en modo simulado (sin red, sin ffmpeg, sin GPU)."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from raphael_core import Action, Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"
BID = "contenido"


def merge(base: dict, extra: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class System:
    def __init__(self, tmp: Path, config: dict | None = None, *, edition: str = "personal", autonomy: dict | None = None,
                 transport=None) -> None:
        self.tmp = tmp
        self.clock = Clock(datetime(2026, 11, 25, 10, 0))
        cfg = merge({"mode": "mock", "video": {"dir": str(tmp / "Videos")},
                     "brand": {"name": "Taller Ejemplo", "tone": "voseo_emojis", "topics": ["vestidos", "telas"], "hashtags": ["moda"]}}, config)
        inst = {"id": "t", "edition": edition, "identity": {"user": "Ana"}, "brigades": {BID: {"active": True, "config": cfg}},
                "autonomy": autonomy or {}, "trust": {"enabled": True}}
        self.rt = Runtime(installation_from(inst), clock=self.clock)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def cook(self, cid: str):
        return self.rt.brigades[BID].cooks[cid]

    def act(self, cook: str, type_: str, data: dict | None = None, summary: str = ""):
        return self.rt.run(self.rt.action(BID, cook, Action(type_, data or {}, summary)))

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "Ana"):
        return self.rt.run(self.rt.command(BID, cook, name, data, who=who))

    def pending(self, kind: str | None = None):
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int):
        return self.rt.run(self.rt.approve(pid, None, who="Ana"))

    def reject(self, pid: int, why: str = ""):
        return self.rt.run(self.rt.reject(pid, why, who="Ana"))

    def drain(self, *cooks: str) -> None:
        for c in cooks or ("video", "instagram", "imagen"):
            assert self.cook(c).jobs.join(20)

    def tick(self) -> None:
        self.rt.run(self.rt.tick())

    def events(self, name: str | None = None):
        return [(e, d) for e, d in self.rt.bus.history if name is None or e == name]

    def space(self):
        return self.rt.store.space(self.rt.space_of(BID))
