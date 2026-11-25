"""Enlace con el celular. Portado de `phone_link.py` (sin el emparejamiento por QR, que es del servidor: pieza 3).

El celular abre UNA conexión WebSocket saliente hacia el servidor (la mantiene un servicio de la app Android). El
servidor, que es quien tiene el endpoint, le pasa esa conexión a `link` y le reenvía lo que recibe:

    from raphael_operaciones.adapters.phone import link
    await link.register(websocket)              # al conectarse el celular
    await link.handle_incoming(mensaje_json)    # por cada mensaje que manda el celular
    await link.unregister(websocket)            # al desconectarse

Cada pedido a una tool del celular viaja como {"type": "tool_call", "id", "tool", "arguments"} y se espera la respuesta
con el mismo `id`. Un solo celular a la vez: una conexión nueva reemplaza a la anterior.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Protocol

from . import AdapterUnavailable


class SendsText(Protocol):
    async def send_text(self, data: str) -> None: ...


class PhoneLink(Protocol):
    @property
    def connected(self) -> bool: ...

    async def dispatch(self, tool: str, arguments: dict, timeout: float) -> Any: ...


class PhoneToolError(AdapterUnavailable):
    """La tool falló del lado del celular; el mensaje ya viene listo para mostrar."""


class RealPhoneLink:
    def __init__(self) -> None:
        self._ws: SendsText | None = None
        self._pending: dict[str, asyncio.Future] = {}

    @property
    def connected(self) -> bool:
        return self._ws is not None

    def _fail_all(self, reason: str) -> None:
        for call_id, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(AdapterUnavailable(reason))
            self._pending.pop(call_id, None)

    async def register(self, ws: SendsText) -> None:
        if self._ws is not None and self._ws is not ws:
            self._fail_all("Se reemplazó la conexión del celular por una nueva")
        self._ws = ws

    async def unregister(self, ws: SendsText) -> None:
        if self._ws is ws:
            self._ws = None
            self._fail_all("El celular se desconectó")

    async def handle_incoming(self, message: dict | str) -> None:
        """Una respuesta del celular a un pedido pendiente. Lo que no corresponde a un pedido se ignora."""
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except ValueError:
                return
        if not isinstance(message, dict):
            return
        fut = self._pending.pop(message.get("id"), None) if message.get("id") else None
        if fut is None or fut.done():
            return
        if message.get("error"):
            fut.set_exception(PhoneToolError(str(message["error"])))
        else:
            fut.set_result(message.get("result"))

    async def dispatch(self, tool: str, arguments: dict, timeout: float) -> Any:
        if self._ws is None:
            raise AdapterUnavailable("No hay ningún celular conectado a Raphael en este momento.")
        call_id = str(uuid.uuid4())
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[call_id] = fut
        payload = {"type": "tool_call", "id": call_id, "tool": tool, "arguments": arguments}
        try:
            await self._ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            self._pending.pop(call_id, None)
            raise AdapterUnavailable(f"No se pudo mandar el pedido al celular: {exc}") from exc
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            self._pending.pop(call_id, None)
            raise AdapterUnavailable(f"El celular no respondió '{tool}' a tiempo ({timeout:g}s).") from None


#: el enlace real de este proceso: el servidor lo conecta, la brigada lo usa
link = RealPhoneLink()


class MockPhone:
    """Un celular de mentira: siempre conectado, anota los pedidos y contesta lo que se le pidió."""

    def __init__(self, results: dict[str, Any] | None = None, connected: bool = True) -> None:
        self.results = dict(results or {})
        self._connected = connected
        self.calls: list[tuple[str, dict]] = []

    @property
    def connected(self) -> bool:
        return self._connected

    async def dispatch(self, tool: str, arguments: dict, timeout: float) -> Any:
        if not self._connected:
            raise AdapterUnavailable("No hay ningún celular conectado a Raphael en este momento.")
        self.calls.append((tool, dict(arguments)))
        if tool in self.results:
            res = self.results[tool]
            return res(arguments) if callable(res) else res
        return {"simulated": True, "tool": tool, "arguments": arguments}
