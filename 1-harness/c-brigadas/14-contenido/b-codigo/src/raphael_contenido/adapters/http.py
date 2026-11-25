"""HTTP mínimo con stdlib para los adaptadores: una función `http(method, url, *, data, json_body, headers, body, timeout)`
que devuelve el JSON como dict. Los tests le pasan una función falsa con la misma forma y no tocan la red."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

Http = Callable[..., dict]


class ServicioError(Exception):
    """Un servicio externo falló o no contestó. El mensaje se le puede mostrar a la persona tal cual (sin claves)."""


def http(method: str, url: str, *, data: dict | None = None, json_body: Any = None, headers: dict | None = None,
         body: bytes | None = None, timeout: float = 60) -> dict:
    hdr = dict(headers or {})
    if json_body is not None:
        payload = json.dumps(json_body).encode()
        hdr.setdefault("Content-Type", "application/json")
    elif body is not None:
        payload = body
    elif data is not None:
        payload = urllib.parse.urlencode(data).encode()
    else:
        payload = None
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise ServicioError("Solo se habla con servicios por https (o con ComfyUI en esta misma PC).")
    req = urllib.request.Request(url, data=payload, method=method, headers=hdr)  # noqa: S310 - esquema validado arriba
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise ServicioError(f"El servicio respondió {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from None
    except OSError as exc:
        raise ServicioError(f"No pude hablar con el servicio: {exc}") from None
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {"raw": raw[:300]}


def mask(text: str, *secrets: str) -> str:
    """Tacha las claves de un mensaje de error antes de mostrarlo o guardarlo."""
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text
