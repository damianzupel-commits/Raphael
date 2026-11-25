"""Modos de operación: SUPERVISADO (Damián mirando) y AUTÓNOMO (Raphael solo). Portado de `operation_mode.py`.

- SUPERVISADO: el sandbox de archivos se abre a las raíces amplias que Damián configure.
- AUTÓNOMO: el sandbox se acota a la carpeta segura (más lo que se haya permitido).

Diseño a prueba de fallas (heredado de JarvisRemote):
- El default es AUTÓNOMO, el más restrictivo. Un valor desconocido también da AUTÓNOMO, nunca supervisado por error.
- ANTI AUTO-ESCALADA: pasar de AUTÓNOMO a SUPERVISADO no se puede hacer desde adentro de un llamado de tool (o sea, que
  Raphael se amplíe a sí mismo los permisos). Solo lo cambia la persona, con el comando `modo` del cocinero supervisor.
  Cada tool corre dentro de `agent_turn()`; ninguna tool cambia el modo.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum


class OperationMode(StrEnum):
    SUPERVISED = "supervisado"
    AUTONOMOUS = "autonomo"


_SUPERVISED_WORDS = {"supervisado", "supervised", "attended"}
_AUTONOMOUS_WORDS = {"autonomo", "autónomo", "autonomous", "unattended"}

_agent_turn: ContextVar[bool] = ContextVar("operaciones_turno_del_agente", default=False)


def parse_mode(raw: str | None) -> tuple[OperationMode, str | None]:
    """(modo, aviso). Vacío o desconocido = AUTÓNOMO; si era desconocido, el aviso lo dice."""
    text = (raw or "").strip().lower()
    if text in _SUPERVISED_WORDS:
        return OperationMode.SUPERVISED, None
    if text in _AUTONOMOUS_WORDS or not text:
        return OperationMode.AUTONOMOUS, None
    return OperationMode.AUTONOMOUS, f"modo '{raw}' no reconocido: se usa autónomo (el restrictivo)"


@contextmanager
def agent_turn() -> Iterator[None]:
    """Marca que corre un llamado de tool (lo que pidió el modelo). Habilita la defensa anti auto-escalada."""
    token = _agent_turn.set(True)
    try:
        yield
    finally:
        _agent_turn.reset(token)


def in_agent_turn() -> bool:
    return _agent_turn.get()


class ModeState:
    """El modo vigente de la instalación. Arranca en el de la config y lo cambia solo la persona."""

    def __init__(self, default: OperationMode = OperationMode.AUTONOMOUS) -> None:
        self.default = default
        self._mode = default

    @property
    def mode(self) -> OperationMode:
        return self._mode

    @property
    def supervised(self) -> bool:
        return self._mode is OperationMode.SUPERVISED

    def set(self, mode: OperationMode) -> OperationMode:
        if mode is OperationMode.SUPERVISED and self._mode is OperationMode.AUTONOMOUS and in_agent_turn():
            raise PermissionError("Auto-escalada de modo bloqueada: no se puede pasar de autónomo a supervisado desde "
                                  "adentro de un llamado de tool. El modo lo cambia Damián, no Raphael.")
        self._mode = mode
        return mode
