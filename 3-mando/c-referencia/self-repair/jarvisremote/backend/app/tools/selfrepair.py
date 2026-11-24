"""Tool `selfrepair_propose_fix` -- primer paso (y único paso automatizable
sin gate) de la Opción C del diseño de auto-reparación: proponer un cambio a
código propio de Jarvis (`backend/`) en modo dry-run, nunca aplicarlo. Ver
`app/selfrepair/` para la lógica real y `app/agent.py` para el guardrail que
exige un proposal_id confirmado por Damian antes de que `code_apply_fix`
pueda aplicar esto de verdad."""

from __future__ import annotations

from .. import audit_log
from ..selfrepair import gate, propose
from . import register_tool


@register_tool(
    name="selfrepair_propose_fix",
    description=(
        "Propone (SOLO propone, nunca aplica) un cambio puntual al propio código de Jarvis "
        "(backend/ -- el código que está corriendo ahora mismo, incluye backend/app y backend/tests). "
        "Genera el diff real (dry-run, no escribe nada) y devuelve un 'proposal_id' -- para aplicarlo "
        "de verdad hace falta que Damian lo confirme EXPLÍCITAMENTE en el chat citando ese id exacto, "
        "y recién ahí llamar a code_apply_fix con confirm=true, file y old_snippet/new_snippet "
        "IDÉNTICOS a esta propuesta. Si 'note_id' viene de una nota de diagnóstico de meta-observación "
        "(ver obsidian_search_notes, notas tag 'autodiagnostico'), el diff se adjunta a esa misma nota "
        "para que quede revisable ahí, no solo en el chat. Podés usarla de forma PROACTIVA "
        "(decisión de Damian 2026-10-06): si detectás un bug real o una mejora concreta en el propio "
        "código de Jarvis, proponela sin esperar a que te lo pidan. Pero sé SELECTIVO -- solo cosas "
        "concretas y justificadas, nunca triviales ni especulativas -- y recordá que aplicar SIEMPRE "
        "requiere que Damian confirme el proposal_id."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Ruta del archivo relativa a backend/ (ej. 'app/agent.py')."},
            "old_snippet": {"type": "string", "description": "Texto exacto a reemplazar (debe aparecer una única vez en el archivo)."},
            "new_snippet": {"type": "string", "description": "Texto de reemplazo propuesto."},
            "rationale": {"type": "string", "description": "Por qué este cambio arregla el problema -- una explicación concreta, no genérica."},
            "commit_message": {"type": "string", "description": "Mensaje de commit sugerido para cuando se aplique de verdad."},
            "note_id": {"type": "string", "description": "Opcional: id de la nota de diagnóstico (Opción B) a la que adjuntar esta propuesta."},
        },
        "required": ["file", "old_snippet", "new_snippet", "rationale", "commit_message"],
    },
)
def selfrepair_propose_fix(
    file: str,
    old_snippet: str,
    new_snippet: str,
    rationale: str,
    commit_message: str,
    note_id: str | None = None,
) -> dict:
    arguments = {"file": file, "rationale": rationale, "note_id": note_id}
    # Interruptor maestro del autorediseño (2026-10-06, pedido de Damian: "dejalo
    # siempre encendido, que siempre me pregunte antes de cambiar algo"). El flag
    # SELF_REDESIGN_ENABLED habilita/deshabilita la CAPACIDAD de proponer cambios al
    # propio código. Aplicar de verdad SIEMPRE sigue necesitando confirmación manual
    # por proposal_id (code_apply_fix confirm=true), así que "encendido" nunca significa
    # "aplica solo": significa "puede proponer; vos confirmás antes de cada cambio".
    from ..config import settings

    if not settings.self_redesign_enabled:
        return {
            "error": "El autorediseño está deshabilitado (SELF_REDESIGN_ENABLED=false). "
            "Prendelo en backend/.env para permitir propuestas.",
            "proposal_id": None,
        }
    # Etapa D -- línea roja: ni siquiera se PROPONE un cambio a un archivo de seguridad.
    from ..selfrepair import guardrail

    blocked = guardrail.check(file)
    if blocked:
        return {"error": blocked, "proposal_id": None, "linea_roja": True}
    try:
        proposal = propose.propose_fix(
            file=file, old_snippet=old_snippet, new_snippet=new_snippet,
            rationale=rationale, commit_message=commit_message, note_id=note_id,
        )
    except Exception as exc:
        audit_log.log_tool_call(target="code", tool="selfrepair_propose_fix", arguments=arguments, error=str(exc))
        raise
    result = {
        "proposal_id": proposal.proposal_id,
        "file": proposal.file,
        "diff": proposal.diff,
        "note_id": proposal.note_id,
        "message": (
            f"Propuesta generada ({proposal.proposal_id}), NADA se aplicó todavía. Para aplicarla de "
            f"verdad, Damian tiene que confirmar '{proposal.proposal_id}' explícitamente en el chat."
        ),
    }
    audit_log.log_tool_call(target="code", tool="selfrepair_propose_fix", arguments=arguments, result=result)
    return result
