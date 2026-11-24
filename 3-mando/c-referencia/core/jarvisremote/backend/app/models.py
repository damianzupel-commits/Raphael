from typing import Any, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    # Id del cliente que manda (tray-pc, un uuid del celular, etc.). Se usa para el
    # espejado en vivo (2026-10-06): el backend re-emite cada mensaje por /ws/chat a
    # TODOS los clientes de la conversación, tagueado con este origin. El cliente que
    # lo mandó ignora su propio eco (ya lo mostró por la respuesta HTTP); los demás
    # lo muestran. Así el historial se refleja entre PC y celular al instante.
    client_id: Optional[str] = None


class ChatMirrorMessage(BaseModel):
    """Un mensaje re-emitido por /ws/chat para el espejado en vivo."""

    role: str  # "user" | "assistant"
    content: str
    ts: float  # epoch segundos


class HistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ChatMirrorMessage] = []


class ToolCallLog(BaseModel):
    tool: str
    arguments: dict
    result: Any


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolCallLog] = []
