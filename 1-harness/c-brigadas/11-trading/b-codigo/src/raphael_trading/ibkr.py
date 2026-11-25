"""Adaptador de Interactive Brokers (TWS o IB Gateway abierto en la PC de Damián) para datos y órdenes.

Usa la librería `ib_async` (opcional: `pip install ib_async`). Todo el trato con IB corre en UN hilo propio con su propio
loop de asyncio (la librería es asíncrona por dentro y el harness ya tiene un loop). Se conecta recién al primer uso.

Seguridad:
- Cuenta demo (`practice`): puerto 4002 (Gateway) o 7497 (TWS), por defecto 4002. Exige que TODAS las cuentas de la sesión
  sean paper (empiezan con `DU`): si no, se niega. La cuenta real (`live`) exige además `TRADING_ALLOW_LIVE=1`.
- Las órdenes solo salen desde `IbkrBroker.place` / `close`, que el cocinero llama ya aprobadas por Damián.
Variables de entorno (ver `.env.plantilla`): IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID, IBKR_ACCOUNT. No hay claves: el login
lo hace Damián en TWS/Gateway.

NO probado contra un IB real (sin cuenta todavía): los tests usan un `ib_async` falso que replica las llamadas. Primera
prueba real: cuenta demo, una orden chica, mirar que stop y objetivo queden colgados en TWS.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC

from . import engine as E

BAR_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
BAR_SIZE = {"1m": "1 min", "5m": "5 mins", "15m": "15 mins", "30m": "30 mins", "1h": "1 hour", "4h": "4 hours", "1d": "1 day"}
DEFAULT_PORT = {"practice": 4002, "live": 4001}


class IbkrError(Exception):
    """Falló la conexión o IB rechazó el pedido. El mensaje es para la persona."""


def available() -> bool:
    return importlib.util.find_spec("ib_async") is not None


def pair_symbol(name: str) -> str:
    return name.replace("/", "").upper()


@dataclass
class IbkrSettings:
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 7
    account: str = ""
    environment: str = "practice"

    @classmethod
    def from_env(cls, environment: str, env: dict | None = None) -> IbkrSettings:
        env = os.environ if env is None else env
        if environment == "live" and env.get("TRADING_ALLOW_LIVE") != "1":
            raise IbkrError("cuenta real bloqueada: falta TRADING_ALLOW_LIVE=1 (decisión explícita de Damián)")
        try:
            return cls(env.get("IBKR_HOST", "127.0.0.1"), int(env.get("IBKR_PORT") or DEFAULT_PORT[environment]),
                       int(env.get("IBKR_CLIENT_ID") or 7), env.get("IBKR_ACCOUNT", ""), environment)
        except ValueError:
            raise IbkrError("IBKR_PORT e IBKR_CLIENT_ID tienen que ser números") from None


class IbkrSession:
    """Una conexión a TWS/Gateway y el hilo donde vive. `api` es el módulo `ib_async` (o uno falso en los tests)."""

    def __init__(self, settings: IbkrSettings, api=None) -> None:
        self.settings = settings
        self._api = api
        self._ib = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ibkr")

    @property
    def api(self):
        if self._api is None:
            try:
                self._api = importlib.import_module("ib_async")
            except ImportError:
                raise IbkrError("falta instalar la librería: pip install ib_async") from None
        return self._api

    def run(self, fn, *args):
        """Corre `fn(ib, *args)` en el hilo de IB, conectando si hace falta."""
        def job():
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
            return fn(self._connected(), *args)
        try:
            return self._pool.submit(job).result(timeout=60)
        except IbkrError:
            raise
        except (OSError, TimeoutError, ConnectionError) as exc:
            self._ib = None
            raise IbkrError(f"no pude hablar con TWS/IB Gateway en {self.settings.host}:{self.settings.port} "
                            f"({type(exc).__name__}): ¿está abierto, con la sesión iniciada y la API activada?") from None

    def _connected(self):
        s = self.settings
        if self._ib is not None and self._ib.isConnected():
            return self._ib
        ib = self.api.IB()
        ib.connect(s.host, s.port, clientId=s.client_id, readonly=False, timeout=10)
        accounts = list(ib.managedAccounts())
        if s.environment == "practice" and any(not a.startswith("DU") for a in accounts):
            ib.disconnect()
            raise IbkrError("la sesión de IB tiene una cuenta que NO es demo (paper) y Trading está en 'practice': "
                            "abrí TWS/Gateway con la cuenta paper")
        if s.account and accounts and s.account not in accounts:
            ib.disconnect()
            raise IbkrError(f"la cuenta {s.account} no está en la sesión de IB")
        self._ib = ib
        return ib

    def close(self) -> None:
        if self._ib is not None:
            self._pool.submit(self._ib.disconnect).result(timeout=10)
            self._ib = None


_SESSIONS: dict[tuple, IbkrSession] = {}


def get_session(environment: str, env: dict | None = None) -> IbkrSession:
    s = IbkrSettings.from_env(environment, env)
    key = (s.host, s.port, s.client_id, s.environment)
    if key not in _SESSIONS:
        _SESSIONS[key] = IbkrSession(s)
    return _SESSIONS[key]


def fetch_candles(session: IbkrSession, name: str, timeframe: str, n: int) -> list[E.Candle]:
    secs = BAR_SECONDS.get(timeframe, 3600)
    days = max(1, math.ceil(n * secs / 86400 * 1.6))   # el forex no opera todo el tiempo: pido de más y me quedo con las últimas
    api = session.api

    def job(ib):
        contract = api.Forex(pair_symbol(name))
        ib.qualifyContracts(contract)
        size = BAR_SIZE.get(timeframe, "1 hour")
        return ib.reqHistoricalData(contract, endDateTime="", durationStr=f"{days} D", barSizeSetting=size,
                                    whatToShow="MIDPOINT", useRTH=False, formatDate=2)
    bars = list(session.run(job))[:-1]               # la última barra está en curso: no se usa
    out = [E.Candle(int(b.date.replace(tzinfo=b.date.tzinfo or UTC).timestamp()), float(b.open), float(b.high),
                    float(b.low), float(b.close), float(b.volume or 0)) for b in bars]
    return out[-n:]
