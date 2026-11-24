"""Registro VIVO de los ayudantes EFÍMEROS que están corriendo ahora mismo (en este proceso).

Liviano a propósito (solo biblioteca estándar, sin importar nada del backend): el motor genérico (`engine.py`) registra al
spawnear un ayudante y lo quita al terminar (ok, timeout, error o cancelado por el watchdog). La vista "Efímeros en vivo" del
orquestador lo consulta por polling (`GET /api/efimeros`). Terminología de Damian: "cocineros" = agentes permanentes de una
brigada; "efímeros" = ayudantes que se crean por tarea y mueren.

Es solo observación: no corta nada ni toca ningún gate (cortar es del watchdog, que además anota acá por qué lo cortó).
Alcance: el proceso donde corren los jefes (el orquestador). Un efímero lanzado desde otro proceso no aparece acá.
"""

from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from typing import Any

_LOCK = threading.Lock()
_IDS = itertools.count(1)
_ACTIVE: dict[int, dict[str, Any]] = {}
_RECENT: deque[dict[str, Any]] = deque(maxlen=12)
_TASK_CHARS = 140


def start(brigade: str, brigade_name: str, helper_id: str, modo: str, modelo: str, tarea: str) -> int:
    """Registra un efímero que acaba de nacer. Devuelve su token (para `touch` / `finish`)."""
    now = time.time()
    token = next(_IDS)
    with _LOCK:
        _ACTIVE[token] = {
            "id": token, "brigada": brigade, "brigada_nombre": brigade_name, "ayudante": helper_id, "modo": modo,
            "modelo": modelo, "tarea": (tarea or "").strip().replace("\n", " ")[:_TASK_CHARS],
            "desde": now, "ultimo_evento": now, "tool": None, "args": "", "pasos": 0,
        }
    return token


def touch(token: int, ev: dict) -> None:
    """Actualiza qué está haciendo, a partir de un evento del feed del ayudante (start / tool / tool_result / final)."""
    with _LOCK:
        e = _ACTIVE.get(token)
        if e is None:
            return
        e["ultimo_evento"] = time.time()
        kind = ev.get("type")
        if kind == "tool":
            e["tool"], e["args"] = str(ev.get("name") or ""), str(ev.get("args") or "")[:100]
            e["pasos"] += 1
        elif kind == "tool_result":
            e["tool"], e["args"] = None, ""  # terminó la tool: vuelve a "pensando"


def finish(token: int, outcome: str = "ok", detail: str = "") -> None:
    """Quita al efímero del tablero de activos y lo deja en los recientes con cómo terminó."""
    with _LOCK:
        e = _ACTIVE.pop(token, None)
        if e is None:
            return
        now = time.time()
        _RECENT.appendleft({**{k: e[k] for k in ("id", "brigada", "brigada_nombre", "ayudante", "modo", "modelo", "tarea", "desde", "pasos")},
                            "hasta": now, "segundos": round(now - e["desde"], 1), "resultado": outcome, "detalle": detail[:160]})


def mark_cut(brigade: str, reason: str) -> None:
    """El watchdog cortó la corrida de `brigade`: anota el motivo en el reciente más nuevo de esa brigada."""
    with _LOCK:
        for r in _RECENT:
            if r["brigada"] == brigade:
                r["resultado"], r["detalle"] = "cortado por el watchdog", reason[:160]
                return


def snapshot() -> dict[str, Any]:
    """Foto del tablero: activos (los más viejos primero) y los últimos que terminaron."""
    now = time.time()
    with _LOCK:
        activos = sorted(({**e, "segundos": round(now - e["desde"], 1), "inactivo": round(now - e["ultimo_evento"], 1)}
                          for e in _ACTIVE.values()), key=lambda x: x["desde"])
        return {"ahora": now, "activos": activos, "recientes": list(_RECENT)}


def reset() -> None:
    """Solo para tests."""
    with _LOCK:
        _ACTIVE.clear()
        _RECENT.clear()
