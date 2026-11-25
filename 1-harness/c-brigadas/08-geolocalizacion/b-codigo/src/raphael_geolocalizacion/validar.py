"""Validación y limpieza de lo que entra: coordenadas, IPs, dominios, direcciones cripto y texto de terceros.

Regla de la brigada: solo infraestructura pública. Una IP privada o de loopback no se geolocaliza (no es infraestructura
pública y, además, no devuelve nada útil). El texto que viene de fuentes externas (títulos de noticias, nombres de
cámaras, nombres de barcos) es DATO: se limpia y se acota, nunca se interpreta como instrucción.
"""

from __future__ import annotations

import ipaddress
import re

_HOST = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
BTC = re.compile(r"^(bc1[0-9a-z]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def coordenadas(lat, lon) -> tuple[float, float] | None:
    """(lat, lon) redondeadas, o None si no son válidas. (0, 0) es una geolocalización fallida: se descarta."""
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0) or (la == 0.0 and lo == 0.0):
        return None
    return round(la, 5), round(lo, 5)


def limpiar(texto, n: int = 120) -> str:
    """Texto de un tercero: sin caracteres de control, en una línea y acotado."""
    return " ".join(_CONTROL.sub(" ", str(texto or "")).split())[:n].strip()


def objetivo_ip(texto: str) -> tuple[str | None, str]:
    """(objetivo normalizado, motivo). Objetivo = IP pública o dominio; si no sirve, None y el motivo en español."""
    t = (texto or "").strip().strip("<>[]()\"'").rstrip(".,;")
    if not t:
        return None, "Falta la IP o el dominio."
    try:
        ip = ipaddress.ip_address(t)
    except ValueError:
        host = t.lower().removeprefix("http://").removeprefix("https://").split("/")[0].split(":")[0]
        if _HOST.match(host):
            return host, ""
        return None, f"«{limpiar(t, 60)}» no parece una IP ni un dominio."
    if not ip.is_global:
        return None, f"{ip} es una dirección privada o reservada: solo geolocalizo infraestructura pública."
    return str(ip), ""


def direccion_cripto(texto: str) -> tuple[str | None, str | None]:
    """(dirección, cadena) con la cadena 'ethereum' o 'bitcoin', o (None, None) si no se reconoce."""
    t = (texto or "").strip()
    if ETH.match(t):
        return t, "ethereum"
    if BTC.match(t):
        return t, "bitcoin"
    return None, None
