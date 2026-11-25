"""Healthcheck de la brigada (al montar y cada 5 minutos). Tres malos seguidos y la brigada deja de recibir mensajes,
así que solo da mal por lo que de verdad la rompe: una config inválida. Un catálogo caído NO es salud mala (se sigue
con la última copia y la Secretaria lo avisa como tarea)."""

from __future__ import annotations

from pydantic import ValidationError
from raphael_core import Health

from .config import business_config
from .tools import make_tools


def check(ctx) -> Health:
    try:
        cfg = business_config(ctx.config)
    except ValidationError as exc:
        first = exc.errors()[0]
        return Health(False, f"config del negocio inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}")
    missing = [n for n, v in (("nombre del negocio", cfg.business.name),) if not v]
    return Health(True, "ok" + (f" (falta: {', '.join(missing)})" if missing else ""))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta (y el error dice qué campo)."""
    try:
        business_config(ctx.config)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise ValueError(f"config del negocio inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}") from None
    for name, fn in make_tools(ctx).items():
        ctx.register_tool(name, fn)
