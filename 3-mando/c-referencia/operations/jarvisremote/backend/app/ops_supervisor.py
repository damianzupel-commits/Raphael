"""Supervisor de la brigada Operaciones (2026-10-12, pedido de Damian).

Antes de ejecutar una tool de ACCIÓN (control de PC/celular = brigada "ops"), un modelo
tier-3 (Sonnet) revisa el llamado y puede FRENARLO si es claramente erróneo o peligroso
("frenar malos llamados"). Es un guardrail SUAVE, aparte de los gates duros del agente.

Reglas de diseño:
- Gateado por settings.ops_supervisor_enabled (default OFF): si está apagado, ni se llama.
- Solo aplica a tools de la brigada "ops" (mission_control.TOOL_BRIGADE) — no a todo, para no
  meter latencia/costo en cada tool.
- FAIL-OPEN: si el supervisor falla, tarda o responde cualquier cosa rara, NO bloquea. Nunca
  puede romper un turno que andaba. Bloquear es la excepción explícita, no el default.
"""

from __future__ import annotations

import json
import logging

from .config import settings

logger = logging.getLogger("jarvis.ops_supervisor")

_SYS = (
    "Sos el SUPERVISOR de la brigada de Operaciones de un asistente que controla la PC y el "
    "celular del usuario. Te paso UNA tool que el agente está por ejecutar, con sus argumentos "
    "y el pedido original del usuario. Tu única tarea: decidir si ese llamado es razonable para "
    "cumplir el pedido. Bloqueá SOLO si es claramente erróneo, incoherente con el pedido, o "
    "destructivo sin sentido. Ante cualquier duda, DEJÁ PASAR. Respondé EXCLUSIVAMENTE un JSON: "
    '{"ok": true}  o  {"ok": false, "reason": "<motivo corto y accionable para el agente>"}.'
)


def _is_ops_tool(tool_name: str) -> bool:
    from . import mission_control

    return mission_control.TOOL_BRIGADE.get(tool_name) == "ops"


async def validate_error(tool_name: str, args: dict, user_text: str, _client_and_model=None) -> str | None:
    """Devuelve un motivo (str) si el llamado hay que BLOQUEARLO, o None si pasa.

    `_client_and_model` es inyectable para testear sin proveedor real: una tupla (cliente, modelo).
    """
    if not settings.ops_supervisor_enabled or not _is_ops_tool(tool_name):
        return None
    try:
        if _client_and_model is not None:
            client, model = _client_and_model
        else:
            from .harness.model_registry import client_and_model_for_tier

            client, model = client_and_model_for_tier(3)  # Sonnet (en modo prueba cae a free)
        payload = json.dumps(
            {"tool": tool_name, "args": args, "pedido_usuario": user_text}, ensure_ascii=False
        )[:4000]
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYS},
                {"role": "user", "content": payload},
            ],
            temperature=0,
            timeout=30,
        )
        raw = (resp.choices[0].message.content or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None  # no devolvió JSON -> fail-open
        data = json.loads(raw[start : end + 1])
        if data.get("ok") is False:
            reason = str(data.get("reason") or "llamado no válido")
            logger.info("ops_supervisor BLOQUEÓ %s: %s", tool_name, reason[:120])
            return "Supervisor de Operaciones frenó este llamado: " + reason
        return None
    except Exception as exc:  # noqa: BLE001 -- fail-open: nunca bloquea por un error propio
        logger.warning("ops_supervisor fail-open (%s): %s", tool_name, exc)
        return None
