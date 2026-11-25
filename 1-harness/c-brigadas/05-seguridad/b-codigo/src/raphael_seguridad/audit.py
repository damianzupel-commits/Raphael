"""Auditor de código (defensa): el flujo E1 a E7 sobre un repo que Damián autorizó. Solo lee; nunca modifica ni ejecuta."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config_check import check_config
from .deps import AdvisorySource, OffSource, scan_deps
from .models import ScanResult, finding, sort_findings
from .secrets_scan import iter_files, scan_secrets
from .triage import triage


def run_audit(root: str | Path, source: AdvisorySource | None = None, *, now: datetime | None = None,
              previous: ScanResult | None = None) -> ScanResult:
    """E1 inventario · E2 secretos · E3 dependencias · E4 configuración · E5 triage · E6 convergencia · E7 reporte (ver report.py)."""
    root = Path(root).resolve()
    res = ScanResult(str(root), (now or datetime.now()).isoformat(timespec="seconds"))

    def step(name: str, state: str = "ok", detail: str = "") -> None:
        res.steps.append({"step": name, "state": state, "detail": detail})

    if not root.is_dir():
        step("E1 inventario", "error", f"no existe la carpeta {root}")
        return res
    files = list(iter_files(root))
    step("E1 inventario", detail=f"{len(files)} archivos")
    items = scan_secrets(root, files)
    step("E2 secretos", detail=f"{len(items)} posibles")
    n = len(items)
    deps_found, skipped = scan_deps(root, files, source or OffSource())
    items += deps_found
    if skipped:
        res.skipped["dependencias"] = skipped
    step("E3 dependencias", "omitido" if skipped else "ok", skipped or f"{len(deps_found)} avisos")
    n = len(items)
    items += check_config(root, files)
    step("E4 configuración", detail=f"{len(items) - n} hallazgos")
    res.findings = sort_findings(triage(items))
    closed = sum(1 for f in res.findings if f.status != "open")
    step("E5 triage", detail=f"{closed} bajados de {len(res.findings)}")
    if previous is not None:
        old = {f.id for f in previous.findings if f.status == "open"}
        now_ids = {f.id for f in res.findings if f.status == "open"}
        new, fixed = sorted(now_ids - old), sorted(old - now_ids)
        step("E6 convergencia", detail=f"{len(new)} nuevos, {len(fixed)} corregidos desde la corrida anterior")
        for f in res.findings:
            if f.id in new and f.status == "open" and f.severity in ("critical", "high"):
                f.message += " (nuevo desde la última auditoría)"
    else:
        step("E6 convergencia", "omitido", "primera auditoría de este repo")
    if not any(f.status == "open" for f in res.findings):
        res.findings.append(finding("secretos", ".", 0, "info", "limpio", "No se encontraron hallazgos abiertos"))
        res.findings[-1].status = "open"
    step("E7 reporte", detail="listo")
    return res
