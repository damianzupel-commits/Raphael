"""Autoconocimiento: qué brigadas tiene esta instalación, armado por CÓDIGO desde el catálogo del harness.

Portado de JarvisRemote `orquestador/agentes.py::reporte_del_sistema`. Antes salía de un registro fijo; ahora sale de
`ctx.catalog()` (lo montado, lo caído y por qué, lo que se puede montar). Ningún modelo interviene: el resultado es un
`InternalReport` y la voz lo comunica con el mismo control de fidelidad que cualquier otro reporte.
"""

from __future__ import annotations

from raphael_core.engine.reports import MAX_FINDING, MAX_FINDINGS, MAX_SUMMARY, REPORT_VERSION, InternalReport, clip

DRAFT_HINT = "Para crear una brigada nueva: /crear-brigada <descripción> (queda como borrador hasta que la actives)."


def _how(b: dict) -> str:
    return f"se usa con /{b['id']} o desde su pestaña"


def system_report(catalog: list[dict], *, drafts: list[str] | None = None, edition: str = "",
                  drafts_enabled: bool = True) -> InternalReport:
    """Un `InternalReport` con lo que el asistente ES hoy. `catalog` = `OrchestratorContext.catalog()`."""
    mounted = [b for b in catalog if b.get("mounted")]
    working = [b for b in mounted if not b.get("down")]
    down = [b for b in mounted if b.get("down")]
    available = [b for b in catalog if not b.get("mounted")]
    findings: list[dict] = []
    for b in working:
        what = (b.get("chief_purpose") or b.get("description") or "").strip()
        parts = [f"{b['name']} ({_how(b)})"]
        if what:
            parts.append(what.rstrip(".") + ".")
        actions = [a for a, spec in (b.get("actions") or {}).items() if spec.get("level") != "automatico"]
        if actions:
            parts.append("Pide tu aprobación para: " + ", ".join(actions) + ".")
        if b.get("private"):
            parts.append("Es privada: lo suyo solo usa modelos que corren en la PC.")
        findings.append({"text": clip(" ".join(parts), MAX_FINDING), "helper": "orquestador", "sources": []})
    for b in down:
        findings.append({"text": clip(f"{b['name']}: montada pero caída ({b.get('down_reason') or 'sin detalle'}).",
                                      MAX_FINDING), "helper": "orquestador", "sources": []})
    for b in available:
        extra = f" Error al montarla: {b['error']}" if b.get("error") else ""
        findings.append({"text": clip(f"{b['name']}: está disponible pero no montada. {b.get('description') or ''}"
                                      f"{extra}".strip(), MAX_FINDING), "helper": "orquestador", "sources": []})
    names = [b["name"] for b in working]
    summary = ("Las brigadas que están trabajando son: " + ", ".join(names) + "." if names
               else "No hay brigadas trabajando en este momento.")
    if down:
        summary += " Caídas: " + ", ".join(b["name"] for b in down) + "."
    summary += " El orquestador reparte cada pedido, puede poner a varias a trabajar juntas y es el único que te habla."
    if drafts:
        summary += " Borradores sin activar: " + ", ".join(drafts[:10]) + "."
    warnings = [DRAFT_HINT] if drafts_enabled and edition != "cloud" else []
    return InternalReport.validate({
        "version": REPORT_VERSION, "brigade": "orquestador", "summary": clip(summary, MAX_SUMMARY),
        "findings": findings[:MAX_FINDINGS], "confidence": "high", "warnings": warnings,
    })
