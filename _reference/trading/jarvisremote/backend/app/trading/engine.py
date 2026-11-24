#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Esses Engine — Fase 1: motor de detección Smart Money Concepts (SMC).

Agnóstico al instrumento: trabaja sobre velas OHLC (funciona igual para NQ,
EURUSD, oro o cripto). Sin dependencias externas (solo stdlib), así corre en
cualquier lado. Los adaptadores de datos reales (yfinance/ccxt/OANDA) van aparte
y se corren en la PC de Damian; acá el motor recibe una lista de Candle.

Detecta: swings, tendencia, BOS/CHoCH, FVG, order blocks, niveles de liquidez,
tomas de liquidez (sweeps) y premium/discount (cuartos).

Método: ver METODO-Esses-Bootcamp-50-dias.md (§ Fase 1 y 2).
NO ejecuta órdenes ni mueve dinero. No es asesoramiento financiero.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal
import math
import random


# ─────────────────────────────────────────────────────────────────────────────
# Modelo de datos
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Candle:
    t: int            # timestamp (índice o epoch)
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

    @property
    def bullish(self) -> bool:
        return self.c >= self.o

    @property
    def body_hi(self) -> float:
        return max(self.o, self.c)

    @property
    def body_lo(self) -> float:
        return min(self.o, self.c)


@dataclass
class Swing:
    i: int
    price: float
    kind: Literal["high", "low"]


@dataclass
class StructureEvent:
    i: int
    kind: Literal["BOS", "CHoCH"]
    direction: Literal["bull", "bear"]
    level: float


@dataclass
class FVG:
    i: int                 # índice de la vela central del gap
    direction: Literal["bull", "bear"]
    top: float
    bottom: float
    filled: bool = False


@dataclass
class IFVG:
    """Inverse Fair Value Gap: un FVG que el precio atravesó y cerró del otro
    lado -> cambia de polaridad y pasa a ser POI en la dirección contraria.
    Es el corazón del modelo de Fede Esses."""
    i: int                 # índice del FVG original
    i_flip: int            # vela donde se invirtió (cerró del otro lado)
    direction: Literal["bull", "bear"]   # dirección NUEVA (a favor de la que entra)
    top: float
    bottom: float
    used: bool = False     # ya retesteado por el precio


@dataclass
class OrderBlock:
    i: int
    direction: Literal["bull", "bear"]
    top: float
    bottom: float


@dataclass
class LiquidityLevel:
    i: int
    price: float
    side: Literal["buy", "sell"]   # buy-side = sobre máximos; sell-side = bajo mínimos
    equal: bool = False            # parte de equal highs/lows


@dataclass
class Sweep:
    i: int
    side: Literal["buy", "sell"]   # buy = barrió liquidez de compra (máximos) -> sesgo short
    level: float


# ─────────────────────────────────────────────────────────────────────────────
# 1. Swings (fractales)
# ─────────────────────────────────────────────────────────────────────────────
def find_swings(candles: List[Candle], k: int = 2) -> List[Swing]:
    """Swing high: h[i] estrictamente mayor a los k vecinos de cada lado. Idem low."""
    swings: List[Swing] = []
    n = len(candles)
    for i in range(k, n - k):
        hi = candles[i].h
        lo = candles[i].l
        is_high = all(hi > candles[j].h for j in range(i - k, i)) and \
                  all(hi > candles[j].h for j in range(i + 1, i + k + 1))
        is_low = all(lo < candles[j].l for j in range(i - k, i)) and \
                 all(lo < candles[j].l for j in range(i + 1, i + k + 1))
        if is_high:
            swings.append(Swing(i, hi, "high"))
        if is_low:
            swings.append(Swing(i, lo, "low"))
    swings.sort(key=lambda s: s.i)
    return swings


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tendencia (a partir de swings)
# ─────────────────────────────────────────────────────────────────────────────
def trend_from_swings(swings: List[Swing]) -> Literal["up", "down", "range"]:
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "range"
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    lh = highs[-1].price < highs[-2].price
    ll = lows[-1].price < lows[-2].price
    if hh and hl:
        return "up"
    if lh and ll:
        return "down"
    return "range"


