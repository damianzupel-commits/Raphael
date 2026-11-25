"""Utilería de los tests: la brigada montada de verdad (harness v2, cargador, manifest.yaml) con reloj controlable, sin red,
con el buscador simulado y sin claves."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_investigacion.config import investigacion_config
from raphael_investigacion.env import Env
from raphael_investigacion.service import Investigacion

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"


def make_env(config: dict | None = None, *, ask=None, http_get=None, environ: dict | None = None, now: datetime | None = None,
             events: list | None = None) -> Env:
    """Un Env suelto (sin runtime) para probar los módulos."""
    clock = {"now": now or datetime(2026, 11, 25, 10, 0)}
    store = Store(":memory:", clock=lambda: clock["now"])
    env = Env(space=store.space("investigacion"), config=investigacion_config({"search": {"providers": ["mock"]}, **(config or {})}),
              now=lambda: clock["now"], ask=ask, http_get=http_get, environ=environ if environ is not None else {},
              publish=(lambda name, data: events.append((name, data))) if events is not None else None)
    env.clock = clock  # type: ignore[attr-defined]
    return env


def make_inv(config: dict | None = None, **kw) -> Investigacion:
    return Investigacion(make_env(config, **kw))


def mounted(config: dict | None = None, edition: str = "personal", transport=None):
    """La brigada montada por el cargador, de punta a punta. Devuelve (runtime, clock)."""
    from raphael_core.models import ModelGateway, Usage, models_from
    clock = Clock(datetime(2026, 11, 25, 10, 0))
    inst = {"id": "damian-test", "edition": edition, "identity": {"user": "Damian"},
            "brigades": {"investigacion": {"active": True, "config": {"search": {"providers": ["mock"]}, **(config or {})}}}}
    models = None
    if transport is not None:
        models = ModelGateway(models_from({
            "providers": {"loc": {"base_url": "http://localhost:11434/v1", "model": "m"}},
            "tiers": {"pago": [], "gratis": [], "local": ["loc"]},
            "roles": {r: ["local"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
            "error_cooldown_seconds": 0}), Usage(Store().space("_uso"), 1000, clock), transport=transport, edition=edition)
    rt = Runtime(installation_from(inst), clock=clock, models=models)
    loader = Loader(rt, [BRIGADE_DIR], installed=False)
    report = rt.run(loader.apply())
    assert not report["errors"], report["errors"]
    return rt, clock
