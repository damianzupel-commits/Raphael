"""Endpoints HTTP de la Brigada de Trading (la pestaña "Trading" de la ventana de
Raphael). Corre la brigada de trading (estaciones T1-T7, modelo IFVG de Fede Esses)
y devuelve el veredicto + el estado por estación, igual que la Brigada de Auditoría.

ADITIVO. NO ejecuta órdenes ni mueve dinero: solo analiza y propone; el humano
decide. No es asesoramiento financiero.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import verify_api_key
from ..harness.trading_brigade import run_trading_brigade
from ..trading import backtest as bt
from ..trading import signals as S

router = APIRouter(prefix="/api/trading", tags=["trading"], dependencies=[Depends(verify_api_key)])


class TradingRunIn(BaseModel):
    instrument: str = "DEMO"
    source: str | None = None          # "ccxt" | "yfinance" | None
    timeframe: str = "15m"
    limit: int = 500
    demo: bool = False
    seed: int = 7
    account: float = 10000.0
    risk_pct: float = 1.0
    min_rr: float = 2.0
    min_conf: float = 0.6              # perilla de win rate
    value_per_point: float = 1.0
    candles: list | None = None
    news_windows: list | None = None


def _fetch(source: str, instrument: str, timeframe: str, limit: int):
    """Best-effort: trae velas reales si la librería está instalada. Si no, None
    y la brigada cae a modo demo (así la pestaña siempre muestra algo)."""
    try:
        if source == "ccxt":
            import ccxt  # type: ignore
            ex = ccxt.binance()
            return ex.fetch_ohlcv(instrument, timeframe=timeframe, limit=limit)
        if source == "yfinance":
            import yfinance as yf  # type: ignore
            df = yf.download(instrument, interval=timeframe, period="60d", progress=False)
            return [[i, float(r["Open"]), float(r["High"]), float(r["Low"]),
                     float(r["Close"]), float(r.get("Volume", 0) or 0)]
                    for i, (_, r) in enumerate(df.iterrows())]
    except Exception:  # noqa: BLE001 -- best-effort; si falla, demo
        return None
    return None


def _resolve_candles(body: TradingRunIn):
    """Devuelve (candles_list_of_Candle, modo_str). Demo si no hay datos reales."""
    from ..trading import engine as E
    if not body.demo and body.candles:
        raw = body.candles
    elif not body.demo and body.source:
        raw = _fetch(body.source or "", body.instrument, body.timeframe, body.limit)
    else:
        raw = None
    if not raw:
        return E.synth(n=500, seed=body.seed), "demo"
    out = []
    for i, c in enumerate(raw):
        if isinstance(c, dict):
            out.append(E.Candle(c.get("t", i), float(c["o"]), float(c["h"]),
                                float(c["l"]), float(c["c"]), float(c.get("v", 0))))
        else:
            t, o, h, l, cl, *rest = c
            out.append(E.Candle(t, float(o), float(h), float(l), float(cl),
                                float(rest[0]) if rest else 0.0))
    return out, "real"


@router.post("/brigada/run")
async def run_trading(body: TradingRunIn) -> dict:
    """Corre la Brigada de Trading. Modos: demo (sintético), candles directas, o
    fetch por instrument+source. Devuelve veredicto + estaciones + señal."""
    payload = body.model_dump()
    if not payload.get("demo") and not payload.get("candles") and payload.get("source"):
        fetched = _fetch(body.source or "", body.instrument, body.timeframe, body.limit)
        if fetched:
            payload["candles"] = fetched
        else:
            payload["demo"] = True  # fallback: la pestaña muestra algo igual
    if not payload.get("demo") and not payload.get("candles"):
        payload["demo"] = True
    return await run_trading_brigade(payload)


@router.post("/backtest/run")
async def run_backtest(body: TradingRunIn) -> dict:
    """Corre el backtest sobre histórico y devuelve estadística (win rate,
    expectativa, R total, drawdown, por setup). Perillas: min_rr, min_conf."""
    candles, modo = _resolve_candles(body)
    cfg = S.RiskConfig(account=body.account, risk_pct=body.risk_pct,
                       min_rr=body.min_rr, value_per_point=body.value_per_point,
                       min_conf=body.min_conf)
    st = bt.simulate(candles, cfg)
    st.pop("_trades", None)  # JSON-safe (los objetos Trade no se serializan)
    st["modo"] = modo
    st["velas"] = len(candles)
    st["config"] = {"min_rr": body.min_rr, "min_conf": body.min_conf,
                    "risk_pct": body.risk_pct, "account": body.account}
    return st
