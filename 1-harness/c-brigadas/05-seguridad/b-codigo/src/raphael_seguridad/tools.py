"""Tools de la brigada (las usan efímeros y el panel). Las arma `setup` con la edición y la config reales y cada una valida
edición y alcance ella misma, sin confiar en quien la llama.

Las de escaneo activo están declaradas `active_scan` en el manifiesto: el harness no las carga en la nube."""

from __future__ import annotations

from .audit import run_audit
from .deps import source_from_env
from .pentest import run_pentest
from .report import render
from .settings import Settings


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

    return {"nmap_scan": nmap_scan, "zap_scan": zap_scan, "sqlmap_scan": sqlmap_scan, "auditar_proyecto": auditar_proyecto}
