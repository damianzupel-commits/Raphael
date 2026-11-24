#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Esses Signals — Fase 2: motor de DECISIÓN + RIESGO.

Toma el análisis SMC (esses_engine) y aplica el pipeline E1-E6 del método:
  E1 contexto/bias -> E2 estructura -> E3 trigger smart money (sweep + POI en
  discount/premium + confirmación) -> E4 riesgo (sizing, SL/TP, R:R) -> E5 filtros
  "no operar" -> E6 (journal, en Fase 3).

Devuelve una SEÑAL TIPADA (dirección, entrada, SL, TP, R:R, tags, confianza).
NUNCA ejecuta órdenes ni mueve dinero. No es asesoramiento financiero.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal
try:
    from . import engine as E
except ImportError:
    import engine as E


# ─────────────────────────────────────────────────────────────────────────────
# Riesgo
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RiskConfig:
    account: float = 10000.0       # tamaño de cuenta
    risk_pct: float = 1.0          # % de la cuenta por trade
    min_rr: float = 2.0            # R:R mínimo aceptable
    value_per_point: float = 1.0   # $ por punto por unidad (depende del instrumento)
    min_conf: float = 0.6          # confianza mínima para aceptar (perilla de WR)


def position_size(cfg: RiskConfig, entry: float, sl: float) -> dict:
    risk_cash = cfg.account * cfg.risk_pct / 100.0
    stop_dist = abs(entry - sl)
    if stop_dist <= 0:
        return {"units": 0.0, "risk_cash": risk_cash, "stop_dist": 0.0}
    units = risk_cash / (stop_dist * cfg.value_per_point)
    return {"units": round(units, 4), "risk_cash": round(risk_cash, 2),
            "stop_dist": round(stop_dist, 4)}


def rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return round(reward / risk, 2) if risk > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Señal
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Signal:
    i: int
    direction: Literal["long", "short"]
    entry: float
    sl: float
    tp: float
    rr: float
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    zone: str = ""
    size: dict = field(default_factory=dict)
    notes: str = ""
    valid: bool = True
    reject_reason: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Filtros "no operar" (E5). news_windows: lista de índices donde hay noticia.
# ─────────────────────────────────────────────────────────────────────────────
def no_trade_filters(candles: List[E.Candle], i: int,
                     news_windows: Optional[List[int]] = None) -> Optional[str]:
    if news_windows and i in set(news_windows):
        return "noticia de alto impacto en la ventana"
    # rango muy chico (sin volatilidad) -> setup poco fiable
    look = candles[max(0, i - 20):i + 1]
    if look:
        rng = max(c.h for c in look) - min(c.l for c in look)
        if rng <= 0:
            return "sin rango / datos planos"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Generador de señal (E1-E5)  —  modelo: sweep -> POI en zona -> confirmación
