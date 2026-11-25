"""Guardrail de alcance del pentest activo: rechazo duro ANTES de tocar la red.

Por default solo se puede apuntar a redes privadas (RFC 1918), loopback y Tailscale. Cualquier otra cosa tiene que estar
en `authorized_targets.yaml`, que edita Damián a mano. Este módulo SOLO LEE ese archivo: no existe ninguna función que lo
escriba, y un "sí" en el chat no autoriza nada (ni una tool ni un modelo lo pueden ampliar). Un hostname se resuelve acá y
se devuelve la IP ya validada: quien escanea usa esa IP, nunca vuelve a resolver el nombre (cierra el DNS rebinding).
Actuar sobre sistemas ajenos sin permiso puede ser delito (Ley 26.388 en Argentina): verificar con fuente vigente."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import yaml

Net = ipaddress.IPv4Network | ipaddress.IPv6Network

DEFAULT_SCOPE: tuple[Net, ...] = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "100.64.0.0/10", "::1/128"))


class TargetNotAuthorized(PermissionError):
    pass


def _resolve_host(host: str) -> str:
    return socket.gethostbyname(host)


def load_authorized(path: str | Path | None) -> list[Net]:
    """Lee la lista de Damián. Archivo ausente o roto = sin ampliaciones (nunca alcance abierto por un error)."""
    if not path or not Path(path).is_file():
        return []
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return []
    out: list[Net] = []
    for entry in (data.get("targets") or []) if isinstance(data, dict) else []:
        raw = entry.get("target") if isinstance(entry, dict) else None
        try:
            out.append(ipaddress.ip_network(str(raw).strip(), strict=False))
        except ValueError:
            continue
    return out


def host_of(target: str) -> str:
    """Acepta IP, CIDR, hostname o URL y devuelve solo el host."""
    t = target.strip()
    if "://" in t:
        t = urlparse(t).hostname or ""
    return t


def authorize(target: str, authorized_file: str | Path | None = None, *,
              resolver: Callable[[str], str] | None = None) -> str:
    """Devuelve la IP o el CIDR validado (para usar tal cual) o lanza TargetNotAuthorized. Un CIDR se valida entero."""
    host = host_of(target)
    if not host or any(c in host for c in " \t\r\n\0;|&$`<>'\""):
        raise TargetNotAuthorized(f"objetivo inválido: {target!r}")
    resolved: str | None = None
    try:
        net = ipaddress.ip_network(host, strict=False)
    except ValueError:
        try:
            resolved = (resolver or _resolve_host)(host)
            net = ipaddress.ip_network(resolved)
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            raise TargetNotAuthorized(f"'{target}' no es una IP, un CIDR ni un nombre que resuelva") from exc
    allowed = [*DEFAULT_SCOPE, *load_authorized(authorized_file)]
    if not any(net.version == a.version and net.subnet_of(a) for a in allowed):
        raise TargetNotAuthorized(
            f"'{target}' ({net}) está fuera del alcance: solo red privada, loopback y Tailscale, más lo que Damián "
            "puso a mano en authorized_targets.yaml. Aprobar en el chat no alcanza.")
    return resolved if resolved is not None else str(net) if "/" in host else host