# ─────────────────────────────────────────────────────────────────────────────
# 3. BOS / CHoCH  (quiebre de estructura / cambio de carácter)
# ─────────────────────────────────────────────────────────────────────────────
def structure_events(candles: List[Candle], swings: List[Swing]) -> List[StructureEvent]:
    """
    Recorre las velas y, cada vez que el CIERRE rompe el último swing high/low
    confirmado, emite un evento. En tendencia alcista, romper el último high =
    BOS bull (continuación); romper el último low = CHoCH bear (posible giro).
    """
    events: List[StructureEvent] = []
    last_high: Optional[Swing] = None
    last_low: Optional[Swing] = None
    bias: Literal["up", "down", "range"] = "range"
    swing_by_i = {}
    for s in swings:
        swing_by_i.setdefault(s.i, []).append(s)

    for idx, c in enumerate(candles):
        # registrar swings que ya quedaron confirmados hasta este índice
        for s in swing_by_i.get(idx, []):
            if s.kind == "high":
                last_high = s
            else:
                last_low = s
        # chequear quiebres por cierre
        if last_high and c.c > last_high.price:
            kind = "BOS" if bias in ("up", "range") else "CHoCH"
            events.append(StructureEvent(idx, kind, "bull", last_high.price))
            bias = "up"
            last_high = None  # consumido hasta el próximo swing high
        if last_low and c.c < last_low.price:
            kind = "BOS" if bias in ("down", "range") else "CHoCH"
            events.append(StructureEvent(idx, kind, "bear", last_low.price))
            bias = "down"
            last_low = None
    return events


# ─────────────────────────────────────────────────────────────────────────────
# 4. Fair Value Gaps (FVG)
# ─────────────────────────────────────────────────────────────────────────────
def find_fvgs(candles: List[Candle]) -> List[FVG]:
    """Gap de 3 velas: bull si low[i+1] > high[i-1]; bear si high[i+1] < low[i-1]."""
    out: List[FVG] = []
    for i in range(1, len(candles) - 1):
        a, c = candles[i - 1], candles[i + 1]
        if c.l > a.h:
            out.append(FVG(i, "bull", top=c.l, bottom=a.h))
        elif c.h < a.l:
            out.append(FVG(i, "bear", top=a.l, bottom=c.h))
    # marcar rellenados por acción posterior
    for g in out:
        for j in range(g.i + 2, len(candles)):
            if g.direction == "bull" and candles[j].l <= g.bottom:
                g.filled = True
                break
            if g.direction == "bear" and candles[j].h >= g.top:
                g.filled = True
                break
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 4b. Inverse FVG (IFVG) — un FVG que se invierte (el modelo de Fede)
# ─────────────────────────────────────────────────────────────────────────────
def find_ifvgs(candles: List[Candle], fvgs: List[FVG]) -> List[IFVG]:
    """Un FVG alcista (soporte) que el precio CIERRA por debajo de su piso se
    invierte -> IFVG bajista (resistencia). Idem al revés. La dirección del IFVG
    es la del movimiento que lo invirtió = la dirección en la que se entra."""
    out: List[IFVG] = []
    for g in fvgs:
        for j in range(g.i + 2, len(candles)):
            c = candles[j]
            if g.direction == "bull" and c.c < g.bottom:
                out.append(IFVG(g.i, j, "bear", top=g.top, bottom=g.bottom)); break
            if g.direction == "bear" and c.c > g.top:
                out.append(IFVG(g.i, j, "bull", top=g.top, bottom=g.bottom)); break
    # marcar retest: ¿el precio volvió a la zona después de invertirse?
    for iv in out:
        for j in range(iv.i_flip + 1, len(candles)):
            if iv.bottom <= candles[j].h and candles[j].l <= iv.top:
                iv.used = True
                break
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 5. Order Blocks (última vela contraria antes del impulso que rompe estructura)
# ─────────────────────────────────────────────────────────────────────────────
def find_order_blocks(candles: List[Candle], events: List[StructureEvent]) -> List[OrderBlock]:
    obs: List[OrderBlock] = []
    for ev in events:
        if ev.direction == "bull":
            # última vela bajista antes del índice del BOS
            for j in range(ev.i - 1, max(-1, ev.i - 12), -1):
                if not candles[j].bullish:
                    obs.append(OrderBlock(j, "bull", top=candles[j].h, bottom=candles[j].l))
                    break
        else:
            for j in range(ev.i - 1, max(-1, ev.i - 12), -1):
                if candles[j].bullish:
                    obs.append(OrderBlock(j, "bear", top=candles[j].h, bottom=candles[j].l))
                    break
    return obs


