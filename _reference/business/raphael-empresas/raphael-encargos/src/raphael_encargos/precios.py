"""Precio sugerido: base de la prenda más específica + recargos por palabras. La dueña siempre lo aprueba."""

from __future__ import annotations

from raphael_harness.texto import normalizar, plata


def sugerir(conf, *textos: str) -> dict | None:
    """`conf` = perfil.encargos. Devuelve {'precio', 'detalle', 'dias'} o None si no hay base para esa prenda."""
    t = " " + " ".join(normalizar(x or "") for x in textos) + " "
    precios = [(" ".join(normalizar(p.prenda).split()), p) for p in conf.precios]
    candidatos = [(k, p) for k, p in precios if all(f" {w}" in t or f" {w}s" in t for w in k.split())]
    if not candidatos:
        return None
    clave, base = max(candidatos, key=lambda kp: len(kp[0]))       # "vestido de novia" le gana a "vestido"
    total, partes = base.base, [f"{clave} {plata(base.base)}"]
    for r in conf.recargos:
        palabra = " ".join(normalizar(r.palabra).split())
        if f" {palabra}" in t:
            if r.tipo == "pct":
                total += base.base * r.valor / 100
                partes.append(f"+{r.valor:g}% {palabra}")
            else:
                total += r.valor
                partes.append(f"+{plata(r.valor)} {palabra}")
    return {"precio": round(total, -2), "detalle": " ".join(partes), "dias": base.dias}
