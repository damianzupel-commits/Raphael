"""Salud y montaje. El healthcheck solo da MAL por lo que de verdad rompe la brigada: una config inválida. Que falte una
clave, un proveedor de búsqueda o el modelo local NO es salud mala: la brigada sigue con reglas y lo cuenta en el detalle."""

from __future__ import annotations

import os

from pydantic import ValidationError
from raphael_core import Health

from .config import investigacion_config
from .env import env_from_context
from .search.chain import build_providers
from .service import Investigacion


def _config_problem(raw: dict) -> str:
    try:
        investigacion_config(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        return f"config de Investigación inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}"
    return ""


def check(ctx) -> Health:
    problem = _config_problem(ctx.config)
    if problem:
        return Health(False, problem)
    env = env_from_context(ctx)
    notes = []
    providers = build_providers(env)
    if not any(p.is_configured() for p in providers):
        notes.append("sin proveedor de búsqueda (BRAVE_SEARCH_API_KEY o SEARXNG_URL): Scout y las tendencias esperan")
    if not os.environ.get("INVESTIGACION_LOG_KEY"):
        notes.append("registro de casos sin firma (falta INVESTIGACION_LOG_KEY): solo encadenado por hash")
    if not env.config.inbox_dir:
        notes.append("sin `inbox_dir`: el forense por pedido de un modelo no toma archivos")
    return Health(True, "ok" + (f" ({'; '.join(notes)})" if notes else ""))


def setup(ctx) -> None:
    """Valida la config y registra las tools (las del manifiesto que no traen `entry`)."""
    problem = _config_problem(ctx.config)
    if problem:
        raise ValueError(problem)
    inv = Investigacion(env_from_context(ctx))
    for name, fn in inv.tools().items():
        ctx.register_tool(name, fn)
