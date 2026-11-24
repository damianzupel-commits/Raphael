"""Registro de actividad de Cerebro — "lo que hizo solo".

Cada vez que Cerebro hace algo por iniciativa propia (reindexar, consolidar, escribir
una nota de conclusión), lo anota acá. La vista de Cerebro en la Suite lo muestra como
feed "lo que hizo mientras no estabas". Persistido en data/cerebro_activity.json.
Best-effort: si el disco falla, no rompe la tarea proactiva.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "cerebro_activity.json"
_LOCK = threading.Lock()
_CAP = 200


def _load() -> list[dict]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        return []


def log(action: str, detail: str = "", meta: dict | None = None) -> None:
    """Anota una acción proactiva de Cerebro. `action`: reindex | consolidacion |
    conclusion | info. `detail`: texto corto para el feed."""
    with _LOCK:
        items = _load()
        items.insert(0, {"action": action, "detail": detail[:400], "meta": meta or {}, "ts": time.time()})
        del items[_CAP:]
        try:
            _PATH.parent.mkdir(parents=True, exist_ok=True)
            _PATH.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def recent(limit: int = 40) -> list[dict]:
    return _load()[: max(1, min(limit, _CAP))]
