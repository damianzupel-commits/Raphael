"""Comunicación agente-a-agente V2 (spec §4).

Por default la brigada es hub-and-spoke: los agentes NO se hablan, el
orquestador reparte y junta. A2A es la capa OPCIONAL para negociación
bidireccional (ej. el Catador le pide al Redactor que reescriba una sección).

El riesgo de A2A es el bucle infinito (dos agentes rebotándose mensajes). Por
eso TODA conversación lleva anti-bucle DURO por construcción:
- TTL: máximo de saltos (hops) por conversación.
- Presupuesto: máximo de mensajes totales.
Si se toca cualquiera de los dos, la conversación se corta. No hay forma de que
un agente genere un bucle infinito acá.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.harness.a2a")


@dataclass
class Message:
    sender: str
    recipient: str
    kind: str  # ej. "request_rewrite", "ack", "reject"
    payload: dict[str, Any] = field(default_factory=dict)
    hops: int = 0  # cuántos saltos lleva esta cadena


# Un handler recibe un Message y opcionalmente devuelve una respuesta (o None).
Handler = Callable[[Message], Awaitable[Message | None]]


class ConversationBudgetExceeded(RuntimeError):
    pass


class MessageBus:
    """Ruteo de mensajes entre agentes con anti-bucle duro.

    `max_hops` corta cadenas largas (TTL); `max_messages` corta conversaciones
    que mandan demasiado en total (presupuesto). Cualquiera de los dos detiene
    la conversación de forma garantizada."""

    def __init__(self, max_hops: int = 6, max_messages: int = 20) -> None:
        self.max_hops = max_hops
        self.max_messages = max_messages
        self._handlers: dict[str, Handler] = {}

    def register(self, agent_name: str, handler: Handler) -> None:
        self._handlers[agent_name] = handler

    async def run_conversation(self, initial: Message) -> list[Message]:
        """Corre una conversación arrancando por `initial`. Devuelve el
        transcript (todos los mensajes que circularon). Termina cuando un
        handler no responde, o cuando se toca el TTL o el presupuesto."""
        transcript: list[Message] = []
        current: Message | None = initial
        while current is not None:
            if len(transcript) >= self.max_messages:
                logger.warning("A2A: presupuesto de mensajes agotado (%d), corto", self.max_messages)
                break
            if current.hops > self.max_hops:
                logger.warning("A2A: TTL agotado (%d hops), corto", self.max_hops)
                break

            transcript.append(current)
            handler = self._handlers.get(current.recipient)
            if handler is None:
                logger.info("A2A: no hay handler para %s, fin de la cadena", current.recipient)
                break

            reply = await handler(current)
            if reply is None:
                break
            # el hop se incrementa SIEMPRE en la respuesta -> el TTL siempre avanza
            reply.hops = current.hops + 1
            current = reply

        return transcript
