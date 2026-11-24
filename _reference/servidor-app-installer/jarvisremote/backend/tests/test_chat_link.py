"""Tests del espejado del chat en vivo (app/chat_link.py). Puro, sin red real:
se inyecta un `send` fake y websockets fake.
"""

import pytest

from app import chat_link


class _FakeWS:
    def __init__(self, fail=False):
        self.received = []
        self.fail = fail


async def _send(ws, payload):
    if ws.fail:
        raise RuntimeError("ws caído")
    ws.received.append(payload)


@pytest.fixture(autouse=True)
def _clean():
    chat_link._subs.clear()
    yield
    chat_link._subs.clear()


def test_register_y_count():
    a, b = _FakeWS(), _FakeWS()
    chat_link.register("default", a, "tray-pc")
    chat_link.register("default", b, "cel-123")
    assert chat_link.subscriber_count("default") == 2
    chat_link.unregister("default", a)
    assert chat_link.subscriber_count("default") == 1


def test_turn_payload_forma():
    p = chat_link.turn_payload("default", "hola", "qué tal", 123.0, "cel-123")
    assert p["type"] == "turn"
    assert p["conversation_id"] == "default"
    assert p["origin"] == "cel-123"
    assert [m["role"] for m in p["messages"]] == ["user", "assistant"]
    assert p["messages"][0]["content"] == "hola"
    assert p["messages"][1]["content"] == "qué tal"


@pytest.mark.anyio
async def test_broadcast_saltea_al_origin():
    pc, cel = _FakeWS(), _FakeWS()
    chat_link.register("default", pc, "tray-pc")
    chat_link.register("default", cel, "cel-123")
    # un turno originado en el celular: le llega a la PC, NO al celular.
    sent = await chat_link.broadcast("default", {"x": 1}, origin="cel-123", send=_send)
    assert sent == 1
    assert pc.received == [{"x": 1}]
    assert cel.received == []


@pytest.mark.anyio
async def test_broadcast_sin_origin_va_a_todos():
    pc, cel = _FakeWS(), _FakeWS()
    chat_link.register("default", pc, "tray-pc")
    chat_link.register("default", cel, "cel-123")
    sent = await chat_link.broadcast("default", {"x": 2}, origin=None, send=_send)
    assert sent == 2


@pytest.mark.anyio
async def test_broadcast_desuscribe_a_los_caidos():
    ok, bad = _FakeWS(), _FakeWS(fail=True)
    chat_link.register("default", ok, "a")
    chat_link.register("default", bad, "b")
    sent = await chat_link.broadcast("default", {"x": 3}, origin=None, send=_send)
    assert sent == 1  # solo el ok
    assert chat_link.subscriber_count("default") == 1  # el caído se fue


@pytest.mark.anyio
async def test_otra_conversacion_no_recibe():
    a = _FakeWS()
    chat_link.register("default", a, "a")
    sent = await chat_link.broadcast("otra", {"x": 4}, origin=None, send=_send)
    assert sent == 0
    assert a.received == []
