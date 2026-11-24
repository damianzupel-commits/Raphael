"""Tool que compila un reporte de auditoría de código en Markdown -- ver
`app/audit_report.py`. Junta hallazgos de seguridad y calidad ya escaneados,
qué fixes/ediciones ya se aplicaron (con su commit, revertible), y un resumen
ejecutivo, y lo guarda como nota nueva en el vault de Obsidian (autor jarvis)
para que quede versionado y visible en la pestaña Obsidian de la UI."""

from __future__ import annotations

from .. import audit_report as audit_report_module
from . import register_tool


@register_tool(
    name="audit_generate_report",
    description=(
        "Compila un reporte de auditoría de código CLIENT-FACING (para el dueño de una PyME, no técnico) de un "
        "proyecto ya escaneado con security_scan_project y/o quality_scan_project. Primero corre TRIAGE de falsos "
        "positivos sobre los hallazgos que importan (critical/high/medium): el LLM mira el código real y descarta "
        "los no explotables (ej. un subprocess en un comando CLI de dev sin input de usuario), que van a una "
        "sección aparte con su razón y NO cuentan como riesgo. Con los reales, genera un RESUMEN EJECUTIVO en "
        "lenguaje de negocio y los RIESGOS PRIORITARIOS explicados en criollo (qué es / por qué importa / cómo se "
        "arregla), y deja las tablas crudas como ANEXO técnico. Marca "
        "bien visible el estado de la ÚLTIMA corrida de tests real (code_run_tests): si nunca se corrió, si no "
        "hay suite, o si falló, para que 'sin hallazgos' nunca se lea como 'verificado'. Se guarda como nota "
        "nueva en el vault de Obsidian (autor jarvis, tags 'reportes'/'cliente'), visible en la pestaña Obsidian."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
        },
        "required": ["path"],
    },
)
async def audit_generate_report(path: str) -> dict:
    # Reporte client-facing (narrativa del LLM + anexo técnico). Si la capa
    # narrativa falla por lo que sea, cae al reporte mecánico de siempre.
    try:
        return await audit_report_module.generate_client_report(path)
    except (NotADirectoryError, ValueError):
        raise  # errores de uso reales (proyecto inexistente / sin escaneos) -> propagar
    except Exception:  # noqa: BLE001
        return audit_report_module.generate_report(path)
