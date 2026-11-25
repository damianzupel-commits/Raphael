"""`memoria.turno`: al cerrar cada turno el orquestador le avisa a la brigada Memoria, por el bus del harness.

Formato (el que consume el cocinero `consolidator` de la 09): `memoria.turno {conv_id, history, dominio}`, con `history` en el
formato de mensajes de chat (`role` y `content`), `conv_id` = la sesión y `dominio` = la brigada que resolvió el turno.
Solo se publica el turno que cerró bien (el que la voz le entregó a la persona); los comandos y la Secretaria no.

El orquestador NO conoce a Memoria: publica al bus y quien quiera escucha. Si el harness no le da cómo publicar
(`ctx.publish`, que el harness ya ofrece), no se rompe nada: lo deja anotado en la auditoría una vez por día y sigue. Nunca lanza.
Por defecto solo en la edición personal (`memory.publish_turns: null`); en la nube no hay Memoria.
"""

from __future__ import annotations

from typing import Any

from .config import OrchestratorConfig

EVENT = "memoria.turno"
COLLECTION = "proactive"


def enabled(cfg: OrchestratorConfig, edition: str) -> bool:
    flag = cfg.memory.publish_turns
    return flag if flag is not None else edition == "personal"


def turn_payload(session: str, request: str, brigade: str, message: str) -> dict:
    return {"conv_id": session, "dominio": brigade,
            "history": [{"role": "user", "content": request}, {"role": "assistant", "content": message}]}


def publish_turn(ctx: Any, cfg: OrchestratorConfig, session: str, request: str, brigade: str, message: str) -> bool:
    """True si se publicó. Nunca lanza: la memoria no puede romper un turno."""
    try:
        if not enabled(cfg, getattr(ctx, "edition", "")) or not request or not message:
            return False
        publish = getattr(ctx, "publish", None)
        if publish is None:
            key = f"nopub-{ctx.now().date()}"
            if not ctx.data.get(COLLECTION, key):
                ctx.data.put(COLLECTION, key, {"at": ctx.now().isoformat(timespec="seconds")})
                ctx.record("memoria_turno_no_publicado", motivo="el harness no ofrece publish (versión vieja)")
            return False
        publish(EVENT, turn_payload(session, request, brigade, message))
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            ctx.record("memoria_turno_fallido", error=repr(exc)[:200])
        except Exception:  # noqa: BLE001
            pass
        return False
