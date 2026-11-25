"""Un `Operations` por instalación montada, compartido entre `setup` (que registra las tools) y los cocineros.

Las tools y los cocineros tienen que ver el MISMO servicio: el mismo celular conectado, el mismo navegador abierto, el mismo
modo de operación. Se guarda por runtime (débil: desaparece con él).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from weakref import WeakKeyDictionary

from .config import load_config
from .service import Operations

_SERVICES: WeakKeyDictionary[Any, Operations] = WeakKeyDictionary()


def _key(ctx: Any) -> Any:
    # el SetupContext y el Context de un cocinero guardan al runtime en `_rt`: es lo único que comparten
    return getattr(ctx, "_rt", ctx)


def ops_for(ctx: Any, env: Mapping[str, str] | None = None) -> Operations:
    """El servicio de esta instalación; lo arma la primera vez con la config de la brigada y el entorno."""
    key = _key(ctx)
    ops = _SERVICES.get(key)
    if ops is None:
        env = os.environ if env is None else env
        ops = Operations(load_config(ctx.config, env), env=env, clock=getattr(ctx, "now", None) or datetime.now)
        _SERVICES[key] = ops
    return ops


def peek(ctx: Any) -> Operations | None:
    return _SERVICES.get(_key(ctx))


def release(ctx: Any) -> Operations | None:
    """Saca el servicio del registro (al desmontar). Devuelve el que había, para cerrarlo."""
    return _SERVICES.pop(_key(ctx), None)
