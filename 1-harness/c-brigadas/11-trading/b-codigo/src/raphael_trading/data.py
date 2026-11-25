"""Adaptadores de DATOS de mercado (velas OHLC). Uno simulado, uno CSV y uno real (OANDA v20, solo lectura).

Todos devuelven `list[Candle]` y un `Source` que dice de dónde salió (para que nunca se confunda lo simulado con
lo real). La clave del real sale de `OANDA_API_TOKEN` (variable de entorno); sin ella se usa el simulado y el
`Source.note` lo avisa.
"""

from __future__ import annotations

import csv
import os
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from . import engine as E
from .config import Instrument, TradingConfig

OANDA_HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}
GRANULARITY = {"1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30", "1h": "H1", "4h": "H4", "1d": "D"}


@dataclass
class Source:
    kind: str          # simulado | csv | oanda
    simulated: bool
    note: str = ""


def oanda_instrument(name: str) -> str:
    return name.replace("/", "_").upper()


def simulated_candles(inst: Instrument, n: int, seed: int | None = None) -> list[E.Candle]:
    seed = seed if seed is not None else zlib.crc32(inst.name.encode()) % 10_000  # crc32 y no hash(): hash varía por proceso
    return E.synth(n=n, seed=seed, start=inst.sim_start, scale=inst.sim_scale)


def csv_candles(path: str, n: int) -> list[E.Candle]:
    out: list[E.Candle] = []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            out.append(E.Candle(i, float(row["o"]), float(row["h"]), float(row["l"]), float(row["c"]),
                                float(row.get("v") or 0)))
    return out[-n:]


def oanda_candles(inst: Instrument, n: int, *, env: dict | None = None, transport: httpx.BaseTransport | None = None,
                  environment: str = "practice") -> list[E.Candle]:
    env = os.environ if env is None else env
    token = env.get("OANDA_API_TOKEN", "")
    params = {"granularity": GRANULARITY.get(inst.timeframe, "H1"), "count": n, "price": "M"}
    url = f"{OANDA_HOSTS[environment]}/v3/instruments/{oanda_instrument(inst.name)}/candles"
    with httpx.Client(transport=transport, timeout=15) as cl:
        r = cl.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    out = []
    for i, c in enumerate(r.json().get("candles", [])):
        if not c.get("complete", True):
            continue                                    # la vela en curso no se usa: no está cerrada
        m = c["mid"]
        t = int(datetime.fromisoformat(c["time"][:19]).replace(tzinfo=UTC).timestamp()) if c.get("time") else i
        out.append(E.Candle(t, float(m["o"]), float(m["h"]), float(m["l"]), float(m["c"]), float(c.get("volume", 0))))
    return out


def load_candles(cfg: TradingConfig, inst: Instrument, *, env: dict | None = None,
                 transport: httpx.BaseTransport | None = None) -> tuple[list[E.Candle], Source]:
    """Velas del instrumento según `cfg.data.adapter`; si el real no se puede usar, cae al simulado y lo dice."""
    env = os.environ if env is None else env
    n = cfg.data.candles
    kind = cfg.data.adapter
    if kind == "csv":
        if not cfg.data.csv_path or not Path(cfg.data.csv_path).is_file():
            return simulated_candles(inst, n, cfg.data.sim_seed), Source("simulado", True, "no encuentro el CSV: uso simulados")
        return csv_candles(cfg.data.csv_path, n), Source("csv", False)
    if kind == "oanda":
        if not env.get("OANDA_API_TOKEN"):
            return simulated_candles(inst, n, cfg.data.sim_seed), Source("simulado", True, "falta OANDA_API_TOKEN: uso simulados")
        try:
            candles = oanda_candles(inst, n, env=env, transport=transport, environment=cfg.broker.environment)
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            note = f"OANDA no respondió ({type(exc).__name__}): uso simulados"
            return simulated_candles(inst, n, cfg.data.sim_seed), Source("simulado", True, note)
        return candles, Source("oanda", False)
    return simulated_candles(inst, n, cfg.data.sim_seed), Source("simulado", True)
