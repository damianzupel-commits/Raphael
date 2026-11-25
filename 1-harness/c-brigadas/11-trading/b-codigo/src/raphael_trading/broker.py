"""Adaptadores de BROKER: uno simulado y uno real (OANDA v20). Solo los toca `execute` del cocinero, ya aprobado.

- `SimulatedBroker`: en memoria, sin red; es el que usan los tests y el que corre si no hay clave.
- `OandaBroker`: REST v20. Cuenta `practice` por defecto; la `live` exige además `TRADING_ALLOW_LIVE=1`.
  Claves por entorno: `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`. El token nunca se guarda ni se loguea.
Decidido el 21 nov: ni en demo se opera sin aprobación de Damián (eso lo garantiza el manifiesto, no este módulo).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from . import ibkr
from .data import OANDA_HOSTS, oanda_instrument


class BrokerError(Exception):
    """El broker rechazó o no pudo con el pedido. El mensaje es para la persona."""


@dataclass
class Order:
    instrument: str
    direction: str          # long | short
    units: float
    sl: float
    tp: float
    ref: str = ""           # id de la señal, para auditar


@dataclass
class Fill:
    id: str
    instrument: str
    direction: str
    units: float
    price: float
    broker: str
    simulated: bool
    raw: dict = field(default_factory=dict)


class Broker(Protocol):
    name: str
    simulated: bool

    def place(self, order: Order, price: float | None = None) -> Fill: ...
    def positions(self) -> list[dict]: ...
    def close(self, position_id: str) -> dict: ...


class SimulatedBroker:
    name = "simulado"
    simulated = True

    def __init__(self) -> None:
        self._n = 0
        self._open: dict[str, Fill] = {}

    def place(self, order: Order, price: float | None = None) -> Fill:
        if order.units <= 0:
            raise BrokerError("unidades inválidas")
        self._n += 1
        fill = Fill(f"SIM-{self._n}", order.instrument, order.direction, order.units, price or 0.0, self.name, True)
        self._open[fill.id] = fill
        return fill

    def positions(self) -> list[dict]:
        return [{"id": f.id, "instrument": f.instrument, "direction": f.direction, "units": f.units, "price": f.price}
                for f in self._open.values()]

    def close(self, position_id: str) -> dict:
        if position_id not in self._open:
            raise BrokerError(f"no existe la posición {position_id}")
        f = self._open.pop(position_id)
        return {"id": f.id, "closed": True}


class OandaBroker:
    name = "oanda"
    simulated = False

    def __init__(self, *, environment: str = "practice", env: dict | None = None,
                 transport: httpx.BaseTransport | None = None) -> None:
        env = os.environ if env is None else env
        if environment == "live" and env.get("TRADING_ALLOW_LIVE") != "1":
            raise BrokerError("cuenta real bloqueada: falta TRADING_ALLOW_LIVE=1 (decisión explícita de Damián)")
        self._token = env.get("OANDA_API_TOKEN", "")
        self._account = env.get("OANDA_ACCOUNT_ID", "")
        if not self._token or not self._account:
            raise BrokerError("faltan OANDA_API_TOKEN u OANDA_ACCOUNT_ID")
        self._base = f"{OANDA_HOSTS[environment]}/v3/accounts/{self._account}"
        self._transport = transport
        self.environment = environment

    def _call(self, method: str, path: str, **kw) -> dict:
        try:
            with httpx.Client(transport=self._transport, timeout=15) as cl:
                r = cl.request(method, self._base + path, headers={"Authorization": f"Bearer {self._token}"}, **kw)
        except httpx.HTTPError as exc:
            raise BrokerError(f"no pude hablar con OANDA ({type(exc).__name__})") from None
        if r.status_code >= 400:
            raise BrokerError(f"OANDA rechazó el pedido ({r.status_code}): {r.text[:200]}")
        return r.json()

    def place(self, order: Order, price: float | None = None) -> Fill:
        units = int(round(order.units))
        if units <= 0:
            raise BrokerError("unidades inválidas")
        signed = units if order.direction == "long" else -units
        body = {"order": {
            "type": "MARKET", "instrument": oanda_instrument(order.instrument), "units": str(signed),
            "timeInForce": "FOK", "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": f"{order.sl:.3f}"}, "takeProfitOnFill": {"price": f"{order.tp:.3f}"},
            "clientExtensions": {"comment": f"raphael:{order.ref}"[:128]},
        }}
        data = self._call("POST", "/orders", json=body)
        fill = data.get("orderFillTransaction")
        if not fill:
            reason = (data.get("orderCancelTransaction") or {}).get("reason", "sin ejecución")
            raise BrokerError(f"OANDA no ejecutó la orden: {reason}")
        return Fill(str(fill.get("id", "")), order.instrument, order.direction, float(units),
                    float(fill.get("price", price or 0)), self.name, False, raw={"environment": self.environment})

    def positions(self) -> list[dict]:
        data = self._call("GET", "/openPositions")
        return [{"instrument": p["instrument"], "long": p["long"].get("units"), "short": p["short"].get("units")}
                for p in data.get("positions", [])]

    def close(self, position_id: str) -> dict:
        data = self._call("PUT", f"/positions/{position_id}/close", json={"longUnits": "ALL", "shortUnits": "ALL"})
        return {"id": position_id, "closed": True, "raw_keys": sorted(data)}


class IbkrBroker:
    """Interactive Brokers por TWS/IB Gateway. La orden entra a mercado con stop y objetivo colgados (bracket)."""

    name = "ibkr"
    simulated = False

    def __init__(self, session: ibkr.IbkrSession) -> None:
        self._s = session
        self.environment = session.settings.environment

    def _wrap(self, fn, *args):
        try:
            return self._s.run(fn, *args)
        except ibkr.IbkrError as exc:
            raise BrokerError(str(exc)) from None

    def place(self, order: Order, price: float | None = None) -> Fill:
        units = int(round(order.units))
        if units <= 0:
            raise BrokerError("unidades inválidas")
        api, acct = self._s.api, self._s.settings.account
        entry_side, exit_side = ("BUY", "SELL") if order.direction == "long" else ("SELL", "BUY")

        def job(ib):
            contract = api.Forex(ibkr.pair_symbol(order.instrument))
            ib.qualifyContracts(contract)
            parent_id = ib.client.getReqId()
            parent = api.MarketOrder(entry_side, units, orderId=parent_id, transmit=False, orderRef=f"raphael:{order.ref}"[:64])
            tp = api.LimitOrder(exit_side, units, round(order.tp, 3), orderId=parent_id + 1, parentId=parent_id, transmit=False)
            sl = api.StopOrder(exit_side, units, round(order.sl, 3), orderId=parent_id + 2, parentId=parent_id, transmit=True)
            for o in (parent, tp, sl):
                if acct:
                    o.account = acct
            trades = [ib.placeOrder(contract, o) for o in (parent, tp, sl)]
            ib.sleep(1)
            status = trades[0].orderStatus
            if status.status in ("Cancelled", "ApiCancelled", "Inactive"):
                raise ibkr.IbkrError(f"IB no aceptó la orden ({status.status})")
            return parent_id, float(getattr(status, "avgFillPrice", 0) or 0)
        oid, avg = self._wrap(job)
        return Fill(str(oid), order.instrument, order.direction, float(units), avg or price or 0.0, self.name, False,
                    raw={"environment": self.environment})

    def positions(self) -> list[dict]:
        def job(ib):
            return [{"id": p.contract.symbol + p.contract.currency, "instrument": f"{p.contract.symbol}/{p.contract.currency}",
                     "units": float(p.position), "avg_price": float(p.avgCost)} for p in ib.positions() if p.position]
        return self._wrap(job)

    def close(self, position_id: str) -> dict:
        api = self._s.api

        def job(ib):
            for p in ib.positions():
                if p.contract.symbol + p.contract.currency == position_id and p.position:
                    side = "SELL" if p.position > 0 else "BUY"
                    ib.placeOrder(p.contract, api.MarketOrder(side, abs(p.position)))
                    ib.sleep(1)
                    return True
            return False
        if not self._wrap(job):
            raise BrokerError(f"no hay posición abierta {position_id}")
        return {"id": position_id, "closed": True}


def make_broker(adapter: str, environment: str, *, env: dict | None = None,
                transport: httpx.BaseTransport | None = None, ibkr_session: ibkr.IbkrSession | None = None
                ) -> tuple[Broker, str]:
    """El broker pedido, o el simulado con el motivo si falta algo. Devuelve (broker, nota)."""
    if adapter == "ibkr":
        try:
            session = ibkr_session or ibkr.get_session(environment, env)
            if ibkr_session is None and not ibkr.available():
                return SimulatedBroker(), "falta instalar ib_async (pip install ib_async): uso el broker simulado"
            return IbkrBroker(session), ""
        except ibkr.IbkrError as exc:
            return SimulatedBroker(), f"{exc}: uso el broker simulado"
    if adapter != "oanda":
        return SimulatedBroker(), ""
    try:
        return OandaBroker(environment=environment, env=env, transport=transport), ""
    except BrokerError as exc:
        return SimulatedBroker(), f"{exc}: uso el broker simulado"
