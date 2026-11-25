"""Tools de la brigada (las usan efímeros y el panel). Las arma `setup` con la edición y la config reales y cada una valida
edición y alcance ella misma, sin confiar en quien la llama.

Las de escaneo activo están declaradas `active_scan` en el manifiesto: el harness no las carga en la nube."""

from __future__ import annotations

import ipaddress
import socket

from .audit import run_audit
from .deps import source_from_env
from .pentest import run_pentest
from .report import render
from .settings import Settings


def local_network() -> dict:
    """La IP de esta PC en la red de casa y su red /24 (para escanear 'mi wifi'). No manda ningún paquete: un socket UDP
    'conectado' solo le pregunta al sistema por qué interfaz saldría."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
        try:
            sk.connect(("192.0.2.1", 9))      # dirección de documentación (RFC 5737): no se envía nada
            ip = sk.getsockname()[0]
        except OSError:
            return {"found": False, "error": "no pude saber la red local de esta PC (¿sin conexión?)"}
    net = ipaddress.ip_network(f"{ip}/24", strict=False)
    return {"found": True, "ip": ip, "network": str(net)}


def make_tools(edition: str, s: Settings) -> dict:
    def _run(kind: str, target: str, option: str) -> dict:
        found = run_pentest(kind, target, edition=edition, env=s.env, authorized_file=s.targets_file, option=option)
        return {"target": target, "findings": [f.to_dict() for f in found], "simulated": any(f.simulated for f in found)}

    def nmap_scan(target: str, preset: str = "quick") -> dict:
        """Escanea puertos con nmap (solo PC, solo objetivos autorizados)."""
        return _run("nmap", target, preset)

    def zap_scan(url: str, mode: str = "spider") -> dict:
        """Escaneo web con ZAP: 'spider' es pasivo, 'full' manda ataques (solo PC, solo objetivos autorizados)."""
        return _run("zap", url, mode)

    def sqlmap_scan(url: str) -> dict:
        """Detecta inyección SQL con sqlmap, sin volcar datos (solo PC, solo objetivos autorizados)."""
        return _run("sqlmap", url, "")

    def auditar_proyecto(repo: str) -> dict:
        """Auditoría estática de un repo de la lista autorizada; devuelve los conteos y el reporte."""
        res = run_audit(s.allowed_repo(repo), source_from_env(s.env))
        return {"counts": res.counts(), "report": render(res)}

    def red_local() -> dict:
        """La IP de esta PC y su red local (CIDR) para usarla de objetivo de nmap_scan. Solo lee, no escanea."""
        return local_network()

    return {"red_local": red_local, "nmap_scan": nmap_scan, "zap_scan": zap_scan, "sqlmap_scan": sqlmap_scan, "auditar_proyecto": auditar_proyecto}
