from __future__ import annotations

from datetime import datetime, timedelta


class Clock:
    """Reloj controlable para pruebas (se le pasa al harness como `clock`)."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 11, 18, 10, 0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> datetime:
        self.now += timedelta(**kw)
        return self.now
