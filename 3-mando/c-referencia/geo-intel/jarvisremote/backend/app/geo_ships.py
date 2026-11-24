"""Capa de barcos / AIS (2026-10-13, batch amarillo).

AISStream.io es gratis pero es un **stream WebSocket** (no REST): mantenemos una conexión de
fondo, nos suscribimos al mundo entero y acumulamos la última posición de cada barco por MMSI.
El globo lee el snapshot (`points()`). Gateado por AISSTREAM_KEY (sin key, no arranca). Fail-soft:
si falla la conexión o falta la librería `websockets`, no rompe nada (capa vacía).

Datos AIS públicos de tráfico marítimo (los barcos transmiten su posición), no vigilancia de
personas.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from .config import settings

logger = logging.getLogger("jarvis.geo_ships")

_ships: dict[str, dict] = {}  # MMSI -> {lat, lon, name, ts}
_MAX_AGE = 1800.0  # 30 min: un barco que no reportó en ese tiempo se considera viejo
_CAP = 4000


def points() -> list[dict]:
    now = time.time()
    out = []
    for mmsi, s in list(_ships.items()):
        if now - s["ts"] > _MAX_AGE:
            _ships.pop(mmsi, None)
            continue
        out.append({"lat": s["lat"], "lon": s["lon"], "label": s.get("name") or f"MMSI {mmsi}"})
        if len(out) >= _CAP:
            break
    return out


async def ais_loop() -> None:
    """Tarea de vida larga (arrancada desde el startup de FastAPI). Mantiene el WS de AISStream
    y actualiza `_ships`. Reconecta con backoff. Default inactivo sin AISSTREAM_KEY."""
    if not settings.aisstream_key:
        logger.info("capa de barcos (AIS) inactiva: falta AISSTREAM_KEY")
        return
    try:
        import websockets  # type: ignore
    except Exception:  # noqa: BLE001
        logger.warning("capa de barcos (AIS): falta la librería 'websockets' (pip install websockets)")
        return

    sub = json.dumps({
        "APIKey": settings.aisstream_key,
        "BoundingBoxes": [[[-90.0, -180.0], [90.0, 180.0]]],
        "FilterMessageTypes": ["PositionReport"],
    })
    backoff = 5.0
    while True:
        try:
            async with websockets.connect("wss://stream.aisstream.io/v0/stream", ping_interval=20) as ws:
                await ws.send(sub)
                backoff = 5.0
                async for raw in ws:
                    try:
                        m = json.loads(raw)
                        md = m.get("MetaData") or {}
                        mmsi = md.get("MMSI")
                        la, lo = md.get("latitude"), md.get("longitude")
                        if mmsi is not None and la is not None and lo is not None:
                            _ships[str(mmsi)] = {
                                "lat": round(float(la), 4), "lon": round(float(lo), 4),
                                "name": (md.get("ShipName") or "").strip(), "ts": time.time(),
                            }
                    except Exception:  # noqa: BLE001 -- un mensaje raro no corta el stream
                        continue
        except Exception:  # noqa: BLE001
            logger.warning("capa de barcos (AIS): se cayó el stream, reconectando en %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
