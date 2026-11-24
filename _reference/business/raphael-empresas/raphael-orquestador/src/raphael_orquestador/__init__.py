"""Orquestador de Raphael."""

__version__ = "0.3.0"

from .orquestador import OrquestadorRaphael  # noqa: E402

ORQUESTADOR = OrquestadorRaphael

__all__ = ["ORQUESTADOR", "OrquestadorRaphael", "__version__"]
