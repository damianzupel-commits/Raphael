"""Watchdog del orquestador: vigila la corrida del jefe de una brigada y la corta si se cuelga.

Portado de JarvisRemote `orquestador/watchdog.py`. Es DEFENSIVO: solo mira el feed de la corrida, la cancela si hace falta
y lo deja anotado (feed, auditoría, tablero de efímeros y su propio registro en el espacio del orquestador). No ejecuta
tools ni toca ninguna compuerta.

Qué detecta (lo que declara el jefe en su `watch` gana; lo que falta lo pone la config del orquestador):
  - loop: la misma llamada idéntica (tool + argumentos, por efímero) `max_repeats` veces en la ventana, o casi la misma
    (cambian solo mayúsculas, espacios o puntuación), o la misma respuesta larga de tool repetida;
  - sin progreso: ningún evento nuevo durante `stall_seconds` (con latidos del motor, se le da más aire);
  - timeout: el turno supera la duración esperada (timeout de los efímeros + margen + lo que tarda el modelo del jefe);
  - errores: `max_errors` tools fallidas seguidas.
Además REPORTA (sin cortar) cuando el jefe ya perdió a un efímero por timeout o error.

Cambios respecto de JR: los eventos son los del motor v2 (`delegation`, `tool`/`tool_result` con `helper`,
`helper_result`, `heartbeat`, `report`); los límites salen del catálogo del harness y de la config; el registro de
intervenciones vive en el espacio del orquestador, no en un archivo.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any

EventCallback = Callable[[dict], Awaitable[None]]
KINDS = ("loop", "stall", "timeout", "errors")
KIND_TEXT = {"loop": "loop", "stall": "falta de progreso (deadlock)", "timeout": "timeout", "errors": "errores seguidos"}
COLLECTION = "watchdog"

_WINDOW = 10            # llamadas recientes que mira el detector de loops
_MIN_RESULT_CHARS = 40  # una respuesta de tool tan corta ("status: ok") se repite legítimamente
_BEAT_AIR = 3           # con el motor latiendo, el límite de «sin progreso» se multiplica por esto


def _norm_args(args: str) -> str:
    """Los argumentos sin lo que un modelo en loop cambia sin cambiar nada: mayúsculas, espacios y puntuación de borde.
    NO se tocan números ni palabras: leer `nota_1`, `nota_2` es trabajo legítimo."""
    return re.sub(r"[\s\"'.,;:!?¿¡]+", " ", args.lower()).strip()


@dataclass(frozen=True)
class Limits:
    max_seconds: float
    stall_seconds: float
    max_repeats: int
    max_errors: int
    poll: float = 2.0


def limits_for(watch: dict | None, cfg: Any) -> Limits:
    """Los límites de una corrida: lo que declara el jefe (`catalog()[i]["watch"]`) y, si falta, la config.
    La duración esperada reusa el timeout de los efímeros + margen + lo que puede tardar el modelo del jefe."""
    w = watch or {}
    base = float(w.get("helper_timeout") or 900.0)

    def pick(key: str, default: float) -> float:
        v = w.get(key)
        return float(v) if v else float(default)

    return Limits(max_seconds=pick("max_seconds", base + cfg.margin_seconds + cfg.chief_seconds),
                  stall_seconds=pick("stall_seconds", cfg.stall_seconds),
                  max_repeats=int(pick("max_repeats", cfg.max_repeats)),
                  max_errors=int(pick("max_errors", cfg.max_errors)),
                  poll=max(0.01, float(cfg.poll_seconds)))


@dataclass
class Verdict:
    kind: str       # uno de KINDS
    detail: str


class RunMonitor:
    """La vigilancia de UNA corrida: se alimenta con los eventos del feed y se consulta con `check()`."""

    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits, self._clock = limits, clock
        self.started = self.last_event = clock()
        self.finished = False
        self.helper: str | None = None      # último efímero en el que delegó el jefe
        self.last_beat: float | None = None
        self._calls: deque[str] = deque(maxlen=_WINDOW)
        self._similar: deque[str] = deque(maxlen=_WINDOW)
        self._results: deque[str] = deque(maxlen=_WINDOW)
        self._errors = 0
        self.reported: list[Verdict] = []   # efímeros que el jefe ya perdió (solo se informan)

    def observe(self, ev: dict) -> None:
        kind, name = ev.get("type"), str(ev.get("name") or "")
        if kind == "heartbeat":   # vivo, esperando a un modelo: no es progreso, pero tampoco está colgado
            self.last_beat = self._clock()
            return
        self.last_event = self._clock()
        who = ev.get("helper")
        tag = f"{who}:" if who else ""
        if kind == "report":
            self.finished = True
        elif kind == "delegation":
            self.helper = str(ev.get("helper") or "") or None
        elif kind == "helper_result":
            if not ev.get("ok", True):
                errors = "; ".join(str(e) for e in ev.get("errors") or []) or str(ev.get("summary") or "")
                self.reported.append(Verdict("timeout" if "no terminó" in errors or ev.get("reason") == "timeout"
                                             else "errors", f"{who or '?'}: {errors}"[:200]))
        elif kind == "tool":
            self._calls.append(f"{tag}{name}|{ev.get('args', '')}")
            self._similar.append(f"{tag}{name}|{_norm_args(str(ev.get('args', '')))}")
        elif kind == "tool_result":
            if ev.get("ok", True):
                self._errors = 0
                s = str(ev.get("summary") or "")
                if len(s) >= _MIN_RESULT_CHARS:
                    self._results.append(f"{tag}{name}|{s}")
            else:
                self._errors += 1

    def check(self) -> Verdict | None:
        if self.finished:
            return None
        lim, now = self.limits, self._clock()
        for window, what in ((self._calls, "la misma llamada idéntica"), (self._results, "la misma respuesta de tool"),
                             (self._similar, "casi la misma llamada")):
            if window:
                sig = max(set(window), key=window.count)
                if window.count(sig) >= lim.max_repeats:
                    return Verdict("loop", f"{what} {window.count(sig)} veces: {sig.replace('|', ' ', 1)[:120]}")
        if self._errors >= lim.max_errors:
            return Verdict("errors", f"{self._errors} tools fallidas seguidas")
        alive = self.last_beat is not None and now - self.last_beat <= max(60.0, lim.stall_seconds / 3)
        top = lim.stall_seconds * (_BEAT_AIR if alive else 1)
        if now - self.last_event > top:
            return Verdict("stall", f"{int(now - self.last_event)}s sin ningún evento nuevo (límite {int(top)}s)")
        if now - self.started > lim.max_seconds:
            return Verdict("timeout", f"{int(now - self.started)}s de turno (esperado ≤ {int(lim.max_seconds)}s)")
        return None


@dataclass
class Intervention:
    when: float
    brigade: str
    target: str        # "jefe de Cerebro" / "efímero investigacion-forense"
    kind: str
    action: str        # "cut" (lo cortó el watchdog) | "reported" (lo cortó el jefe; el watchdog lo informa)
    detail: str
    message: str = field(default="")

    def event(self) -> dict:
        return {"type": "watchdog", "action": self.action, "reason": self.kind, "target": self.target,
                "detail": self.detail, "message": self.message}


class Log:
    """Las últimas intervenciones, en el espacio del orquestador (acotadas). Best-effort."""

    def __init__(self, space: Any, keep: int = 50) -> None:
        self._space, self._keep = space, keep

    def add(self, iv: Intervention) -> None:
        try:
            n = self._space.next(COLLECTION)
            self._space.put(COLLECTION, n, {"n": n, **asdict(iv)})
            old = n - self._keep
            if old >= 1:
                self._space.delete(COLLECTION, old)
        except Exception:  # noqa: BLE001
            pass

    def recent(self, limit: int = 20) -> list[dict]:
        try:
            items = sorted(self._space.list(COLLECTION), key=lambda d: -d["n"])
        except Exception:  # noqa: BLE001
            return []
        return items[: max(1, min(limit, self._keep))]


async def supervise(run: Callable[[EventCallback], Awaitable[Any]], on_event: EventCallback, *, brigade: str,
                    brigade_name: str = "", limits: Limits, ctx: Any = None, log: Log | None = None,
                    clock: Callable[[], float] = time.monotonic, enabled: bool = True) -> tuple[Any, str]:
    """Corre `run(feed)` vigilado. Devuelve (resultado, "") o (None, aviso) si el watchdog cortó la corrida.

    `run` recibe el callback del feed (en el orquestador: `lambda feed: ctx.ask(brigada, pedido, on_event=feed, ...)`).
    El aviso es texto de CÓDIGO: sale literal, no pasa por la voz. Una excepción de la corrida se propaga igual."""
    if not enabled:
        return await run(on_event), ""
    mon = RunMonitor(limits, clock)
    name = brigade_name or brigade

    def note(iv: Intervention) -> None:
        if log is not None:
            log.add(iv)
        if ctx is not None:
            try:
                ctx.record("watchdog", brigada=brigade, accion=iv.action, motivo=iv.kind, detalle=iv.detail[:200])
            except Exception:  # noqa: BLE001
                pass

    async def watched(ev: dict) -> None:
        before = len(mon.reported)
        mon.observe(ev)
        await on_event(ev)
        for v in mon.reported[before:]:
            iv = Intervention(time.time(), brigade, f"efímero {v.detail.split(':', 1)[0]}", v.kind, "reported", v.detail,
                              f"un efímero de {name} cayó por {KIND_TEXT[v.kind]} (lo cortó el jefe): {v.detail}")
            note(iv)
            await on_event(iv.event())

    task = asyncio.ensure_future(run(watched))
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=limits.poll)
            if done:
                return task.result(), ""
            v = mon.check()
            if v is None:
                continue
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            target = f"efímero {mon.helper}" if mon.helper else f"jefe de {name}"
            iv = Intervention(time.time(), brigade, target, v.kind, "cut", v.detail,
                              f"el watchdog cortó al {target} por {KIND_TEXT[v.kind]}: {v.detail}")
            note(iv)
            if ctx is not None:
                try:
                    ctx.mark_cut(brigade, f"{KIND_TEXT[v.kind]}: {v.detail}")
                except Exception:  # noqa: BLE001
                    pass
            await on_event(iv.event())
            text = iv.message[0].upper() + iv.message[1:]
            return None, f"{text}. La corrida se interrumpió; podés reintentar."
    finally:
        if not task.done():   # se canceló el turno: no dejar la corrida huérfana
            task.cancel()
