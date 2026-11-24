"""Bus de eventos: así se enteran unas brigadas de lo que hacen otras, sin conocerse.

Cambios respecto del bus de Empresas 0.4:
- Aislamiento: si un suscriptor falla, el error se reporta (`on_error`) y NO le llega a quien publicó
  ni a los demás suscriptores.
- Manejadores comunes o `async`. `publish` (sync) llama a los comunes en el acto y agenda los async en el
  loop que esté corriendo; `apublish` espera a todos en orden. `drain()` espera lo agendado.
- Cada suscripción tiene dueño: desmontar una brigada saca todas las suyas (`unsubscribe`).
- Historial acotado (antes crecía sin límite).
- Ciclos: pasado el límite de profundidad se corta con `EventCycleError` (también entre tareas async).
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import logging
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("raphael_core.events")

Handler = Callable[[str, dict], Any]
ErrorHook = Callable[[str, str, BaseException], None]   # (dueño, evento, error)

_depth: contextvars.ContextVar[int] = contextvars.ContextVar("raphael_event_depth", default=0)


class EventCycleError(RuntimeError):
    """Eventos encadenados de más: casi seguro un ciclo entre brigadas."""


@dataclass(frozen=True)
class _Sub:
    owner: str
    handler: Handler


class EventBus:
    def __init__(self, max_depth: int = 8, history: int = 500, on_error: ErrorHook | None = None) -> None:
        self._subs: dict[str, list[_Sub]] = defaultdict(list)
        self._max = max_depth
        self.history: deque[tuple[str, dict]] = deque(maxlen=history)
        self._on_error = on_error
        self._pending: set[asyncio.Task] = set()

    # --- suscripciones
    def subscribe(self, event: str, handler: Handler, owner: str) -> None:
        self._subs[event].append(_Sub(owner, handler))

    def unsubscribe(self, owner: str) -> int:
        """Saca todas las suscripciones de un dueño. Devuelve cuántas sacó."""
        n = 0
        for event in list(self._subs):
            before = len(self._subs[event])
            self._subs[event] = [s for s in self._subs[event] if s.owner != owner]
            n += before - len(self._subs[event])
            if not self._subs[event]:
                del self._subs[event]
        return n

    def owners(self, event: str | None = None) -> set[str]:
        subs = self._subs.get(event, []) if event else [s for lst in self._subs.values() for s in lst]
        return {s.owner for s in subs}

    # --- publicar
    def _targets(self, event: str) -> list[_Sub]:
        return [*self._subs.get(event, []), *(self._subs.get("*", []) if event != "*" else [])]

    def _enter(self, event: str) -> contextvars.Token:
        depth = _depth.get()
        if depth >= self._max:
            raise EventCycleError(f"eventos encadenados de más (¿un ciclo?): {event}")
        return _depth.set(depth + 1)

    def _report(self, owner: str, event: str, exc: BaseException) -> None:
        logger.warning("el suscriptor %s falló con el evento %s: %r", owner, event, exc)
        if self._on_error is not None:
            try:
                self._on_error(owner, event, exc)
            except Exception:  # noqa: BLE001 - el reporte nunca rompe el bus
                logger.exception("on_error falló")

    def publish(self, event: str, data: dict, source: str = "") -> None:
        """Publica desde código sync. Los manejadores async se agendan (si no hay loop, se corren acá)."""
        token = self._enter(event)
        try:
            payload = {**data, "_from": source} if source else dict(data)
            self.history.append((event, dict(payload)))
            for sub in self._targets(event):
                try:
                    out = sub.handler(event, dict(payload))
                    if inspect.isawaitable(out):
                        self._schedule(sub.owner, event, out)
                except Exception as exc:  # noqa: BLE001 - aislamiento: un suscriptor roto no rompe a nadie
                    self._report(sub.owner, event, exc)
        finally:
            _depth.reset(token)

    async def apublish(self, event: str, data: dict, source: str = "") -> None:
        """Publica desde código async y espera a todos los manejadores, en orden."""
        token = self._enter(event)
        try:
            payload = {**data, "_from": source} if source else dict(data)
            self.history.append((event, dict(payload)))
            for sub in self._targets(event):
                try:
                    out = sub.handler(event, dict(payload))
                    if inspect.isawaitable(out):
                        await out
                except Exception as exc:  # noqa: BLE001
                    self._report(sub.owner, event, exc)
        finally:
            _depth.reset(token)

    def _schedule(self, owner: str, event: str, awaitable: Any) -> None:
        async def run() -> None:
            try:
                await awaitable
            except Exception as exc:  # noqa: BLE001
                self._report(owner, event, exc)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(run())  # sin loop corriendo: se resuelve en el acto
            return
        task = loop.create_task(run())  # hereda el contexto: la profundidad sigue contando
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def drain(self) -> None:
        """Espera las tareas async agendadas por `publish` (y las que esas agenden)."""
        while self._pending:
            await asyncio.gather(*list(self._pending))
