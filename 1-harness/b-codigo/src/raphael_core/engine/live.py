"""Tablero en vivo de los efímeros: quién nació, qué está haciendo y cómo terminó. Portado de JarvisRemote
(`brigades/live.py`). Diferencia: es una INSTANCIA (una por runtime), no un global del módulo, así dos runtimes (o dos
tests) no se pisan. Lo lee el panel ("Ayudantes efímeros") y el `status()` del runtime."""

from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

_TASK_CHARS = 140


class LiveBoard:
    def __init__(self, recent: int = 12, clock: Callable[[], float] = time.time) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._active: dict[int, dict[str, Any]] = {}
        self._recent: deque[dict[str, Any]] = deque(maxlen=recent)
        self._clock = clock

    def start(self, brigade: str, brigade_name: str, helper: str, mode: str, model: str, task: str) -> int:
        now = self._clock()
        token = next(self._ids)
        with self._lock:
            self._active[token] = {
                "id": token, "brigade": brigade, "brigade_name": brigade_name, "helper": helper, "mode": mode,
                "model": model, "task": (task or "").strip().replace("\n", " ")[:_TASK_CHARS],
                "since": now, "last_event": now, "tool": None, "args": "", "steps": 0,
            }
        return token

    def touch(self, token: int, ev: dict) -> None:
        with self._lock:
            e = self._active.get(token)
            if e is None:
                return
            e["last_event"] = self._clock()
            kind = ev.get("type")
            if kind == "tool":
                e["tool"], e["args"] = str(ev.get("name") or ""), str(ev.get("args") or "")[:100]
                e["steps"] += 1
            elif kind == "tool_result":
                e["tool"], e["args"] = None, ""      # terminó la tool: vuelve a "pensando"

    def finish(self, token: int, outcome: str = "ok", detail: str = "") -> None:
        with self._lock:
            e = self._active.pop(token, None)
            if e is None:
                return
            now = self._clock()
            keep = ("id", "brigade", "brigade_name", "helper", "mode", "model", "task", "since", "steps")
            self._recent.appendleft({**{k: e[k] for k in keep}, "until": now, "seconds": round(now - e["since"], 1),
                                     "outcome": outcome, "detail": detail[:160]})

    def mark_cut(self, brigade: str, reason: str) -> None:
        """El watchdog cortó la corrida: anota el motivo en el reciente más nuevo de esa brigada."""
        with self._lock:
            for r in self._recent:
                if r["brigade"] == brigade:
                    r["outcome"], r["detail"] = "cortado por el watchdog", reason[:160]
                    return

    def snapshot(self, brigade: str | None = None) -> dict[str, Any]:
        """Activos (los más viejos primero) y los últimos que terminaron; `brigade` filtra a una sola."""
        now = self._clock()
        with self._lock:
            active = sorted(({**e, "seconds": round(now - e["since"], 1), "idle": round(now - e["last_event"], 1)}
                             for e in self._active.values() if brigade in (None, e["brigade"])), key=lambda x: x["since"])
            recent = [r for r in self._recent if brigade in (None, r["brigade"])]
        return {"now": now, "active": active, "recent": recent}
