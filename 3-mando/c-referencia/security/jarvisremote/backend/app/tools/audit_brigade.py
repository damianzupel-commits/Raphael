"""Tool que corre la auditoría a través de la BRIGADA (el DAG de estaciones del
harness), en vez de la secuencia lineal de `audit_generate_report`. Ver
`app/harness/audit_brigade.py` y `docs/BRIGADA-AUDITORIA.md`.

Mismo resultado que `audit_generate_report` (reporte client-facing guardado en el
vault), pero orquestado como grafo: E1 Reconocimiento → E3 Triage + E4 Config →
E2 Contexto → E5 Redacción → E6 Catador → E7 Pase. Cada estación con su contexto
chico y su rol.

ACTIVACIÓN: YA está importada en tools/__init__.py (activada 2026-09-21, tras 61
tests en verde), así que `audit_report_brigade` aparece en el registro de tools
cuando el backend arranca. Convive con `audit_generate_report`: no lo reemplaza.
Pendiente: una vez validada en vivo, converger (que el lineal delegue en la
brigada) -- ver docs/BRIGADA-AUDITORIA.md.
"""

from __future__ import annotations

from ..harness import audit_brigade as brigade
from . import register_tool


@register_tool(
    name="audit_report_brigade",
    description=(
        "Igual que audit_generate_report (reporte de auditoría client-facing de un proyecto ya escaneado con "
        "security_scan_project/quality_scan_project), pero corrido a través de la BRIGADA: un grafo de estaciones "
        "especializadas (reconocimiento, triage, contexto por ruta, config checker, redacción, catador/QA, pase) "
        "coordinadas por el orquestador, cada una con su contexto acotado. Mismo entregable (nota en el vault, autor "
        "jarvis, tags reportes/cliente), pero con el pipeline decompuesto y verificable estación por estación. "
        "Requiere que el proyecto ya haya sido escaneado. Devuelve el resumen de la corrida (qué estaciones "
        "corrieron) y el reporte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya escaneado)."},
        },
        "required": ["path"],
    },
)
async def audit_report_brigade(path: str) -> dict:
    return await brigade.run_audit_brigade(path)
