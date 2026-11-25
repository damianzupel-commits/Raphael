"""Transporte real: internet con urllib (sin dependencias nuevas), caché por URL y fail-soft.

Si la fuente falla, devuelve la última copia del caché (aunque esté vencida) o None; nunca levanta una excepción.
El AIS (barcos) es un WebSocket: necesita la librería opcional `websockets`; si falta, avisa qué instalar.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from collections.abc import Mapping

from .base import Fuentes

UA = "Raphael-Geolocalizacion/1.0"


class HttpReal:
    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[float, str]] = {}

    def __call__(self, url: str, *, ttl: float = 60.0, timeout: float = 15.0, data: bytes | None = None,
                 headers: dict | None = None) -> str | None:
        key = (url, data)
        ahora = time.time()
        hit = self._cache.get(key)
        if hit and ahora - hit[0] < ttl:
            return hit[1]
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 -- URLs fijas de APIs públicas
                raw = resp.read().decode("utf-8", "replace")
        except (OSError, ValueError):   # URLError, timeout, HTTP error, URL inválida
            return hit[1] if hit else None
        self._cache[key] = (ahora, raw)
        return raw


class FuentesReales(Fuentes):
    def __init__(self, env: Mapping[str, str] | None = None, http=None) -> None:
        super().__init__(env, http or HttpReal())

    def _ais(self, segundos: float) -> list[dict]:
        try:
            import websockets  # type: ignore[import-not-found]
        except ImportError:
            raise RuntimeError("Falta la librería 'websockets' para la capa de barcos (pip install websockets).") from None
        sub = json.dumps({"APIKey": self.clave("barcos"), "BoundingBoxes": [[[-90.0, -180.0], [90.0, 180.0]]],
                          "FilterMessageTypes": ["PositionReport"]})

        async def leer() -> list[dict]:
            out: list[dict] = []
            fin = time.monotonic() + segundos
            async with websockets.connect("wss://stream.aisstream.io/v0/stream", open_timeout=10) as ws:
                await ws.send(sub)
                while (resto := fin - time.monotonic()) > 0:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=resto)
                    except TimeoutError:
                        break
                    try:
                        out.append(json.loads(raw))
                    except ValueError:
                        continue
            return out

        try:
            return asyncio.run(leer())
        except Exception as exc:   # noqa: BLE001 -- red, clave inválida o servidor: se avisa, no se rompe
            raise RuntimeError(f"AISStream no respondió ({type(exc).__name__}).") from None
