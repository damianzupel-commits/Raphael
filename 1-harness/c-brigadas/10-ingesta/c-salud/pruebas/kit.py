"""Utilería de los tests: la brigada montada por el cargador desde su manifest.yaml, con reloj controlable, adaptadores
simulados y sin red."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from raphael_core import Action, Loader, Runtime
from raphael_core.contract import Trust
from raphael_core.installation import installation_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"
MINIMAL = {"modo": "simulado"}
URL_VIDEO = "https://www.youtube.com/watch?v=MOCKVID0001"
URL_LIST = "https://www.youtube.com/playlist?list=PLmock"


def answers(items, seen: list | None = None):
    """Transporte falso del modelo: devuelve las respuestas en orden (una Exception = el modelo falla)."""
    it = iter(items)

    def transport(url, body, headers):
        if seen is not None:
            seen.append(body["messages"])
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return {
            "choices": [{"message": {"content": a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        }

    return transport


def gateway(transport, clock):
    return ModelGateway(
        models_from(
            {
                "providers": {"x": {"base_url": "https://ia.example/v1", "model": "m"}},
                "tiers": {"pago": [], "gratis": ["x"], "local": []},
                "roles": {r: ["gratis"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
                "error_cooldown_seconds": 0,
            }
        ),
        Usage(Store().space("_uso"), 1000, clock),
        transport=transport,
    )


GOOD = {
    "title": "Cómo funcionan los agentes con herramientas",
    "category": "IA",
    "summary": "El video explica cómo un agente planifica y usa herramientas, y por qué las acciones peligrosas "
    "piden aprobación.",
    "key_topics": ["agentes", "herramientas", "aprobación"],
    "relevance": {"verdict": "útil", "score": 5, "reason": "habla de agentes con aprobación humana"},
}


class System:
    def __init__(
        self,
        config: dict | None = None,
        *,
        vault: Path | None = None,
        clock: Clock | None = None,
        transport=None,
        edition: str = "personal",
        autonomy: dict | None = None,
    ) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 25, 10, 0))
        cfg = {**MINIMAL, **({"vault_dir": str(vault)} if vault else {}), **(config or {})}
        inst = {
            "id": "ingesta-test",
            "edition": edition,
            "identity": {"user": "Damian"},
            "brigades": {"ingesta": {"active": True, "config": cfg}},
            "autonomy": autonomy or {},
            "trust": {"enabled": True},
        }
        models = gateway(transport, self.clock) if transport is not None else None
        self.rt = Runtime(installation_from(inst), clock=self.clock, models=models)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def owner(self, text: str) -> list[str]:
        """La persona dueña escribe (canal propio, confiable)."""
        return self.rt.run(self.rt.receive("panel", "damian", text, trust=Trust.TRUSTED))

    def stranger(self, text: str) -> list[str]:
        return self.rt.run(self.rt.receive("whatsapp", "549341", text))

    def cook(self, cid: str):
        return self.rt.brigades["ingesta"].cooks[cid]

    def ctx(self, cid: str):
        return self.rt.context("ingesta", cid)

    def act(self, cid: str, type_: str, data: dict | None = None) -> dict:
        return self.rt.run(self.ctx(cid).arequest(Action(type_, data or {}, summary=type_)))

    def cmd(self, cid: str, name: str, data: dict | None = None, who: str = "Damian"):
        return self.rt.run(self.rt.command("ingesta", cid, name, data, who=who))

    def tick(self) -> None:
        self.rt.run(self.rt.tick(self.clock.now))

    def pending(self, kind: str | None = None) -> list[dict]:
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int) -> dict:
        return self.rt.run(self.rt.approve(pid, None, who="Damian"))

    def notes(self) -> list[dict]:
        return self.ctx("web").shared.list("notas")

    def events(self, name: str) -> list[dict]:
        return [d for e, d in self.rt.bus.history if e == name]
