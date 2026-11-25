"""Fuentes de datos de la brigada: la real (internet) y la simulada (sin red, para tests y pruebas sin claves)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .base import ALIAS, CAPAS, LIBRES, Fuentes, ais_a_puntos
from .real import FuentesReales
from .simulado import FuentesSimuladas

__all__ = ["ALIAS", "CAPAS", "LIBRES", "Fuentes", "FuentesReales", "FuentesSimuladas", "ais_a_puntos", "elegir"]


def elegir(config: Mapping | None = None, env: Mapping[str, str] | None = None) -> Fuentes:
    """`modo` de la config de la brigada (`real` o `simulado`); la variable RAPHAEL_GEO_MODO lo pisa. Por defecto: real."""
    e = os.environ if env is None else env
    modo = (e.get("RAPHAEL_GEO_MODO") or (config or {}).get("modo") or "real").strip().lower()
    if modo == "simulado":
        return FuentesSimuladas(e)
    return FuentesReales(e)
