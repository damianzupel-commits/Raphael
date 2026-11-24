"""Un efímero: nace con una sub-tarea, trabaja con SU modelo y SU caja de tools, y muere con la respuesta.

Portado del loop de `BrigadeChief.run` de JarvisRemote. Cambios:
  - el modelo sale de la pasarela (rol `efimero`, override por id) y no de un cliente OpenAI fijo;
  - las tools pasan por la caja y la compuerta de política (`tools.ToolBox`): una tool que necesita aprobación vuelve al
    modelo como `pending_approval` y no se ejecuta;
  - si alcanza el máximo de pasos sin cerrar, FALLA (`StepLimit`) en vez de devolver un texto de relleno como si fuera ok;
  - no es persistente: no guarda memoria (la memoria es del jefe).

`trace` = [{"tool", "args", "ok", "result" | "error", "executed"}], con el resultado SIN recortar. Vive en la instancia para
que el jefe saque fuentes y artefactos también si al efímero lo cortó un timeout a mitad de camino.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from ..tools import ToolBox
from .spec import BrigadeSpec, HelperSpec

logger = logging.getLogger("raphael_core.engine")

EventCallback = Callable[[dict], Awaitable[None]]
ChatFn = Callable[[list[dict], list[dict] | None], Awaitable[dict | None]]   # (messages, tools) -> {"content", "tool_calls"}

MAX_TOOL_RESULT_CHARS = 6000


class NoModel(RuntimeError):
    """No hay ningún modelo disponible para este rol (sin clave, sin cupo, o privado sin modelo local)."""


class StepLimit(RuntimeError):
    """El efímero llegó al máximo de pasos sin cerrar una respuesta."""


async def emit(cb: EventCallback | None, ev: dict) -> None:
    if cb is None:
        return
    try:
        await cb(ev)
    except Exception:  # noqa: BLE001 - un consumidor del feed que falla no corta el trabajo
        logger.debug("on_event falló para %s", ev.get("type"), exc_info=True)


def short_args(args: dict) -> str:
    try:
        s = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(args)
    return s[:160]


def cap(result: object) -> str:
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + "\n[...truncado...]"
    return text


def summary(result: object) -> str:
    if isinstance(result, dict):
        for k in ("status", "message", "title"):
            if result.get(k):
                return f"{k}: {result[k]}"[:200]
        if isinstance(result.get("note"), dict):
            n = result["note"]
            return f"nota: {n.get('title') or n.get('id')}"[:200]
    return cap(result)[:200]


# --- identidad: los nombres de fábrica de los prompts se cambian por los de la instalación ----------------------------------
_USER = re.compile(r"\bDami[aá]n\b")
_ASSISTANT = re.compile(r"\bRaphael\b")


def personalize(text: str, identity: dict | None) -> str:
    """Cambia "Damian"/"Raphael" por los nombres configurados SOLO en texto del código (prompts). Nunca en contenido del
    usuario. Sin identidad, o con los de fábrica, el texto queda idéntico."""
    if not text or not identity:
        return text
    user, assistant = (identity.get("user") or "").strip(), (identity.get("assistant") or "").strip()
    if user and user not in ("Damian", "Damián"):
        text = _USER.sub(user, text)
    if assistant and assistant != "Raphael":
        text = _ASSISTANT.sub(assistant, text)
    return text


class Helper:
    def __init__(self, spec: HelperSpec, brigade: BrigadeSpec, *, chat: ChatFn, toolbox: ToolBox | None = None,
                 identity: dict | None = None) -> None:
        self.spec = spec
        self.brigade = brigade
        self._chat = chat
        self._box = toolbox
        self._identity = identity
        self.trace: list[dict] = []

    async def run(self, task: str, on_event: EventCallback | None = None) -> tuple[str, list[dict]]:
        """Devuelve (texto final, historial). Lanza `NoModel` o `StepLimit`; el jefe lo convierte en resultado ok=false."""
        system = personalize(self.spec.system_prompt() or self.brigade.system_prompt(), self._identity)
        history: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": task}]
        schemas = self._box.schemas() if self._box else []
        self.trace = []
        await emit(on_event, {"type": "start", "topic": task})
        for _ in range(max(1, self.spec.max_steps)):
            msg = await self._chat(history, schemas or None)
            if msg is None:
                raise NoModel(f"no hay modelo disponible para el efímero {self.spec.id}")
            calls = msg.get("tool_calls") or []
            if not calls:
                final = (msg.get("content") or "").strip()
                history.append({"role": "assistant", "content": final})
                await emit(on_event, {"type": "final", "reply": final})
                return final, history
            history.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for tc in calls:
                history.append(await self._tool(tc, on_event))
        raise StepLimit(f"el efímero {self.spec.id} llegó a {self.spec.max_steps} pasos sin cerrar una respuesta")

    async def _tool(self, tc: dict, on_event: EventCallback | None) -> dict:
        fn = tc.get("function") or {}
        name = str(fn.get("name") or "")
        out: dict[str, Any] = {"role": "tool", "tool_call_id": tc.get("id") or "", "name": name}
        try:
            args = json.loads(fn.get("arguments") or "{}")
            if not isinstance(args, dict):
                raise ValueError("los argumentos tienen que ser un objeto")
        except ValueError:
            self.trace.append({"tool": name, "args": {}, "ok": False, "error": "argumentos inválidos"})
            await emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": "argumentos inválidos"})
            return {**out, "content": f"[error] argumentos inválidos para {name}"}
        await emit(on_event, {"type": "tool", "name": name, "args": short_args(args)})
        if self._box is None:
            err = "este efímero no tiene tools"
        else:
            try:
                result, executed = await self._box.call(name, args)
            except Exception as exc:  # noqa: BLE001 - una tool caída vuelve al modelo como dato, no tumba al efímero
                err = str(exc) or type(exc).__name__
            else:
                self.trace.append({"tool": name, "args": args, "ok": True, "result": result, "executed": executed})
                await emit(on_event, {"type": "tool_result", "name": name, "ok": True, "summary": summary(result),
                                      "pending": not executed})
                return {**out, "content": cap(result)}
        logger.warning("tool %s falló en %s: %s", name, self.spec.id, err)
        self.trace.append({"tool": name, "args": args, "ok": False, "error": err})
        await emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": err[:200]})
        return {**out, "content": f"[error] la tool {name} falló: {err}"}
