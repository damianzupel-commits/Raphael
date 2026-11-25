"""Healthcheck y `setup` de la brigada. Solo da mal por lo que de verdad la rompe: una config inválida. Que falten datos
del negocio o que la consulta de fuentes esté apagada NO es salud mala: se avisa en el detalle y los borradores salen
con `[COMPLETAR: ...]` / "sin verificar"."""

from __future__ import annotations

from pydantic import ValidationError
from raphael_core import Health

from .config import legales_config, missing_business


def _first(exc: ValidationError) -> str:
    e = exc.errors()[0]
    return f"{'.'.join(map(str, e['loc']))}: {e['msg']}"


def check(ctx) -> Health:
    try:
        cfg = legales_config(ctx.config)
    except ValidationError as exc:
        return Health(False, f"config de legales inválida: {_first(exc)}")
    notes = []
    if (m := missing_business(cfg)):
        notes.append("faltan datos del negocio: " + ", ".join(m))
    if cfg.fuentes.modo != "real":
        notes.append(f"fuentes en modo {cfg.fuentes.modo}: todo sale sin verificar")
    return Health(True, "ok" + (f" ({'; '.join(notes)})" if notes else ""))


def validate(ctx) -> None:
    try:
        legales_config(ctx.config)
    except ValidationError as exc:
        raise ValueError(f"config de legales inválida: {_first(exc)}") from None
