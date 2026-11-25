"""Healthcheck y validación de la brigada. Solo da mal por una config inválida; lo que falta (claves, ffmpeg) se avisa en el
detalle y los cocineros degradan solos."""

from __future__ import annotations

from pydantic import ValidationError
from raphael_core import Health

from .config import contenido_config
from .entorno import build, missing_for_real
from .tools import make_tools


def _first(exc: ValidationError) -> str:
    e = exc.errors()[0]
    return f"config de contenido inválida: {'.'.join(map(str, e['loc']))}: {e['msg']}"


def check(ctx) -> Health:
    try:
        cfg = contenido_config(ctx.config)
    except ValidationError as exc:
        return Health(False, _first(exc))
    modos = build(cfg).modos()
    falta = missing_for_real() if "mock" not in modos.values() else {}
    detalle = ", ".join(f"{k}: {v}" for k, v in modos.items())
    if falta:
        detalle += " · falta " + "; ".join(f"{k} ({', '.join(v)})" for k, v in falta.items())
    return Health(True, detalle)


def validate(ctx) -> None:
    try:
        contenido_config(ctx.config)
    except ValidationError as exc:
        raise ValueError(_first(exc)) from None
    for name, fn in make_tools(ctx).items():
        ctx.register_tool(name, fn)
