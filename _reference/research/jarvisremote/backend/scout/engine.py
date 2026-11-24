"""Engine de Raphael Scout: loop de agente COMPACTO que reusa el núcleo.

Reusa del núcleo compartido, sin duplicarlo (SPEC §2/§5):
  - el cliente LLM OpenAI-compatible (vía scout/config.py),
  - el registro y ejecutor de tools (app.tools.call_tool / openai_tool_schemas),
    filtrado al set chico de Scout (identity.SCOUT_TOOL_NAMES),
  - a través de esas tools, el vault de Obsidian y el navegador del núcleo.

Lo único "propio" de Scout es este loop fino (~un puñado de líneas): mandar el
request, despachar los tool_calls, reinyectar los resultados, repetir. No
arrastra el run_agent del monolito (gates de PC, mission_control, phone_link,
persistencia FastAPI) a propósito: Scout tiene que poder correr solo, también
el día que viva en su propio repo.
"""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable

from app.obsidian import profile as vault_profile
from app.tools import call_tool, openai_tool_schemas

from .config import ScoutConfig, build_client, load_scout_config
from .identity import SCOUT_TOOL_NAMES, build_scout_system_prompt

logger = logging.getLogger("scout.engine")

# Un callback opcional que recibe eventos del turno ({"type": ..., ...}) para que
# una UI muestre el "feed en vivo" (qué tool corre, qué devolvió, la respuesta
# final). Es async para poder encolar/streamear sin bloquear el loop.
EventCallback = Callable[[dict], Awaitable[None]]

# Tope de caracteres por resultado de tool reinyectado al modelo. research_topic
# puede traer varias páginas; sin tope, un solo resultado infla el próximo
# request y revienta el presupuesto de TPM de los tiers gratis. Truncado simple
# (el contenido completo ya quedó guardado en la nota del vault de todos modos).
_MAX_TOOL_RESULT_CHARS = 6000

# Guard de iteraciones: cuántas rondas LLM->tool->LLM como mucho en un turno,
# para que un modelo que se traba pidiendo tools para siempre no cuelgue el turno.
_MAX_ITERATIONS = 12


def scout_tool_schemas() -> list[dict]:
    """Los schemas SOLO de las tools de Scout (subconjunto del registro del
    núcleo). Esto es lo que mantiene el request liviano."""
    return openai_tool_schemas(SCOUT_TOOL_NAMES)


def _cap(result: object) -> str:
    """Serializa el resultado de una tool a string y lo trunca si es enorme."""
    if isinstance(result, str):
        text = result
    else:
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except Exception:  # noqa: BLE001
            text = str(result)
    if len(text) > _MAX_TOOL_RESULT_CHARS:
        text = text[:_MAX_TOOL_RESULT_CHARS] + "\n[...truncado; el contenido completo quedó en la nota del vault...]"
    return text


async def _emit(cb: "EventCallback | None", ev: dict) -> None:
    """Dispara un evento al callback de feed, si hay uno. Defensivo: un fallo del
    callback (ej. la UI se desconectó) nunca debe tirar el turno de Scout."""
    if cb is None:
        return
    try:
        await cb(ev)
    except Exception:  # noqa: BLE001
        logger.debug("on_event falló para %s", ev.get("type"), exc_info=True)


def _short_args(args: dict) -> str:
    try:
        s = json.dumps(args, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        s = str(args)
    return s[:160]


def _summary(result: object) -> str:
    """Resumen corto y legible del resultado de una tool, para el feed en vivo."""
    if isinstance(result, dict):
        for k in ("status", "message", "title"):
            if k in result and result[k]:
                return f"{k}: {result[k]}"[:200]
        if isinstance(result.get("note"), dict):
            n = result["note"]
            return f"nota: {n.get('title') or n.get('id')}"[:200]
    return _cap(result)[:200]


async def run_scout(
    message: str,
    history: list[dict] | None = None,
    cfg: ScoutConfig | None = None,
    on_event: "EventCallback | None" = None,
) -> tuple[str, list[dict]]:
    """Corre un turno de Scout.

    `message`: lo que pide el usuario (ej. "investigá el estado de los LLM locales").
    `history`: historial previo (lista de mensajes estilo OpenAI). Si es None,
        arranca una conversación nueva con el system prompt de Scout.
    `cfg`: config BYOM; si es None se carga del entorno (scout/config.py).
    `on_event`: callback async opcional para el feed en vivo (ver EventCallback).

    El turno corre dentro del vault de investigación de Scout (cfg.vault_path), para
    que lo capturado no se mezcle con el vault de seguridad/código del Raphael grande.

    Devuelve (texto_final, history_actualizado).
    """
    cfg = cfg or load_scout_config()
    client = build_client(cfg)
    tools = scout_tool_schemas()
    prof = vault_profile.VaultProfile(vault_path=cfg.vault_path, embeddings_path=cfg.embeddings_path)

    if history is None:
        history = [{"role": "system", "content": build_scout_system_prompt(cfg.capture_dir)}]
    history.append({"role": "user", "content": message})
    await _emit(on_event, {"type": "start", "topic": message})

    # Default: cubre el caso "se agotaron las iteraciones sin respuesta final".
    final_text = (
        "Scout alcanzó el máximo de pasos sin cerrar una respuesta. Lo capturado "
        "quedó guardado en el vault; probá acotar el pedido."
    )

    with vault_profile.use_profile(prof):
        for _ in range(_MAX_ITERATIONS):
            response = await client.chat.completions.create(
                model=cfg.model,
                messages=history,
                tools=tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                final_text = msg.content or ""
                history.append({"role": "assistant", "content": final_text})
                break

            # El modelo pidió una o más tools: se registra el mensaje assistant con
            # los tool_calls y después un mensaje 'tool' por cada uno (con su
            # tool_call_id), que es lo que el protocolo OpenAI espera en la ronda
            # siguiente.
            history.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    result_text = f"[error] argumentos inválidos (no son JSON) para {name}: {tc.function.arguments!r}"
                    await _emit(on_event, {"type": "tool", "name": name, "args": "(inválidos)"})
                    await _emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": result_text[:200]})
                else:
                    await _emit(on_event, {"type": "tool", "name": name, "args": _short_args(args)})
                    try:
                        result = await call_tool(name, args)
                        result_text = _cap(result)
                        await _emit(on_event, {"type": "tool_result", "name": name, "ok": True, "summary": _summary(result)})
                    except Exception as exc:  # noqa: BLE001 — una tool que falla no debe tirar el turno
                        logger.warning("tool %s falló: %s", name, exc)
                        result_text = f"[error] la tool {name} falló: {exc}"
                        await _emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": str(exc)[:200]})
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": result_text,
                    }
                )

    # Si se salió por agotar iteraciones, el último mensaje es 'tool': dejamos
    # el texto final default como respuesta del asistente.
    if not history or history[-1].get("role") != "assistant":
        history.append({"role": "assistant", "content": final_text})

    await _emit(on_event, {"type": "final", "reply": final_text})
    return final_text, history
