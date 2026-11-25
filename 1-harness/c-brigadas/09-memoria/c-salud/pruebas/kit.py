"""Utilería de los tests: una instalación de verdad (harness v2 + brigada Memoria montada por el cargador desde su
manifest.yaml), con reloj controlable, vault en una carpeta temporal y sin red.

Los embeddings son los simulados (`provider: mock`) salvo que el test pida otra cosa. El modelo es un transporte falso
que contesta con lo que le pasen: el modelo «local» es un proveedor en localhost, como lo será LM Studio u Ollama.
"""

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


def answers(items, seen: list | None = None):
    """Transporte falso del modelo: devuelve las respuestas en orden (una Exception = el modelo falla)."""
    it = iter(items)

    def transport(url, body, headers):
        if seen is not None:
            seen.append({"url": url, "messages": body["messages"]})
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return {"choices": [{"message": {"content": a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
    return transport


def gateway(transport, clock, *, local: bool = True, private: tuple[str, ...] = ("memoria",)):
    """`local=True`: el único modelo corre en localhost (LM Studio). `local=False`: solo hay uno en la nube."""
    url = "http://localhost:1234/v1" if local else "https://nube.example/v1"
    cfg = {"providers": {"x": {"base_url": url, "model": "m"}},
           "tiers": {"pago": [], "gratis": [] if local else ["x"], "local": ["x"] if local else []},
           "roles": {r: ["local", "gratis"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
           "overrides": {"cocinero.memoria": ["local"]} if local else {}, "private": list(private),
           "error_cooldown_seconds": 0}
    return ModelGateway(models_from(cfg), Usage(Store().space("_uso"), 1000, clock), transport=transport)


class System:
    """La instalación armada, con atajos sync para los tests."""

    def __init__(self, tmp: Path, config: dict | None = None, *, transport=None, local: bool = True, clock: Clock | None = None,
                 edition: str = "personal", autonomy: dict | None = None, private: tuple[str, ...] = ("memoria",)) -> None:
        self.clock = clock or Clock(datetime(2026, 11, 25, 10, 0))
        self.vault = tmp / "vault"
        cfg: dict[str, Any] = {"vault": {"path": str(self.vault)}, "embeddings": {"provider": "mock"}}
        for k, v in (config or {}).items():
            cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
        inst = {"id": "damian-test", "edition": edition, "identity": {"user": "Damián"},
                "brigades": {"memoria": {"active": True, "config": cfg}}, "autonomy": autonomy or {},
                "trust": {"enabled": True}, "limits": {"messages_month": 3000}}
        models = gateway(transport, self.clock, local=local, private=private) if transport is not None else None
        self.rt = Runtime(installation_from(inst), clock=self.clock, models=models)
        self.loader = Loader(self.rt, [BRIGADE_DIR], installed=False)
        self.report = self.rt.run(self.loader.apply())
        assert not self.report["errors"], self.report["errors"]

    def cmd(self, cook: str, name: str, data: dict | None = None, who: str = "Damián"):
        return self.rt.run(self.rt.command("memoria", cook, name, data, who=who))

    def tick(self, now: datetime | None = None) -> None:
        self.rt.run(self.rt.tick(now))

    def publish(self, event: str, data: dict) -> None:
        self.rt.run(self.rt.bus.apublish(event, data, source="otra/brigada"))

    def pending(self, kind: str | None = None) -> list[dict]:
        return [p for p in self.rt.approvals.list() if kind is None or (p.get("action") or {}).get("type") == kind]

    def approve(self, pid: int, changes: dict | None = None) -> dict:
        return self.rt.run(self.rt.approve(pid, changes, who="Damián"))

    def reject(self, pid: int, reason: str = "") -> dict:
        return self.rt.run(self.rt.reject(pid, reason, who="Damián"))

    def cook(self, cid: str):
        return self.rt.brigades["memoria"].cooks[cid]

    def space(self):
        return self.rt.store.space("memoria")

    def save(self, title: str, content: str, **kw) -> dict:
        data = {"title": title, "content": content, **kw}
        return self.cmd("consolidador", "guardar", data)
