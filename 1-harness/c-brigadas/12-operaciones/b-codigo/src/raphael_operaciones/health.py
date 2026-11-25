"""Healthcheck de Operaciones (al montar y cada 5 minutos). Tres malos seguidos y la brigada deja de recibir mensajes, así
que solo da mal por lo que de verdad la rompe: una config inválida, o un interruptor real prendido sin su librería.
En modo simulado siempre da bien y lo dice (para que nadie crea que Raphael ya está tocando la PC)."""

from __future__ import annotations

import importlib.util
import sys

from raphael_core import Health

from .config import ConfigError
from .registry import ops_for


def _have(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def check(ctx) -> Health:
    try:
        ops = ops_for(ctx)
        cfg = ops.config
    except ConfigError as exc:
        return Health(False, f"config de Operaciones inválida: {exc}")
    if not cfg.real:
        return Health(True, "modo simulado: no toca la PC ni el celular (OPERACIONES_ADAPTADORES=real para usarlos)")
    missing = []
    if cfg.desktop and (sys.platform != "win32" or not (_have("pyautogui") and _have("pywinauto"))):
        missing.append("escritorio (Windows con pyautogui y pywinauto)")
    if missing:
        return Health(False, "interruptor prendido sin lo necesario: " + "; ".join(missing))
    on = [n for n, v in (("shell PC", cfg.pc_shell), ("escritorio", cfg.desktop), ("shell celular", cfg.phone_shell),
                         ("cámara", cfg.phone_camera)) if v]
    return Health(True, f"modo real · modo {ops.mode.mode.value} · prendido: {', '.join(on) or 'solo lectura'}")
