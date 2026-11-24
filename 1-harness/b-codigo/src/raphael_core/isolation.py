"""Aislamiento de fallos: toda llamada del harness a una pieza montada pasa por `Guard`.

- Una excepción no sale de acá: se devuelve como resultado fallido y se cuenta.
- Las llamadas async (y las sync marcadas `blocking`, que van a un hilo) tienen tope de tiempo.
- Tras `max_failures` fallas SEGUIDAS de un mismo método (`label`) la pieza queda caída (`down`) y el harness
  deja de llamarla hasta que alguien la reactive. Una llamada que sale bien pone en cero el contador de ESE
  método: que `interest` ande no salva a un `handle` que siempre falla.

Es el chokepoint que en Empresas no existía (una brigada rota tumbaba el mensaje entero) y que en
JarvisRemote estaba solo para los ayudantes (`engine.py`: timeout + excepciones contenidas).
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("raphael_core.isolation")

DownHook = Callable[[str, str], None]   # (pieza, motivo)


@dataclass
class Outcome:
    ok: bool
    value: Any = None
    error: BaseException | None = None
    timed_out: bool = False
    skipped: bool = False     # la pieza estaba caída y no se la llamó

    @property
    def reason(self) -> str:
        if self.skipped:
            return "la pieza está caída"
        if self.timed_out:
            return "se pasó del tiempo"
        return repr(self.error) if self.error else ""


@dataclass
class _State:
    failures: dict[str, int] = field(default_factory=dict)
    down: bool = False
    reason: str = ""
    history: list[str] = field(default_factory=list)


class Guard:
    def __init__(self, max_failures: int = 3, default_timeout: float | None = 60.0,
                 on_down: DownHook | None = None, passthrough: tuple[type[BaseException], ...] = ()) -> None:
        self._max = max_failures
        self._timeout = default_timeout
        self._on_down = on_down
        self._state: dict[str, _State] = {}
        #: excepciones que son parte del contrato (ej. ActionError): se devuelven como fallo pero no cuentan
        self._passthrough = passthrough

    def _st(self, piece: str) -> _State:
        return self._state.setdefault(piece, _State())

    def is_down(self, piece: str) -> bool:
        return self._st(piece).down

    def down_reason(self, piece: str) -> str:
        return self._st(piece).reason

    def mark_down(self, piece: str, reason: str) -> None:
        st = self._st(piece)
        if st.down:
            return
        st.down, st.reason = True, reason
        logger.warning("pieza %s caída: %s", piece, reason)
        if self._on_down is not None:
            try:
                self._on_down(piece, reason)
            except Exception:  # noqa: BLE001
                logger.exception("on_down falló")

    def revive(self, piece: str) -> None:
        self._state[piece] = _State()

    def forget(self, piece: str) -> None:
        self._state.pop(piece, None)

    def failures(self, piece: str, label: str = "") -> int:
        return self._st(piece).failures.get(label, 0)

    def history(self, piece: str) -> list[str]:
        """Las últimas fallas de una pieza (hasta 10), aunque después haya andado bien."""
        return list(self._st(piece).history)

    def _ok(self, piece: str, value: Any, label: str = "") -> Outcome:
        self._st(piece).failures[label] = 0
        return Outcome(True, value)

    def _fail(self, piece: str, exc: BaseException | None, timed_out: bool = False, label: str = "") -> Outcome:
        out = Outcome(False, error=exc, timed_out=timed_out)
        if exc is not None and isinstance(exc, self._passthrough):
            return out
        st = self._st(piece)
        st.failures[label] = st.failures.get(label, 0) + 1
        st.history = [*st.history[-9:], out.reason]
        if st.failures[label] >= self._max:
            where = f" en {label}" if label else ""
            self.mark_down(piece, f"{st.failures[label]} fallas seguidas{where}; la última: {out.reason}")
        return out

    async def call(self, piece: str, fn: Callable[..., Any], *args: Any, timeout: float | None = None,
                   blocking: bool = False, label: str = "", **kwargs: Any) -> Outcome:
        """Llama a `fn` (sync o async) de forma aislada."""
        if self.is_down(piece):
            return Outcome(False, skipped=True)
        limit = self._timeout if timeout is None else timeout
        try:
            if inspect.iscoroutinefunction(fn):
                value = await asyncio.wait_for(fn(*args, **kwargs), timeout=limit)
            elif blocking:
                value = await asyncio.wait_for(asyncio.to_thread(fn, *args, **kwargs), timeout=limit)
            else:
                value = fn(*args, **kwargs)
                if inspect.isawaitable(value):
                    value = await asyncio.wait_for(value, timeout=limit)
        except TimeoutError as exc:
            return self._fail(piece, exc, timed_out=True, label=label)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - aislamiento
            return self._fail(piece, exc, label=label)
        return self._ok(piece, value, label=label)

    def call_sync(self, piece: str, fn: Callable[..., Any], *args: Any, label: str = "", **kwargs: Any) -> Outcome:
        """Versión sync (sin tope de tiempo) para lo que corre fuera de un loop: tests, compat v1."""
        if self.is_down(piece):
            return Outcome(False, skipped=True)
        try:
            value = fn(*args, **kwargs)
            if inspect.isawaitable(value):
                value = asyncio.run(_await(value))
        except Exception as exc:  # noqa: BLE001
            return self._fail(piece, exc, label=label)
        return self._ok(piece, value, label=label)


async def _await(aw: Any) -> Any:
    return await aw
