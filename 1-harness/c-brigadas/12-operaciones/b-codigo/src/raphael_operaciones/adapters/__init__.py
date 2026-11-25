"""Adaptadores enchufables de Operaciones: lo único que toca el mundo real.

Cada uno tiene un protocolo, una versión REAL y una SIMULADA. Los tests corren con las simuladas; en la PC de Damián se
pasa a las reales con `OPERACIONES_ADAPTADORES=real`. Una librería que falta (pyautogui, playwright…) se avisa con un
mensaje claro, no rompe el resto.
"""

from __future__ import annotations

from raphael_core.contract import ActionError


class AdapterUnavailable(ActionError):
    """El adaptador real no se puede usar acá (falta una librería, no es Windows, el celular no está conectado…)."""


class AdapterDisabled(ActionError):
    """El adaptador real está apagado por configuración: el mensaje dice qué interruptor prender."""
