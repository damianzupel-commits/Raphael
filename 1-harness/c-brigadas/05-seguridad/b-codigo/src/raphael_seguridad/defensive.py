"""Vigilancia defensiva: mira la propia instalación y avisa. Solo lectura y pasivo, también en el VPS.

Chequeos: intentos de login fallidos, tokens por vencer, certificado TLS, servicio caído y backups viejos.
Las sondas (certificado, servicio, backup) son un adaptador: la real toca solo el host propio que está en la config;
la simulada devuelve lo que le pasen."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from .models import Finding, finding


class Probes(Protocol):
    simulated: bool

    def tls_days_left(self, host: str, port: int) -> int | None: ...
    def service_up(self, url: str) -> bool: ...
    def backup_age_hours(self, path: str) -> float | None: ...


class RealProbes:
    simulated = False

    def tls_days_left(self, host, port):
        try:
            with socket.create_connection((host, port), timeout=8) as raw, \
                    ssl.create_default_context().wrap_socket(raw, server_hostname=host) as s:
                exp = datetime.strptime(s.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z")
            return (exp - datetime.utcnow()).days
        except (OSError, ssl.SSLError, KeyError, ValueError):
            return None

    def service_up(self, url):
        try:
            return httpx.get(url, timeout=8).status_code < 500
        except httpx.HTTPError:
            return False

    def backup_age_hours(self, path):
        files = [p for p in Path(path).rglob("*") if p.is_file()] if Path(path).is_dir() else []
        if not files:
            return None
        return (datetime.now().timestamp() - max(p.stat().st_mtime for p in files)) / 3600


@dataclass
class MockProbes:
    simulated = True
    tls: dict = field(default_factory=dict)        # host -> días
    up: dict = field(default_factory=dict)         # url -> bool
    backups: dict = field(default_factory=dict)    # ruta -> horas

    def tls_days_left(self, host, port):
        return self.tls.get(host)

    def service_up(self, url):
        return self.up.get(url, True)

    def backup_age_hours(self, path):
        return self.backups.get(path)


def probes_from_env(env: dict[str, str]) -> Probes:
    return MockProbes() if (env.get("SEGURIDAD_WATCH_ADAPTER") or "real").lower() == "mock" else RealProbes()


def failed_login_alerts(events: list[dict], now: datetime, *, window_min: int = 10, threshold: int = 5) -> list[Finding]:
    """`events` = [{'at': iso, 'source': ip o canal}]. Alerta cuando una misma fuente pasa el umbral en la ventana."""
    since = now - timedelta(minutes=window_min)
    counts: dict[str, int] = {}
    for e in events:
        try:
            at = datetime.fromisoformat(e["at"])
        except (KeyError, ValueError):
            continue
        if at >= since:
            counts[e.get("source", "?")] = counts.get(e.get("source", "?"), 0) + 1
    return [finding("vigilancia", src, 0, "high" if n >= threshold * 3 else "medium", "login-fallido",
                    f"{n} intentos de acceso fallidos desde {src} en {window_min} minutos", evidence=str(n),
                    fix="Mirá si es la dueña; si no, bloqueá esa fuente y cambiá la clave de la app.")
            for src, n in counts.items() if n >= threshold]


def token_alerts(tokens: list[dict], today: date, *, warn_days: int = 14) -> list[Finding]:
    """`tokens` = [{'name': 'Token de Meta', 'expires': '2027-01-31'}] de la config (no se leen valores de claves)."""
    out = []
    for t in tokens:
        try:
            left = (date.fromisoformat(str(t["expires"])) - today).days
        except (KeyError, ValueError):
            continue
        if left <= warn_days:
            out.append(finding("vigilancia", t.get("name", "token"), 0, "high" if left <= 3 else "medium", "token-por-vencer",
                               f"{t.get('name', 'un token')} " + (f"vence en {left} días" if left >= 0 else f"venció hace {-left} días"),
                               fix="Renovalo y cargá el nuevo en la pantalla de Configuración."))
    return out


def run_watch(cfg: dict, probes: Probes, now: datetime, login_events: list[dict]) -> list[Finding]:
    """Corre todos los chequeos que la config tenga armados. Lo que no está configurado no se mira (y no se inventa)."""
    out = failed_login_alerts(login_events, now, window_min=int(cfg.get("login_window_minutes", 10)),
                              threshold=int(cfg.get("login_threshold", 5)))
    out += token_alerts(cfg.get("tokens") or [], now.date(), warn_days=int(cfg.get("token_warn_days", 14)))
    for host in cfg.get("tls_hosts") or []:
        h, _, port = str(host).partition(":")
        days = probes.tls_days_left(h, int(port or 443))
        if days is None:
            out.append(finding("vigilancia", str(host), 0, "high", "tls-ilegible", "no se pudo leer el certificado",
                               fix="Revisá que el servicio esté arriba y el certificado instalado.", simulated=probes.simulated))
        elif days <= int(cfg.get("tls_warn_days", 14)):
            out.append(finding("vigilancia", str(host), 0, "high" if days <= 3 else "medium", "tls-por-vencer",
                               f"el certificado de {host} vence en {days} días", fix="Renovalo (Caddy lo hace solo si el puerto 443 está abierto).",
                               simulated=probes.simulated))
    for url in cfg.get("services") or []:
        if not probes.service_up(url):
            out.append(finding("vigilancia", url, 0, "critical", "servicio-caido", f"{url} no responde",
                               fix="Mirá el log del servidor y reinicialo.", simulated=probes.simulated))
    for path in cfg.get("backups") or []:
        age = probes.backup_age_hours(path)
        if age is None:
            out.append(finding("vigilancia", path, 0, "high", "backup-ausente", "no hay copias de seguridad en la carpeta",
                               fix="Verificá que el job de backup corra.", simulated=probes.simulated))
        elif age > float(cfg.get("backup_max_hours", 36)):
            out.append(finding("vigilancia", path, 0, "medium", "backup-viejo", f"la última copia tiene {int(age)} horas",
                               fix="Verificá que el job de backup corra.", simulated=probes.simulated))
    return out
