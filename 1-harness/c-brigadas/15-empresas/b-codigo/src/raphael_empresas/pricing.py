"""Precio sugerido: base de la prenda más específica + recargos por palabras. La dueña siempre lo aprueba.

Portado de `raphael_encargos.precios` (Empresas 0.4).
"""

from __future__ import annotations

from raphael_core.text_es import money, normalize

from .config import Orders


def suggest(conf: Orders, *texts: str) -> dict | None:
    """{'price', 'detail', 'days'} o None si no hay base para esa prenda en la tabla de precios."""
    t = " " + " ".join(normalize(x or "") for x in texts) + " "
    prices = [(" ".join(normalize(p.item).split()), p) for p in conf.prices]
    candidates = [(k, p) for k, p in prices if all(f" {w}" in t or f" {w}s" in t for w in k.split())]
    if not candidates:
        return None
    key, base = max(candidates, key=lambda kp: len(kp[0]))       # "vestido de novia" le gana a "vestido"
    total, parts = base.base, [f"{key} {money(base.base)}"]
    for s in conf.surcharges:
        word = " ".join(normalize(s.word).split())
        if f" {word}" in t:
            if s.kind == "pct":
                total += base.base * s.value / 100
                parts.append(f"+{s.value:g}% {word}")
            else:
                total += s.value
                parts.append(f"+{money(s.value)} {word}")
    return {"price": round(total, -2), "detail": " ".join(parts), "days": base.days}
