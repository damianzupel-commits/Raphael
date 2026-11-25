"""Healthcheck de la brigada: solo da mal una config inválida. Un adaptador real sin clave NO es mala salud: cae al
simulado y lo avisa (el detalle sale en `estado` y en la salud como texto)."""

from __future__ import annotations

import os

from pydantic import ValidationError
from raphael_core import Health

from . import ibkr
from .config import trading_config


def _modes(cfg) -> str:
    notes = []
    if cfg.data.adapter == "oanda" and not os.environ.get("OANDA_API_TOKEN"):
        notes.append("datos: falta OANDA_API_TOKEN, simulados")
    if cfg.broker.adapter == "oanda" and not (os.environ.get("OANDA_API_TOKEN") and os.environ.get("OANDA_ACCOUNT_ID")):
        notes.append("broker: faltan claves de OANDA, simulado")
    if "ibkr" in (cfg.data.adapter, cfg.broker.adapter) and not ibkr.available():
        notes.append("IBKR: falta instalar ib_async, simulado")
    return " (" + "; ".join(notes) + ")" if notes else ""


def check(ctx) -> Health:
    try:
        cfg = trading_config(ctx.config)
    except ValidationError as exc:
        first = exc.errors()[0]
        return Health(False, f"config de trading inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}")
    return Health(True, "ok" + _modes(cfg))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta."""
    try:
        trading_config(ctx.config)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ValueError(f"config de trading inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}") from None
