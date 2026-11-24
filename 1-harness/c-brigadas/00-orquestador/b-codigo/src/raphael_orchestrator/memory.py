"""Memoria de la CHARLA del orquestador con la persona: continuidad entre turnos y entre brigadas.

Portado de JarvisRemote `orquestador/conversacion.py`. La memoria:
  - es ACOTADA: los últimos `max_turns` turnos (pedido y mensaje recortados) + un RESUMEN determinista de los anteriores
    (una línea por turno viejo, hasta `max_summary`); no crece sin fin ni necesita otro modelo para resumirse;
  - es por SESIÓN (la app, el WhatsApp de la dueña y la voz no se mezclan);
  - solo la lee la voz del orquestador, como DATO. Nunca se le pasa a un jefe ni a un efímero;
  - vive en el espacio propio del orquestador (`ctx.data`, espacio `_orchestrator` del harness), no en un archivo suelto;
  - es best-effort: si el almacén falla, la voz sigue sin memoria.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("raphael_orchestrator.memory")

COLLECTION = "conversation"


@dataclass(frozen=True)
class MemorySettings:
    enabled: bool = True
    max_turns: int = 8
    max_summary: int = 12
    max_request: int = 300
    max_message: int = 500


def _short(text: str, limit: int) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


class Conversation:
    """La charla de una instalación, por sesión, sobre un espacio del harness (cualquier objeto con get/put/delete)."""

    def __init__(self, space: Any, settings: MemorySettings | None = None) -> None:
        self._space = space
        self.settings = settings or MemorySettings()

    def _load(self, session: str) -> dict:
        try:
            data = self._space.get(COLLECTION, session)
            if isinstance(data, dict) and isinstance(data.get("turns"), list) and isinstance(data.get("summary"), list):
                return data
        except Exception:  # noqa: BLE001 - sin memoria se sigue igual
            logger.warning("no se pudo leer la memoria de la charla", exc_info=True)
        return {"turns": [], "summary": []}

    def record(self, session: str, request: str, brigade: str, message: str, *, when: str = "") -> None:
        """Suma un turno (qué pidió la persona, qué brigada lo resolvió y qué se le dijo) y compacta lo viejo."""
        st = self.settings
        if not st.enabled:
            return
        data = self._load(session)
        data["turns"].append({"when": when, "brigade": brigade, "request": _short(request, st.max_request),
                              "message": _short(message, st.max_message)})
        while len(data["turns"]) > st.max_turns:   # lo que sale de la ventana queda como una línea de resumen
            old = data["turns"].pop(0)
            data["summary"].append(f"[{old.get('brigade', '?')}] {_short(old.get('request', ''), 120)}")
        data["summary"] = data["summary"][-st.max_summary:]
        try:
            self._space.put(COLLECTION, session, data)
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo guardar la memoria de la charla", exc_info=True)

    def for_prompt(self, session: str, user: str = "") -> str:
        """La charla previa como texto para la voz ('' si no hay o está apagada). Es DATO."""
        if not self.settings.enabled:
            return ""
        who = user or "La persona"
        data = self._load(session)
        lines: list[str] = []
        if data["summary"]:
            lines.append("Antes se habló de: " + " · ".join(str(x) for x in data["summary"]))
        for t in data["turns"]:
            lines.append(f"- {who} pidió ({t.get('brigade', '?')}): {t.get('request', '')}\n"
                         f"  Se le dijo: {t.get('message', '')}")
        return "\n".join(lines)

    def turns(self, session: str) -> list[dict]:
        return list(self._load(session)["turns"])

    def reset(self, session: str) -> None:
        try:
            self._space.delete(COLLECTION, session)
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo borrar la memoria de la charla", exc_info=True)
