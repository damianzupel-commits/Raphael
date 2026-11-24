"""Watchdog del orquestador: vigila la ejecución de los jefes y ayudantes en curso y corta los que se cuelgan.

Es DEFENSIVO: solo mira el feed de eventos de una corrida (start / tool / tool_result / final), corta la corrida
colgada (cancela la tarea del jefe, y con ella a su ayudante efímero) y lo reporta en el feed del orquestador.
No escribe nada fuera de su propio registro de intervenciones, no ejecuta tools y no toca ningún gate.

Qué detecta (contra lo que el spec de la brigada declara, `BrigadeSpec.watch`; lo que falta lo pone el default de `.env`):
  - loop        la misma llamada idéntica (tool + argumentos) repetida `max_repeats` veces en la ventana, o la misma
                respuesta de tool (larga) repetida otras tantas veces.
  - sin progreso  ningún evento nuevo en el feed durante `stall_seconds` (deadlock / colgado).
  - timeout     el turno supera la duración esperada (`max_seconds`; default = el timeout de ayudante que ya existe
                + margen, así el corte propio del jefe, que informa mejor, salta primero cuando hay ayudante).
  - errores     `max_errors` tools fallidas seguidas.
Además REPORTA (sin cortar él) cuando el propio jefe ya cortó o perdió a un ayudante por timeout o error.

Con el flujo decidido (Ayudantes -> Jefe -> Orquestador) un turno del jefe es: planificar + ayudantes (en paralelo) +
sintetizar. Por eso la duración esperada suma, además del timeout de ayudante, un presupuesto para el LLM del jefe
(`WATCHDOG_JEFE_SECONDS`): si un ayudante agota su tiempo, el jefe todavía tiene que poder reportar ese fallo. Los eventos
`plan`, `delegacion`, `resultado_ayudante`, `sintesis` y `reporte` cuentan como progreso; las llamadas se distinguen por
ayudante (dos ayudantes en paralelo haciendo la misma búsqueda no son un loop).

El aviso de corte es texto de CÓDIGO: sale como `final` con `origen: "watchdog"` y se muestra LITERAL (no pasa por el LLM
de la voz del orquestador).

Variables de `.env` (todas opcionales): WATCHDOG_ENABLED (1), WATCHDOG_STALL_SECONDS (300), WATCHDOG_MAX_REPEATS (4),
WATCHDOG_MAX_ERRORS (5), WATCHDOG_MARGIN_SECONDS (30), WATCHDOG_JEFE_SECONDS (600), WATCHDOG_POLL_SECONDS (2).
Límite honesto: cancelar una corrida corta lo que está en `await`; una tool síncrona en un hilo termina sola.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

logger = logging.getLogger("orquestador.watchdog")

EventCallback = Callable[[dict], Awaitable[None]]
_WINDOW = 10            # cuántas llamadas recientes mira el detector de loops
_MIN_RESULT_CHARS = 40  # una respuesta de tool tan corta ("status: ok") se repite legítimamente: no cuenta como loop
_LOG = Path(__file__).resolve().parent.parent / "data" / "watchdog" / "intervenciones.jsonl"
_RECENT: deque[dict] = deque(maxlen=50)

_MARGEN_PARECIDAS = 0   # una llamada "parecida" (ver _normalizar_args) cuenta como la idéntica
_AIRE_CON_LATIDOS = 3   # con el motor latiendo, el límite de «sin progreso» se multiplica por esto

KINDS = ("loop", "sin_progreso", "timeout", "errores")


def _normalizar_args(args: str) -> str:
    """Los argumentos de una llamada sin lo que un modelo en loop cambia sin cambiar nada: mayúsculas, espacios y puntuación
    de borde. A propósito NO se tocan los números ni las palabras: leer `nota_1`, `nota_2`, `nota_3` es trabajo legítimo, no
    un loop (el loop que cambia de verdad los argumentos lo detecta la respuesta repetida de la tool)."""
    import re

    return re.sub(r"[\s\"'.,;:!?¿¡]+", " ", args.lower()).strip()
KIND_TEXT = {"loop": "loop", "sin_progreso": "falta de progreso (deadlock)", "timeout": "timeout", "errores": "errores seguidos"}


def _env_num(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def enabled() -> bool:
    return os.getenv("WATCHDOG_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class Limits:
    max_seconds: float
    stall_seconds: float
    max_repeats: int
    max_errors: int
    poll: float = 2.0


def limits_for(spec: Any | None) -> Limits:
    """Límites de una corrida: lo que declara el spec (`watch`) y, si falta, el default global de `.env`."""
    from brigades.engine import default_helper_timeout

    w = getattr(spec, "watch", None)
    fn = getattr(spec, "helper_timeout", None)
    try:
        base = float(fn()) if fn else default_helper_timeout()  # REUSA el timeout de ayudante existente
    except Exception:  # noqa: BLE001
        base = default_helper_timeout()
    # margen + lo que puede tardar el LLM del jefe (plan y síntesis con reintento) después de que terminan los ayudantes
    margin = _env_num("WATCHDOG_MARGIN_SECONDS", 30) + _env_num("WATCHDOG_JEFE_SECONDS", 600)

    def pick(declared, env_name: str, default: float) -> float:
        return float(declared) if declared else _env_num(env_name, default)

    return Limits(
        max_seconds=float(w.max_seconds) if w and w.max_seconds else base + margin,
        stall_seconds=pick(w.stall_seconds if w else None, "WATCHDOG_STALL_SECONDS", 300),
        max_repeats=int(pick(w.max_repeats if w else None, "WATCHDOG_MAX_REPEATS", 4)),
        max_errors=int(pick(w.max_errors if w else None, "WATCHDOG_MAX_ERRORS", 5)),
        poll=max(0.05, _env_num("WATCHDOG_POLL_SECONDS", 2)),
    )


@dataclass
class Verdict:
    kind: str       # uno de KINDS
    detail: str


class RunMonitor:
    """Estado de vigilancia de UNA corrida: se alimenta con los eventos del feed y se consulta con `check()`."""

    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits, self._clock = limits, clock
        self.started = self.last_event = clock()
        self.finished = False
        self.helper: str | None = None  # último ayudante en el que delegó el jefe
        self.last_beat: float | None = None  # último `latido` del motor (está vivo, esperando a un modelo)
        self._calls: deque[str] = deque(maxlen=_WINDOW)
        self._parecidas: deque[str] = deque(maxlen=_WINDOW)  # las mismas llamadas, sin los detalles que cambian apenas
        self._results: deque[str] = deque(maxlen=_WINDOW)
        self._errors = 0
        self.reported: list[Verdict] = []  # cortes/fallas que el jefe ya resolvió por su cuenta (solo se reportan)

    def observe(self, ev: dict) -> None:
        kind, name = ev.get("type"), str(ev.get("name") or "")
        if kind == "latido":  # el motor avisa que sigue vivo esperando a un modelo: NO es progreso, pero tampoco está colgado
            self.last_beat = self._clock()
            return
        self.last_event = self._clock()
        if kind == "final":
            self.finished = True
        elif kind == "tool" and name.startswith("delegar:"):
            self.helper = name.split(":", 1)[1]
        elif kind == "tool":
            who = ev.get("ayudante")  # con ayudantes en paralelo, la misma llamada de dos ayudantes distintos no es un loop
            self._calls.append(f"{who + ':' if who else ''}{name}|{ev.get('args', '')}")
            self._parecidas.append(f"{who + ':' if who else ''}{name}|{_normalizar_args(str(ev.get('args', '')))}")
        elif kind == "tool_result" and name.startswith("delegar:"):
            if not ev.get("ok", True):  # el jefe ya cortó/perdió al ayudante: el watchdog lo reporta
                s = str(ev.get("summary") or "")
                self.reported.append(Verdict("timeout" if "no terminó" in s else "errores", s[:200]))
        elif kind == "tool_result":
            if ev.get("ok", True):
                self._errors = 0
                s = str(ev.get("summary") or "")
                if len(s) >= _MIN_RESULT_CHARS:
                    who = ev.get("ayudante")
                    self._results.append(f"{who + ':' if who else ''}{name}|{s}")
            else:
                self._errors += 1

    def check(self) -> Verdict | None:
        if self.finished:
            return None
        lim, now = self.limits, self._clock()
        for window, what in ((self._calls, "la misma llamada idéntica"), (self._results, "la misma respuesta de tool")):
            if window:
                sig = max(set(window), key=window.count)
                if window.count(sig) >= lim.max_repeats:
                    return Verdict("loop", f"{what} {window.count(sig)} veces: {sig.replace('|', ' ', 1)[:120]}")
        if self._parecidas:  # la misma tool con argumentos que solo cambian en mayúsculas, espacios o puntuación
            sig = max(set(self._parecidas), key=self._parecidas.count)
            if self._parecidas.count(sig) >= lim.max_repeats + _MARGEN_PARECIDAS:
                return Verdict("loop", f"casi la misma llamada {self._parecidas.count(sig)} veces: {sig.replace('|', ' ', 1)[:120]}")
        if self._errors >= lim.max_errors:
            return Verdict("errores", f"{self._errors} tools fallidas seguidas")
        # Con latidos recientes el motor está vivo esperando a un modelo lento: se le da más aire antes de decir «sin progreso»
        # (igual lo acotan el timeout del ayudante y el del LLM del jefe). Sin latidos, el límite es el de siempre.
        vivo = self.last_beat is not None and now - self.last_beat <= max(60.0, lim.stall_seconds / 3)
        tope = lim.stall_seconds * (_AIRE_CON_LATIDOS if vivo else 1)
        if now - self.last_event > tope:
            return Verdict("sin_progreso", f"{int(now - self.last_event)}s sin ningún evento nuevo (límite {int(tope)}s)")
        if now - self.started > lim.max_seconds:
            return Verdict("timeout", f"{int(now - self.started)}s de turno (esperado ≤ {int(lim.max_seconds)}s)")
        return None


@dataclass
class Intervention:
    ts: float
    brigade: str
    target: str     # "jefe Cerebro" / "ayudante investigacion-forense"
    kind: str
    action: str     # "cut" (lo cortó el watchdog) | "reported" (lo cortó el jefe; el watchdog lo informa)
    detail: str
    message: str = field(default="")


def _record(iv: Intervention) -> Intervention:
    d = asdict(iv)
    _RECENT.appendleft(d)
    logger.warning("watchdog: %s", iv.message)
    try:  # registro propio, best-effort (data/ está gitignoreada)
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        logger.debug("no se pudo escribir el registro del watchdog", exc_info=True)
    return iv


def recent(limit: int = 20) -> list[dict]:
    return list(_RECENT)[: max(1, min(limit, 50))]


def status() -> dict:
    return {"enabled": enabled(), "kinds": list(KINDS), "defaults": asdict(limits_for(None)), "recent": recent(10)}


def _event(iv: Intervention) -> dict:
    return {"type": "watchdog", "action": iv.action, "reason": iv.kind, "target": iv.target, "detail": iv.detail,
            "message": iv.message}


async def supervise(
    chief: Any,
    message: str,
    on_event: EventCallback,
    *,
    brigade: str,
    spec: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
    limits: Limits | None = None,
    contexto: str = "",
) -> tuple[str, list[dict]] | None:
    """Corre `chief.run(message)` vigilado. Devuelve lo mismo que `run`, o None si el watchdog cortó la corrida
    (en ese caso ya emitió su evento `watchdog` y un `final` que cierra el feed)."""
    extra = {"contexto": contexto} if contexto else {}  # solo viaja si hay (DAG): un jefe sin ese parámetro no lo recibe
    if not enabled():
        return await chief.run(message, on_event=on_event, **extra)
    lim = limits or limits_for(spec)
    mon = RunMonitor(lim, clock)
    chief_name = getattr(getattr(chief, "config", None), "name", brigade)

    async def watched(ev: dict) -> None:
        n_before = len(mon.reported)
        mon.observe(ev)
        await on_event(ev)
        for v in mon.reported[n_before:]:  # el jefe cortó a un ayudante: se informa
            who = f"ayudante {mon.helper or '?'}"
            iv = Intervention(time.time(), brigade, who, v.kind, "reported", v.detail,
                              f"el {who} cayó por {KIND_TEXT[v.kind]} (lo cortó el jefe): {v.detail}")
            await on_event(_event(_record(iv)))

    task = asyncio.create_task(chief.run(message, on_event=watched, **extra))
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=lim.poll)
            if done:
                return task.result()
            v = mon.check()
            if v is None:
                continue
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)  # espera a que termine de cancelarse
            target = f"ayudante {mon.helper}" if mon.helper else f"jefe {chief_name}"
            try:  # el tablero de efímeros en vivo anota por qué lo cortamos
                from brigades import live

                live.mark_cut(brigade, f"{KIND_TEXT[v.kind]}: {v.detail}")
            except Exception:  # noqa: BLE001
                pass
            iv = Intervention(time.time(), brigade, target, v.kind, "cut", v.detail,
                              f"el watchdog cortó al {target} por {KIND_TEXT[v.kind]}: {v.detail}")
            await on_event(_event(_record(iv)))
            text = iv.message[0].upper() + iv.message[1:]
            await on_event({"type": "final", "reply": f"{text}. La corrida se interrumpió; podés reintentar.",
                            "origen": "watchdog", "literal": True})
            return None
    finally:
        if not task.done():  # el cliente se fue / se canceló el turno: no dejar la corrida huérfana
            task.cancel()
