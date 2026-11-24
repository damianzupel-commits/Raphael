"""BrigadeChief — el molde del "jefe de brigada" (generaliza el engine de Scout).

Un jefe es un supervisor PERSISTENTE de una brigada (decisión 2026-11-03):
  - ve SOLO las tools de su brigada (allowlist = menor privilegio = defensa),
  - corre su propio mini-loop reusando el núcleo (cliente LLM, call_tool, vault),
  - tiene estado que RECUERDA entre turnos y reinicios (persistido en disco),
  - opcionalmente corre dentro del vault propio de su brigada.

Reusa el núcleo sin duplicarlo; lo único propio es este loop fino + la persistencia.
Scout fue el primer jefe de facto; este molde lo generaliza para todas las brigadas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from app.obsidian import profile as vault_profile
from app.tools import call_tool, openai_tool_schemas

logger = logging.getLogger("brigades.chief")

EventCallback = Callable[[dict], Awaitable[None]]

# Tope de caracteres de un resultado de tool reinyectado (evita inflar el request).
_MAX_TOOL_RESULT_CHARS = 6000
# Cuántas rondas LLM->tool->LLM como mucho en un turno.
_MAX_ITERATIONS = 12
# Memoria persistente del jefe: últimos N mensajes user/assistant (texto) que se
# guardan entre turnos. Chico a propósito: el jefe "recuerda qué viene haciendo"
# sin que el historial crezca sin fin (lo que reventaría el presupuesto de TPM).
_MEMORY_MESSAGES = 16
# Carpeta de estado por brigada (best-effort; si el disco falla, el jefe sigue sin memoria).
_STATE_DIR = Path(__file__).resolve().parent.parent / "data" / "brigades"


@dataclass(frozen=True)
class ChiefConfig:
    id: str
    name: str
    tool_names: frozenset[str]
    # str fijo, o un builder sin args que lo arma en cada turno (para prompts que
    # dependen de estado vivo, ej. las directrices editables de Cerebro).
    system_prompt: "str | Callable[[], str]"
    vault_path: str | None = None
    embeddings_path: str | None = None
    # Decisión 2026-11-03: TODOS los jefes son PERSISTENTES (el "representante de
    # plaza": siempre está, recuerda qué viene haciendo). Lo efímero/por-tarea son
    # los AYUDANTES que el jefe spawnea (capa futura, ver blueprint). El flag queda
    # para modelar esos ayudantes (persistent=False) cuando se construyan.
    persistent: bool = True


async def _emit(cb: EventCallback | None, ev: dict) -> None:
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


def _cap(result: object) -> str:
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > _MAX_TOOL_RESULT_CHARS:
        text = text[:_MAX_TOOL_RESULT_CHARS] + "\n[...truncado...]"
    return text


def _summary(result: object) -> str:
    if isinstance(result, dict):
        for k in ("status", "message", "title"):
            if k in result and result[k]:
                return f"{k}: {result[k]}"[:200]
        if isinstance(result.get("note"), dict):
            n = result["note"]
            return f"nota: {n.get('title') or n.get('id')}"[:200]
    return _cap(result)[:200]


class BrigadeChief:
    """Jefe persistente de una brigada. Instanciar una vez (ver brigades/registry.py)."""

    def __init__(self, config: ChiefConfig, client, model: str) -> None:
        self.config = config
        self._client = client
        self._model = model
        self._tools = openai_tool_schemas(config.tool_names) or None
        # Traza de las tools del turno: [{"tool", "args", "ok", "result" | "error"}], con el resultado SIN recortar. El motor
        # (brigades/engine.py) saca de acá las fuentes y artefactos del `ResultadoAyudante`, también si al ayudante lo
        # cortó un timeout a mitad de camino (por eso vive en la instancia y no en lo que devuelve `run`).
        self.trace: list[dict] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def model_label(self) -> str:
        """Modelo EFECTIVO + proveedor ('nemotron-… (NVIDIA)'), resuelto del endpoint real del cliente."""
        from .config import describe_endpoint

        return describe_endpoint(getattr(self._client, "base_url", ""), self._model)["label"]

    # --- persistencia (memoria del jefe) ---------------------------------
    def _state_path(self) -> Path:
        return _STATE_DIR / f"{self.config.id}.json"

    def _load_memory(self) -> list[dict]:
        """Historial limpio persistido (system + últimos user/assistant de texto)."""
        try:
            data = json.loads(self._state_path().read_text(encoding="utf-8"))
            return data.get("history", [])
        except Exception:  # noqa: BLE001
            return []

    def _persist_memory(self, working_history: list[dict]) -> None:
        """Guarda una versión LIMPIA del historial: system + mensajes user/assistant
        con texto (sin tool_calls ni resultados de tools). Así la memoria queda chica
        y sin problemas de apareamiento tool_call/tool. Recorta a los últimos N."""
        clean: list[dict] = []
        for m in working_history:
            role = m.get("role")
            if role == "system" and not clean:
                clean.append({"role": "system", "content": m.get("content", "")})
            elif role == "user":
                clean.append({"role": "user", "content": m.get("content", "")})
            elif role == "assistant" and (m.get("content") or "").strip():
                clean.append({"role": "assistant", "content": m.get("content", "")})
        # system (si hay) + últimos N del resto
        head = clean[:1] if clean and clean[0]["role"] == "system" else []
        tail = [m for m in clean if not (m is head[0] if head else False)]
        trimmed = head + tail[-_MEMORY_MESSAGES:]
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            self._state_path().write_text(
                json.dumps({"history": trimmed}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo persistir la memoria del jefe %s", self.config.id, exc_info=True)

    # --- el turno --------------------------------------------------------
    async def run(self, message: str, on_event: EventCallback | None = None) -> tuple[str, list[dict]]:
        """Corre un turno del jefe. Carga su memoria persistida, procesa, y la guarda.
        Devuelve (texto_final, working_history)."""
        sp = self.config.system_prompt
        system_prompt = sp() if callable(sp) else sp  # builder vivo o str fijo
        from .identidad import personalizar

        system_prompt = personalizar(system_prompt)  # identidad configurada (nombre del asistente / del usuario)
        history = self._load_memory() if self.config.persistent else []
        if not history or history[0].get("role") != "system":
            history = [{"role": "system", "content": system_prompt}] + history
        else:
            history[0]["content"] = system_prompt  # prompt siempre al día
        history.append({"role": "user", "content": message})
        self.trace = []
        await _emit(on_event, {"type": "start", "topic": message})

        final_text = "El jefe alcanzó el máximo de pasos sin cerrar una respuesta."
        prof = (
            vault_profile.VaultProfile(vault_path=self.config.vault_path, embeddings_path=self.config.embeddings_path or "")
            if self.config.vault_path
            else None
        )
        ctx = vault_profile.use_profile(prof) if prof else _nullctx()
        with ctx:
            for _ in range(_MAX_ITERATIONS):
                response = await self._client.chat.completions.create(
                    model=self._model, messages=history, tools=self._tools,
                    tool_choice="auto" if self._tools else None,
                )
                msg = response.choices[0].message
                if not msg.tool_calls:
                    final_text = msg.content or ""
                    history.append({"role": "assistant", "content": final_text})
                    break
                history.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        result_text = f"[error] argumentos inválidos para {name}"
                        self.trace.append({"tool": name, "args": {}, "ok": False, "error": "argumentos inválidos"})
                        await _emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": result_text})
                    else:
                        await _emit(on_event, {"type": "tool", "name": name, "args": _short_args(args)})
                        try:
                            result = await call_tool(name, args)
                            result_text = _cap(result)
                            self.trace.append({"tool": name, "args": args, "ok": True, "result": result})
                            await _emit(on_event, {"type": "tool_result", "name": name, "ok": True, "summary": _summary(result)})
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("tool %s falló: %s", name, exc)
                            result_text = f"[error] la tool {name} falló: {exc}"
                            self.trace.append({"tool": name, "args": args, "ok": False, "error": str(exc)})
                            await _emit(on_event, {"type": "tool_result", "name": name, "ok": False, "summary": str(exc)[:200]})
                    history.append({"role": "tool", "tool_call_id": tc.id, "name": name, "content": result_text})

        if not history or history[-1].get("role") != "assistant":
            history.append({"role": "assistant", "content": final_text})
        await _emit(on_event, {"type": "final", "reply": final_text})
        if self.config.persistent:
            self._persist_memory(history)
        return final_text, history


class _nullctx:
    """Context manager vacío (cuando el jefe no tiene vault propio)."""

    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False
