"""Mapa de inteligencia geoespacial de Raphael (2026-10-13).

Guarda los puntos geolocalizados que Raphael va juntando (IPs de ip_geolocate, evidencia
con GPS, targets del cyber range…) para plotearlos en el globo 3D (/globo). Inspirado en
God's Eye View (MIT) pero código 100% propio: no copiamos nada, solo la idea del "globo con
tu propia inteligencia encima".

Store en memoria + persistencia liviana a disco (sobrevive reinicios) + broadcast por WebSocket
para que un punto nuevo aparezca en el globo EN VIVO (mismo patrón que mission_control).

SOLO datos públicos de infraestructura (de dónde sale una IP/servidor), nunca vigilancia de
personas — misma línea ética que el resto del OSINT del proyecto.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

_PATH = Path(__file__).resolve().parent.parent / "data" / "geo_intel.json"
_LOCK = threading.Lock()
_CAP = 500

_subs: list[Any] = []


def register(ws: Any) -> None:
    _subs.append(ws)


def unregister(ws: Any) -> None:
    try:
        _subs.remove(ws)
    except ValueError:
        pass


def subscriber_count() -> int:
    return len(_subs)


def _load() -> list[dict]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8")).get("points", [])
    except Exception:  # noqa: BLE001
        return []


def _save(points: list[dict]) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps({"points": points}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def list_points(limit: int = _CAP) -> list[dict]:
    return _load()[:limit]


def snapshot() -> dict:
    return {"points": _load()}


def add_point(lat: float, lon: float, label: str, kind: str = "ip", meta: dict | None = None) -> dict | None:
    """Agrega un punto geolocalizado y lo re-emite al globo en vivo. Devuelve el punto, o None
    si lat/lon no son válidos. Best-effort."""
    try:
        la = float(lat)
        lo = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0) or (la == 0.0 and lo == 0.0):
        return None  # fuera de rango o (0,0) = geolocalización fallida
    point = {
        "id": uuid.uuid4().hex[:12],
        "lat": round(la, 5),
        "lon": round(lo, 5),
        "label": (label or "punto")[:120],
        "kind": kind,
        "meta": meta or {},
        "ts": time.time(),
    }
    with _LOCK:
        points = _load()
        points.insert(0, point)  # más nuevo primero
        del points[_CAP:]
        _save(points)
    # Broadcast en vivo si hay un loop corriendo (si no, el punto igual queda guardado).
    try:
        asyncio.get_running_loop().create_task(_broadcast({"type": "point", **point}))
    except RuntimeError:
        pass
    return point


# --- Capa de vuelos en vivo (ADS-B público, estilo God's Eye View) --------------------------
# Datos públicos de OpenSky (sin API key; anónimo, rate-limiteado). Se trae server-side para
# evitar CORS en el navegador. Cacheado ~15s para no pegarle de más. Son posiciones AGREGADAS
# que las aeronaves transmiten por ADS-B — OSINT de tráfico aéreo, no seguimiento de personas.
_flights_cache: dict = {"ts": 0.0, "data": []}
_FLIGHTS_TTL = 15.0
_OPENSKY_URL = "https://opensky-network.org/api/states/all"


def fetch_flights(max_aircraft: int = 2000) -> list[dict]:
    now = time.time()
    if now - _flights_cache["ts"] < _FLIGHTS_TTL and _flights_cache["data"]:
        return _flights_cache["data"]
    try:
        import urllib.request

        req = urllib.request.Request(_OPENSKY_URL, headers={"User-Agent": "JarvisRemote-Globo/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310 -- URL fija pública
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 -- best-effort; si OpenSky falla, capa vacía
        return _flights_cache["data"]
    out: list[dict] = []
    for s in raw.get("states") or []:
        try:
            lon, lat, on_ground = s[5], s[6], s[8]
            if lon is None or lat is None or on_ground:
                continue
            out.append({
                "lat": round(float(lat), 4), "lon": round(float(lon), 4),
                "cs": (s[1] or "").strip(), "pais": s[2], "alt": s[7], "vel": s[9],
            })
            if len(out) >= max_aircraft:
                break
        except Exception:  # noqa: BLE001
            continue
    _flights_cache["ts"] = now
    _flights_cache["data"] = out
    return out


async def _broadcast(payload: dict, send: Callable[[Any, dict], Awaitable[None]] | None = None) -> int:
    sent = 0
    dead: list[Any] = []
    for ws in list(_subs):
        try:
            if send is not None:
                await send(ws, payload)
            else:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            sent += 1
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        unregister(ws)
    return sent
