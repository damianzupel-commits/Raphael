"""Solo URLs públicas. En el VPS una URL a `localhost`, a la red interna o al servicio de metadatos de la nube sería
una puerta a lo que no es público (SSRF): se rechaza antes de pedir nada, y también en cada redirección."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from .model import SourceError


def validate_public_url(url: str, resolve=socket.getaddrinfo) -> str:
    """Devuelve la URL limpia o levanta `SourceError`. `resolve` se inyecta para probar sin red."""
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("http", "https"):
        raise SourceError("solo se aceptan direcciones http o https")
    host = parts.hostname or ""
    if not host:
        raise SourceError("la dirección no tiene sitio")
    if parts.username or parts.password:
        raise SourceError("no se aceptan direcciones con usuario y clave")
    try:
        infos = resolve(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        raise SourceError("no pude resolver el sitio", retriable=True) from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise SourceError("esa dirección apunta a una red privada o local: solo ingiero sitios públicos")
    return parts.geturl()
