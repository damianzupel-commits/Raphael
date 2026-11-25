#!/usr/bin/env python3
"""
Esses Backtest — Fase 3: simula el motor sobre histórico y saca estadística.

Recorre las velas, genera señales (esses_signals), simula cada trade hacia
adelante (¿toca antes SL o TP?) y reporta win rate, expectativa, R total,
drawdown y desglose por tipo de setup.

Conservador: si en una misma vela se tocan SL y TP, cuenta PÉRDIDA (no sabemos
el orden intrabar sin datos de menor timeframe).

NO ejecuta órdenes ni mueve dinero. No es asesoramiento financiero. Un backtest
positivo NO garantiza resultados en vivo.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import engine as E
from . import signals as S


@dataclass
class Trade:
    i_entry: int
    i_exit: int
    direction: str
    entry: float
    sl: float
    tp: float
    r_planned: float
    r_result: float   # +r_planned si ganó, -1 si perdió, 0 si expiró
    outcome: str      # win | loss | expired
    tags: list[str]


def simulate(candles: list[E.Candle], cfg: S.RiskConfig | None = None,
             max_hold: int = 60, warmup: int = 40) -> dict:
    cfg = cfg or S.RiskConfig()
    trades: list[Trade] = []
    i = warmup
    n = len(candles)
    while i < n - 1:
        sig = S.generate_signal(candles[:i + 1], cfg)
        if not sig or not sig.valid:
            i += 1
            continue
        # entrar en la vela siguiente
        entry = sig.entry
        exit_i, r_res, outcome = None, 0.0, "expired"
        for j in range(i + 1, min(i + 1 + max_hold, n)):
            c = candles[j]
            hit_sl = c.l <= sig.sl if sig.direction == "long" else c.h >= sig.sl
            hit_tp = c.h >= sig.tp if sig.direction == "long" else c.l <= sig.tp
            if hit_sl and hit_tp:
                exit_i, r_res, outcome = j, -1.0, "loss"; break   # conservador
            if hit_sl:
                exit_i, r_res, outcome = j, -1.0, "loss"; break
            if hit_tp:
                exit_i, r_res, outcome = j, sig.rr, "win"; break
        if exit_i is None:
            exit_i = min(i + max_hold, n - 1)
        trades.append(Trade(i, exit_i, sig.direction, entry, sig.sl, sig.tp,
                            sig.rr, round(r_res, 2), outcome, sig.tags))
        i = exit_i + 1   # una operación a la vez (sin solapamiento)
    return _stats(trades)


def _stats(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "msg": "sin trades"}
    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    total_r = sum(t.r_result for t in trades)
    win_rate = len(wins) / n
    expectancy = total_r / n  # R esperado por trade
    avg_win = (sum(t.r_result for t in wins) / len(wins)) if wins else 0.0
    # drawdown en R sobre la curva acumulada
    eq, peak, dd = 0.0, 0.0, 0.0
    for t in trades:
        eq += t.r_result
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    # desglose por tag principal
    by_tag = {}
    for t in trades:
        key = next((tg for tg in t.tags if tg.startswith("poi-")), "poi-?")
        d = by_tag.setdefault(key, {"n": 0, "w": 0, "r": 0.0})
        d["n"] += 1; d["w"] += 1 if t.outcome == "win" else 0; d["r"] += t.r_result
    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "expired": n - len(wins) - len(losses),
        "win_rate": round(win_rate, 3),
        "expectancy_R": round(expectancy, 3),
        "total_R": round(total_r, 2),
        "avg_win_R": round(avg_win, 2),
        "max_drawdown_R": round(dd, 2),
        "by_setup": {k: {"n": v["n"], "win_rate": round(v["w"] / v["n"], 2),
                         "total_R": round(v["r"], 2)} for k, v in by_tag.items()},
        "_trades": trades,
    }


def print_report(st: dict, cfg: S.RiskConfig):
    print("=== Esses Backtest — reporte ===")
    if st["trades"] == 0:
        print("Sin trades."); return
    print(f"Trades: {st['trades']}  (ganados {st['wins']} / perdidos {st['losses']}"
          f" / expirados {st['expired']})")
    print(f"Win rate: {st['win_rate']*100:.1f}%")
    print(f"Expectativa: {st['expectancy_R']} R por trade  "
          f"({'POSITIVA' if st['expectancy_R']>0 else 'negativa'})")
    print(f"R total: {st['total_R']}   |  R promedio por ganada: {st['avg_win_R']}")
    print(f"Máx drawdown: {st['max_drawdown_R']} R")
    # traducción a dinero con el riesgo configurado
    risk_cash = cfg.account * cfg.risk_pct / 100.0
    print(f"En $ (riesgo ${risk_cash:.0f}/trade): "
          f"P&L ≈ ${st['total_R']*risk_cash:.0f}  |  DD ≈ ${st['max_drawdown_R']*risk_cash:.0f}")
    print("\nPor tipo de POI:")
    for k, v in st["by_setup"].items():
        print(f"  {k}: {v['n']} trades, win {v['win_rate']*100:.0f}%, {v['total_R']:+.1f} R")