# ─────────────────────────────────────────────────────────────────────────────
# 6. Liquidez + tomas de liquidez (sweeps)
# ─────────────────────────────────────────────────────────────────────────────
def liquidity_levels(swings: List[Swing], tol: float = 0.0005) -> List[LiquidityLevel]:
    levels: List[LiquidityLevel] = []
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    for s in highs:
        levels.append(LiquidityLevel(s.i, s.price, "buy"))
    for s in lows:
        levels.append(LiquidityLevel(s.i, s.price, "sell"))
    # equal highs/lows (dentro de tolerancia relativa)
    def mark_equal(group):
        for a in range(len(group)):
            for b in range(a + 1, len(group)):
                if abs(group[a].price - group[b].price) / max(group[b].price, 1e-9) <= tol:
                    group[a].equal = True
                    group[b].equal = True
    mark_equal([lv for lv in levels if lv.side == "buy"])
    mark_equal([lv for lv in levels if lv.side == "sell"])
    return levels


def find_sweeps(candles: List[Candle], levels: List[LiquidityLevel]) -> List[Sweep]:
    """Sweep: la mecha supera el nivel pero la vela CIERRA del lado contrario."""
    out: List[Sweep] = []
    for lv in levels:
        for j in range(lv.i + 1, len(candles)):
            c = candles[j]
            if lv.side == "buy" and c.h > lv.price and c.c < lv.price:
                out.append(Sweep(j, "buy", lv.price))
                break
            if lv.side == "sell" and c.l < lv.price and c.c > lv.price:
                out.append(Sweep(j, "sell", lv.price))
                break
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 7. Premium / Discount (dealing range + cuartos)
# ─────────────────────────────────────────────────────────────────────────────
def premium_discount(swings: List[Swing]) -> Optional[dict]:
    """Rango operativo = último swing low al último swing high (o viceversa)."""
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    if not highs or not lows:
        return None
    hi = highs[-1]
    lo = lows[-1]
    top, bottom = max(hi.price, lo.price), min(hi.price, lo.price)
    eq = (top + bottom) / 2
    return {
        "top": top, "bottom": bottom, "eq": eq,
        "q25": bottom + (top - bottom) * 0.25,
        "q75": bottom + (top - bottom) * 0.75,
        "newer": "high" if hi.i > lo.i else "low",
    }


def zone_of(price: float, pd: dict) -> Literal["premium", "discount", "equilibrium"]:
    if pd is None:
        return "equilibrium"
    if price > pd["eq"] * 1.0005:
        return "premium"
    if price < pd["eq"] * 0.9995:
        return "discount"
    return "equilibrium"


