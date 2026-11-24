"""Brigada Atención de Raphael."""

__version__ = "0.1.0"

from .brigada import Atencion  # noqa: E402

BRIGADA = Atencion

__all__ = ["BRIGADA", "Atencion", "__version__"]
