"""Arranque de una instalación de Raphael Empresas: harness v2 + orquestador (modo `secretary`) + esta brigada.

Es lo que llama el servidor (pieza 03) al levantar: arma el `Runtime` con la base SQLite de la clienta, el cargador
(paquetes instalados y, si se pasan, carpetas de desarrollo), la pasarela de modelos (si hay `modelos.yaml` y claves
en el entorno; sin eso todo sigue por reglas) y deja montado lo que dice la instalación. No abre puertos ni canales:
eso es del servidor.

    from raphael_empresas.boot import start
    rt, report = start("2-entrega/c-despliegue/instalacion-clienta/clienta.installation.yaml", "datos/")
    await rt.receive("whatsapp", "549341...", "hola")         # mensaje de un cliente
    await rt.talk_to_owner("¿qué tareas hay hoy?")            # la dueña

La hora: el VPS corre en UTC; el reloj del runtime usa la zona de la instalación (`timezone`).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from raphael_core import Loader, Runtime
from raphael_core.installation import load_installation
from raphael_core.models import ModelGateway, Usage, load_models
from raphael_core.store import Store

DB_FILE = "raphael.sqlite"


def local_clock(timezone: str) -> Callable[[], datetime]:
    """Hora local de la instalación, sin zona (como la usa el harness). Si el sistema no tiene la base de zonas
    (Windows sin `tzdata`), la hora de la máquina."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone)
    except Exception:  # noqa: BLE001 - zoneinfo sin base de datos de zonas
        return datetime.now
    return lambda: datetime.now(tz).replace(tzinfo=None)


def build_models(store: Store, installation: Any, clock: Callable[[], datetime], models_path: str | Path | None,
                 env: dict[str, str] | None) -> ModelGateway | None:
    try:
        cfg = load_models(models_path) if models_path else load_models()
    except Exception:  # noqa: BLE001 - sin config de modelos: reglas
        return None
    return ModelGateway(cfg, Usage(store.space("_uso"), installation.limits.messages_month, clock), plan=installation.plan,
                        edition=installation.edition, env=dict(os.environ) if env is None else env)


def start(installation_path: str | Path, data_dir: str | Path, *, dev_dirs: Iterable[str | Path] = (),
          installed: bool = True, models_path: str | Path | None = None, env: dict[str, str] | None = None,
          clock: Callable[[], datetime] | None = None, models: bool = True,
          connectors: dict[str, Any] | None = None) -> tuple[Runtime, dict]:
    """(runtime montado, reporte del cargador). El reporte trae `errors` por brigada y del orquestador.
    `connectors`: los canales de salida por nombre ("whatsapp", "instagram"), con un método `send(destinatario, texto)`."""
    inst = load_installation(installation_path)
    inst.use_profile_from(os.environ if env is None else env)   # RAPHAEL_AUTONOMIA (deslizador de autonomía)
    data = Path(data_dir)
    data.mkdir(parents=True, exist_ok=True)
    clock = clock or local_clock(inst.timezone)
    store = Store(str(data / DB_FILE), clock=clock)
    gw = build_models(store, inst, clock, models_path, env) if models else None
    rt = Runtime(inst, store=store, clock=clock, models=gw, connectors=connectors)
    loader = Loader(rt, list(dev_dirs), installed=installed, installation_path=installation_path)
    report = Runtime.run(loader.apply())
    return rt, report
