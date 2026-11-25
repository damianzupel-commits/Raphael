"""Lógica común de los tres cocineros: analizar un instrumento y armar la señal con su id. Sin efectos."""

from __future__ import annotations

from dataclasses import asdict

import httpx

from . import engine as E
from . import signals as S
from .config import Instrument, TradingConfig
from .data import load_candles

DISCLAIMER = "Solo análisis: la decisión y la ejecución son tuyas. No es asesoramiento financiero."


def value_per_point(inst: Instrument, price: float) -> float:
    if inst.value_per_point:
        return inst.value_per_point
    return round(1.0 / price, 8) if inst.name.upper().endswith("/JPY") and price else 1.0


def risk_config(cfg: TradingConfig, inst: Instrument, price: float) -> S.RiskConfig:
    r = cfg.risk
    return S.RiskConfig(account=r.account, risk_pct=r.risk_pct, min_rr=r.min_rr,
                        value_per_point=value_per_point(inst, price), min_conf=r.min_conf)


def analyze(cfg: TradingConfig, inst: Instrument, env: dict | None = None,
            transport: httpx.BaseTransport | None = None) -> dict:
    """Corre el motor sobre las últimas velas. Devuelve la señal (o None), de dónde salieron los datos y el veredicto."""
    candles, source = load_candles(cfg, inst, env=env, transport=transport)
    out = {"instrument": inst.name, "timeframe": inst.timeframe,
           "source": {"kind": source.kind, "simulated": source.simulated, "note": source.note},
           "candles": len(candles), "signal": None, "verdict": "ESPERAR", "reason": "", "disclaimer": DISCLAIMER}
    if len(candles) < 30:
        out["reason"] = f"pocas velas ({len(candles)}), necesito al menos 30"
        return out
    last = candles[-1]
    a = E.analyze(candles)
    out["trend"], out["zone"], out["last_price"] = a["trend"], a["price_zone"], last.c
    sig = S.generate_signal(candles, risk_config(cfg, inst, last.c))
    if sig is None:
        out["reason"] = "sin gatillo: no hubo toma de liquidez reciente"
        return out
    d = asdict(sig)
    d["id"] = f"{inst.name}:{last.t}:{sig.direction}"
    d["instrument"] = inst.name
    out["signal"] = d
    if sig.valid:
        out["verdict"] = "OPERAR"
    else:
        out["reason"] = sig.reject_reason
    return out
