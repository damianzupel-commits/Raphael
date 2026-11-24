"""Último 'rastro' de activación del recall asociativo, para que la UI lo muestre
en vivo sobre el grafo (2026-10-05).

Cuando Raphael recupera notas (spreading activation, ver [[spreading]], o búsqueda
normal), guarda acá qué nodos se activaron y con qué nivel. La pestaña Obsidian de la
tray-app pollea `GET /api/obsidian/activation` y enciende esos nodos en el grafo 3D
(ver tray-app/ui/web_assets/graph3d.html::setActivation). Así, si Damian está mirando
el grafo mientras habla con Raphael, VE el rastro de lo que Raphael trajo a la mente.

Es un único slot en memoria (el último rastro gana), con un número de secuencia para
que la UI detecte cuándo hay uno nuevo sin re-encender lo mismo. No se persiste: es
efímero por diseño (un rastro de atención, no un registro)."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_state: dict = {"seq": 0, "ts": 0.0, "query": "", "mode": "", "nodes": {}}


def record(query: str, mode: str, nodes: dict[str, float]) -> None:
    """Guarda el último rastro. `nodes` = {note_id: nivel 0..1}."""
    global _state
    with _lock:
        _state = {
            "seq": _state["seq"] + 1,
            "ts": time.time(),
            "query": query,
            "mode": mode,
            "nodes": {k: round(float(v), 3) for k, v in nodes.items()},
        }


def latest() -> dict:
    with _lock:
        return dict(_state)