# ─────────────────────────────────────────────────────────────────────────────
# Resumen de mercado (todo junto)
# ─────────────────────────────────────────────────────────────────────────────
def inducement(candles: List[Candle], events: List[StructureEvent],
               lookback: int = 12) -> Optional[dict]:
    """Inducement: liquidez 'trampa' (un swing menor) barrida poco ANTES del último
    quiebre de estructura. Usa swings finos (k=1). Devuelve el nivel barrido o None."""
    if not events:
        return None
    ev = events[-1]
    minor = find_swings(candles, k=1)
    for s in reversed(minor):
        if ev.i - lookback <= s.i < ev.i:
            # ¿fue barrido entre s.i y ev.i?
            for j in range(s.i + 1, ev.i + 1):
                if s.kind == "high" and candles[j].h > s.price and candles[j].c < s.price:
                    return {"i": s.i, "price": s.price, "side": "buy", "taken": True}
                if s.kind == "low" and candles[j].l < s.price and candles[j].c > s.price:
                    return {"i": s.i, "price": s.price, "side": "sell", "taken": True}
    return None


def analyze(candles: List[Candle], k: int = 2) -> dict:
    swings = find_swings(candles, k=k)
    events = structure_events(candles, swings)
    fvgs = find_fvgs(candles)
    ifvgs = find_ifvgs(candles, fvgs)
    obs = find_order_blocks(candles, events)
    levels = liquidity_levels(swings)
    sweeps = find_sweeps(candles, levels)
    pd = premium_discount(swings)
    ind = inducement(candles, events)
    last = candles[-1]
    return {
        "trend": trend_from_swings(swings),
        "swings": swings,
        "structure": events,
        "fvgs": fvgs,
        "ifvgs": ifvgs,
        "order_blocks": obs,
        "liquidity": levels,
        "sweeps": sweeps,
        "premium_discount": pd,
        "inducement": ind,
        "price_zone": zone_of(last.c, pd),
        "last_price": last.c,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Generador de velas sintéticas (para testear el motor sin datos reales)
# ─────────────────────────────────────────────────────────────────────────────
def synth(n: int = 300, seed: int = 7, start: float = 100.0) -> List[Candle]:
    random.seed(seed)
    candles: List[Candle] = []
    price = start
    drift = 0.05
    for i in range(n):
        if i == n // 2:
            drift = -0.06  # cambio de tendencia a mitad para generar CHoCH
        o = price
        move = random.gauss(drift, 0.6)
        c = o + move
        h = max(o, c) + abs(random.gauss(0, 0.4))
        l = min(o, c) - abs(random.gauss(0, 0.4))
        candles.append(Candle(i, round(o, 3), round(h, 3), round(l, 3), round(c, 3),
                              v=abs(random.gauss(1000, 200))))
        price = c
    return candles


if __name__ == "__main__":
    c = synth()
    a = analyze(c)
    print("=== Esses Engine — demo sobre velas sintéticas ===")
    print(f"Velas: {len(c)}  | precio final: {a['last_price']}")
    print(f"Tendencia: {a['trend']}  | zona del precio: {a['price_zone']}")
    print(f"Swings: {len(a['swings'])}")
    print(f"Eventos de estructura: {len(a['structure'])}  "
          f"(BOS={sum(1 for e in a['structure'] if e.kind=='BOS')}, "
          f"CHoCH={sum(1 for e in a['structure'] if e.kind=='CHoCH')})")
    print(f"FVGs: {len(a['fvgs'])} (sin rellenar: {sum(1 for g in a['fvgs'] if not g.filled)})")
    print(f"Order blocks: {len(a['order_blocks'])}")
    print(f"Niveles de liquidez: {len(a['liquidity'])} "
          f"(equal: {sum(1 for lv in a['liquidity'] if lv.equal)})")
    print(f"Sweeps: {len(a['sweeps'])}")
    if a["premium_discount"]:
        pd = a["premium_discount"]
        print(f"Rango: {pd['bottom']:.2f}–{pd['top']:.2f}  eq={pd['eq']:.2f}")
    print("\nÚltimos 3 eventos de estructura:")
    for e in a["structure"][-3:]:
        print(f"  vela {e.i}: {e.kind} {e.direction} @ {e.level:.2f}")
    print("\nÚltimos 3 FVG sin rellenar:")
    for g in [g for g in a["fvgs"] if not g.filled][-3:]:
        print(f"  vela {g.i}: FVG {g.direction} [{g.bottom:.2f}, {g.top:.2f}]")
