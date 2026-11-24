"""Pendientes: lo que espera a una persona (aprobar, rechazar o resolver).

Dos clases de pendiente:
    - "action": una acción que el Policy Engine no dejó ejecutar sola (`aprobacion` o `humano`);
    - "trust":  una propuesta de la confianza progresiva ("aprobaste esto N veces, ¿la dejo automática?").

Los números se validan: un id inventado o ya cerrado se rechaza con `ActionError` (nunca se ejecuta nada).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .contract import Action, ActionError, Level
from .store import Space

OPEN = "abierto"


class Approvals:
    COLLECTION = "pending"

    def __init__(self, space: Space, clock: Callable[[], datetime]) -> None:
        self._s = space
        self._clock = clock

    def create(self, *, brigade: str, cook: str, level: Level, summary: str, action: Action | None = None,
               kind: str = "action", reason: str = "", data: dict | None = None) -> dict:
        pid = self._s.next(self.COLLECTION)
        doc = {"id": pid, "kind": kind, "brigade": brigade, "cook": cook, "level": level.value, "summary": summary,
               "action": action.to_dict() if action else None, "reason": reason, "data": data or {},
               "state": OPEN, "created": self._clock().isoformat(timespec="seconds")}
        return self._s.put(self.COLLECTION, pid, doc)

    def open(self, pid: Any) -> dict:
        try:
            n = int(pid)
        except (TypeError, ValueError):
            raise ActionError(f"'{pid}' no es un número de pendiente") from None
        doc = self._s.get(self.COLLECTION, n)
        if not doc or doc["state"] != OPEN:
            raise ActionError(f"no hay un pendiente abierto con el número {n}")
        return doc

    def close(self, pid: int, state: str, **extra: Any) -> dict:
        doc = {**self._s.get(self.COLLECTION, pid), "state": state,
               "closed": self._clock().isoformat(timespec="seconds"), **extra}
        return self._s.put(self.COLLECTION, pid, doc)

    def list(self, state: str | None = OPEN, brigade: str | None = None) -> list[dict]:
        out = self._s.list(self.COLLECTION)
        return [p for p in out if (state is None or p["state"] == state) and (brigade is None or p["brigade"] == brigade)]
