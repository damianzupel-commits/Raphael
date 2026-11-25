"""Reporte (E7): texto en español rioplatense, ordenado por severidad, con evidencia tachada y cómo corregir."""

from __future__ import annotations

from .models import SEVERITIES, ScanResult

ES = {"critical": "CRÍTICO", "high": "ALTO", "medium": "MEDIO", "low": "BAJO", "info": "INFO"}


def summary_line(res: ScanResult) -> str:
    c = res.counts()
    total = sum(c.values())
    if total == 0 or (total == 1 and any(f.rule_id == "limpio" for f in res.findings)):
        return "Auditoría sin hallazgos abiertos."
    return "Hallazgos abiertos: " + ", ".join(f"{c[s]} {ES[s].lower()}" for s in SEVERITIES if c[s])


def render(res: ScanResult) -> str:
    lines = [f"# Auditoría de {res.root}", f"Hecha el {res.at}. {summary_line(res)}", ""]
    sim = any(f.simulated for f in res.findings)
    if sim:
        lines += ["> ⚠ Incluye datos SIMULADOS (adaptador de prueba). No son vulnerabilidades reales.", ""]
    for why in res.skipped.values():
        lines.append(f"> Ojo: {why}.")
    if res.skipped:
        lines.append("")
    lines.append("## Pasos")
    lines += [f"- {s['step']}: {s['state']}" + (f" ({s['detail']})" if s["detail"] else "") for s in res.steps]
    lines.append("")
    for sev in SEVERITIES:
        group = [f for f in res.findings if f.severity == sev and f.status == "open" and f.rule_id != "limpio"]
        if not group:
            continue
        lines.append(f"## {ES[sev]} ({len(group)})")
        for f in group:
            where = f"{f.file}:{f.line}" if f.line else f.file
            lines.append(f"- **{f.rule_id}** en `{where}`: {f.message}" + (" [SIMULADO]" if f.simulated else ""))
            if f.evidence:
                lines.append(f"  - evidencia: `{f.evidence}`")
            if f.fix:
                lines.append(f"  - cómo corregirlo: {f.fix}")
        lines.append("")
    lowered = [f for f in res.findings if f.status != "open"]
    if lowered:
        lines.append(f"## Revisados y bajados ({len(lowered)})")
        lines += [f"- `{f.file}:{f.line}` {f.rule_id}: {f.reasoning}" for f in lowered]
    return "\n".join(lines).rstrip() + "\n"
