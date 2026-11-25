"""Arranque de Raphael personal: harness + orquestador maestro + las brigadas instaladas + cerebro mixto.

    rt, report = start("personal.installation.yaml", ".data/personal")

No abre puertos: eso es del servidor. No importa ninguna brigada ni el orquestador: el cargador del harness los busca por
`manifest.yaml` (carpetas de desarrollo o paquetes instalados) y el orquestador sale del `entry` de la instalación.
Las brigadas listadas en la instalación que todavía no existen quedan en `report["pending"]`, no como error.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from raphael_core import Loader, Runtime
from raphael_core.installation import load_installation
from raphael_core.loader import discover
from raphael_core.models import ModelGateway, Usage
from raphael_core.store import Store

from . import cerebro

DB_FILE = "raphael.sqlite"
ROOT = Path(__file__).resolve().parents[6]


def local_clock(timezone: str) -> Callable[[], datetime]:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
    except Exception:  # noqa: BLE001 - Windows sin tzdata: la hora de la máquina
        return datetime.now
    return lambda: datetime.now(tz).replace(tzinfo=None)


def dev_dirs_default(root: Path = ROOT) -> list[Path]:
    """Las carpetas `b-codigo` de cada brigada y del orquestador del repo (donde estén sus manifiestos)."""
    base = root / "1-harness" / "c-brigadas"
    return sorted(p for p in base.glob("*/b-codigo") if p.is_dir()) if base.is_dir() else []


def start(installation_path: str | Path, data_dir: str | Path, *, dev_dirs: Iterable[str | Path] | None = None,
          models_path: str | Path | None = None, environ: Mapping[str, str] | None = None, installed: bool = True,
          clock: Callable[[], datetime] | None = None, connectors: dict[str, Any] | None = None) -> tuple[Runtime, dict]:
    """(runtime, reporte). El reporte: `mounted`, `errors`, `warnings` del cargador y `pending` (brigadas de la instalación
    que no están en el repo todavía)."""
    environ = os.environ if environ is None else environ
    inst = load_installation(installation_path)
    data = Path(data_dir)
    data.mkdir(parents=True, exist_ok=True)
    clock = clock or local_clock(inst.timezone)
    store = Store(str(data / DB_FILE), clock=clock)
    cfg = cerebro.load(models_path, environ)
    gw = ModelGateway(cfg, Usage(store.space("_uso"), inst.limits.messages_month, clock), plan=inst.plan, edition=inst.edition,
                      env=dict(environ))
    rt = Runtime(inst, store=store, clock=clock, models=gw, connectors=connectors)
    dirs = list(dev_dirs) if dev_dirs is not None else dev_dirs_default()
    found, _ = discover(dirs, installed=installed)
    pending = sorted(b for b, t in inst.brigades.items() if t.active and b not in found)
    for b in pending:                     # no existe todavía: no es un error del arranque
        inst.brigades[b].active = False
    loader = Loader(rt, dirs, installed=installed, installation_path=installation_path)
    report = Runtime.run(loader.apply())
    report["pending"] = pending
    report["unlisted"] = sorted(b for b in found if b not in inst.brigades and b != "orquestador")
    return rt, report
