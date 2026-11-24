"""Bus de eventos: así se enteran unas brigadas de lo que hacen otras, sin conocerse."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

Manejador = Callable[[str, dict], None]


class Bus:
    def __init__(self, max_profundidad: int = 8) -> None:
        self._subs: dict[str, list[Manejador]] = defaultdict(list)
        self._prof = 0
        self._max = max_profundidad
        self.historial: list[tuple[str, dict]] = []

    def suscribir(self, evento: str, fn: Manejador) -> None:
        self._subs[evento].append(fn)

    def publicar(self, evento: str, datos: dict) -> None:
        if self._prof >= self._max:
            raise RuntimeError(f"eventos encadenados de más (¿un ciclo?): {evento}")
        self.historial.append((evento, dict(datos)))
        self._prof += 1
        try:
            for fn in [*self._subs.get(evento, []), *self._subs.get("*", [])]:
                fn(evento, dict(datos))
        finally:
            self._prof -= 1