# ─────────────────────────────────────────────────────────────────────────────
def generate_signal(candles: List[E.Candle], cfg: Optional[RiskConfig] = None,
                    lookback: int = 8,
                    news_windows: Optional[List[int]] = None) -> Optional[Signal]:
    cfg = cfg or RiskConfig()
    if len(candles) < 30:
        return None
    a = E.analyze(candles)
    i = len(candles) - 1
    last = candles[i]
    pd = a["premium_discount"]
    zone = a["price_zone"]
    tags: List[str] = []
    conf = 0.0

    # E5 — filtros duros primero
    reason = no_trade_filters(candles, i, news_windows)
    if reason:
        return Signal(i, "long", last.c, last.c, last.c, 0, ["no-trade"], 0.0,
                      zone, valid=False, reject_reason=reason)

    # E3 — ¿hubo un sweep reciente?
    recent_sweeps = [s for s in a["sweeps"] if i - s.i <= lookback]
    if not recent_sweeps:
        return None
    sweep = recent_sweeps[-1]
    tags.append(f"sweep-{sweep.side}")
    conf += 0.3

    # dirección: un sweep de sell-side (barrió mínimos) sesga LONG; buy-side -> SHORT
    direction = "long" if sweep.side == "sell" else "short"

    # E1/E2 — confluencia con estructura y zona
    trend = a["trend"]
    if (direction == "long" and trend in ("up", "range")) or \
       (direction == "short" and trend in ("down", "range")):
        conf += 0.15
        tags.append(f"trend-{trend}")
    if (direction == "long" and zone == "discount") or \
       (direction == "short" and zone == "premium"):
        conf += 0.2
        tags.append(f"zone-{zone}")

    # E3 — POI: IFVG primero (el modelo de Fede), luego FVG, luego OB
    poi = None
    poi_kind = None
    want = "bull" if direction == "long" else "bear"
    cand_ifvg = [iv for iv in a.get("ifvgs", []) if iv.direction == want]
    for iv in reversed(cand_ifvg):
        if iv.bottom <= last.c * 1.02 and iv.top >= last.c * 0.98:
            poi = (iv.bottom, iv.top); poi_kind = "IFVG"; break
    cand_fvgs = [] if poi else [g for g in a["fvgs"] if not g.filled and
                 g.direction == ("bull" if direction == "long" else "bear")]
    for g in reversed(cand_fvgs):
        if g.bottom <= last.c * 1.02 and g.top >= last.c * 0.98:
            poi = (g.bottom, g.top); poi_kind = "FVG"; break
    if poi is None:
        cand_obs = [o for o in a["order_blocks"] if
                    o.direction == ("bull" if direction == "long" else "bear")]
        for o in reversed(cand_obs):
            if o.bottom <= last.c * 1.02 and o.top >= last.c * 0.98:
                poi = (o.bottom, o.top); poi_kind = "OB"; break
    if poi:
        conf += 0.25 if poi_kind == "IFVG" else 0.2
        tags.append(f"poi-{poi_kind}")

    # E3b — inducement barrido antes del quiebre = confluencia del modelo de Fede
    ind = a.get("inducement")
    if ind and ind.get("taken"):
        if (direction == "long" and ind["side"] == "sell") or \
           (direction == "short" and ind["side"] == "buy"):
            conf += 0.1
            tags.append("inducement")

    # E3 — confirmación de cambio (proxy de CISD): último evento estructural a favor
    recent_struct = [e for e in a["structure"] if i - e.i <= lookback]
    if recent_struct:
        last_ev = recent_struct[-1]
        if (direction == "long" and last_ev.direction == "bull") or \
           (direction == "short" and last_ev.direction == "bear"):
            conf += 0.15
            tags.append(f"confirm-{last_ev.kind}")

    # E4 — niveles: entrada, SL detrás del sweep/POI, TP en liquidez opuesta
    entry = last.c
    if direction == "long":
        sl = sweep.level - (abs(sweep.level) * 0.001) - (last.h - last.l)
        if poi:
            sl = min(sl, poi[0])
        opp = [lv.price for lv in a["liquidity"] if lv.side == "buy" and lv.price > entry]
        tp = min(opp) if opp else pd["top"] if pd else entry + (entry - sl) * cfg.min_rr
    else:
        sl = sweep.level + (abs(sweep.level) * 0.001) + (last.h - last.l)
        if poi:
            sl = max(sl, poi[1])
        opp = [lv.price for lv in a["liquidity"] if lv.side == "sell" and lv.price < entry]
        tp = max(opp) if opp else pd["bottom"] if pd else entry - (sl - entry) * cfg.min_rr

    # guard de stop mínimo: evita stops microscópicos que inflan el tamaño.
    # mínimo = 0.5 * rango promedio de las últimas 14 velas (proxy de ATR).
    look = candles[max(0, i - 14):i + 1]
    atr = sum(c.h - c.l for c in look) / max(len(look), 1)
    min_stop = 0.5 * atr
    if abs(entry - sl) < min_stop:
        sl = entry - min_stop if direction == "long" else entry + min_stop
        tags.append("sl-ajustado-min")

    r = rr(entry, sl, tp)
    size = position_size(cfg, entry, sl)

    sig = Signal(i, direction, round(entry, 4), round(sl, 4), round(tp, 4), r,
                 tags, round(min(conf, 1.0), 2), zone, size)

    # E4/E5 — validaciones finales
    if r < cfg.min_rr:
        sig.valid = False
        sig.reject_reason = f"R:R {r} < mínimo {cfg.min_rr}"
    if not poi:
        sig.valid = False
        sig.reject_reason = "sin POI (FVG/OB) válido en la zona"
    if sig.confidence < cfg.min_conf:
        sig.valid = False
        sig.reject_reason = (sig.reject_reason + "; " if sig.reject_reason else "") + \
                            f"confianza baja ({sig.confidence} < {cfg.min_conf})"
    return sig


if __name__ == "__main__":
    candles = E.synth(seed=7)
    cfg = RiskConfig(account=10000, risk_pct=1.0, min_rr=2.0, value_per_point=1.0)
    print("=== Esses Signals — demo (pipeline E1-E5) ===")
    # correr el generador vela a vela y contar señales válidas
    valid, rejected = [], 0
    for end in range(40, len(candles)):
        s = generate_signal(candles[:end + 1], cfg)
        if s is None:
            continue
        if s.valid:
            valid.append(s)
        else:
            rejected += 1
    print(f"Señales válidas: {len(valid)}  |  descartadas por gates: {rejected}")
    print("\nÚltimas 3 señales válidas:")
    for s in valid[-3:]:
        print(f"  vela {s.i}: {s.direction.upper()} entry={s.entry} SL={s.sl} "
              f"TP={s.tp} R:R={s.rr} conf={s.confidence}")
        print(f"     tags: {', '.join(s.tags)}  | size={s.size['units']} u "
              f"(riesgo ${s.size['risk_cash']})")
    if not valid:
        print("  (sin señales A+ en esta corrida — el gate está filtrando bien)")
