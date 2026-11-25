"""Healthcheck y validación de la config de la brigada.

La salud solo da mal por lo que de verdad la rompe: una config inválida. Que falte una clave o que una fuente no responda
NO es salud mala (el cocinero avisa y sigue): si no, tres chequeos malos seguidos la dejarían sin atender.
"""

from __future__ import annotations

from raphael_core import Health

from . import fuentes

MODOS = ("real", "simulado")


def problema(config: dict) -> str | None:
    modo = config.get("modo", "real")
    if modo not in MODOS:
        return f"modo inválido: {modo!r} (real o simulado)"
    n = config.get("pines_max")
    if n is not None and (not isinstance(n, int) or isinstance(n, bool) or not 10 <= n <= 5000):
        return "pines_max tiene que ser un entero entre 10 y 5000"
    return None


def check(ctx) -> Health:
    p = problema(ctx.config)
    if p:
        return Health(False, f"config inválida: {p}")
    f = fuentes.elegir(ctx.config)
    if f.simulado:
        return Health(True, "ok, en modo SIMULADO (datos de muestra, sin red)")
    faltan = [v.split()[1] for v in f.estado_claves().values() if v.startswith("falta")]
    return Health(True, "ok" + (f" (sin clave: {', '.join(faltan)})" if faltan else ""))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta y el error dice qué campo."""
    p = problema(ctx.config)
    if p:
        raise ValueError(f"config de geolocalización inválida: {p}")
