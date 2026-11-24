"""Fuentes de ingesta + registro de lo ingerido (2026-10-12, pedido de Damian).

Persiste en un JSON (backend/data/ingestion_sources.json) para que sobreviva reinicios:
 - watchlist: URLs de playlists/canales de YouTube que el usuario agregó para que se
   ingieran solas (además de la playlist histórica de PLAYLIST_WATCH_URL).
 - recent: últimos ítems ingeridos {title, url, type, ts}, para mostrarlos con su link
   en el panel (brigada Ingesta).

Best-effort: si el disco falla, no rompe la ingesta (devuelve vacío / no persiste).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "data" / "ingestion_sources.json"
_LOCK = threading.Lock()
_RECENT_CAP = 30


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- no existe aún / json inválido -> estado vacío
        return {"watchlist": [], "recent": []}


def _save(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 -- persistencia best-effort
        pass


def list_sources() -> list[str]:
    return list(_load().get("watchlist", []))


def add_source(url: str) -> list[str]:
    url = (url or "").strip()
    with _LOCK:
        data = _load()
        wl = data.setdefault("watchlist", [])
        if url and url not in wl:
            wl.append(url)
        _save(data)
        return list(wl)


def remove_source(url: str) -> list[str]:
    url = (url or "").strip()
    with _LOCK:
        data = _load()
        wl = [u for u in data.get("watchlist", []) if u != url]
        data["watchlist"] = wl
        _save(data)
        return list(wl)


def log_ingested(title: str, url: str, kind: str = "youtube") -> None:
    """Registra un ítem recién ingerido (más nuevo primero, con tope)."""
    with _LOCK:
        data = _load()
        rec = data.setdefault("recent", [])
        rec.insert(0, {"title": title or url, "url": url, "type": kind, "ts": time.time()})
        del rec[_RECENT_CAP:]
        _save(data)


def recent_ingested(limit: int = 20) -> list[dict]:
    return _load().get("recent", [])[:limit]


def snapshot() -> dict:
    """Lo que devuelve GET /api/ingest: fuentes auto-ingeridas + últimos ítems ingeridos."""
    data = _load()
    return {"sources": data.get("watchlist", []), "recent": data.get("recent", [])[:20]}
