"""Arma el texto de lienzo (qué hace falta, dónde se saca, dónde se pega, qué se prueba) desde el catálogo."""

from __future__ import annotations

from .catalogo import CUENTAS


def generar() -> str:
    out = ["## Cuentas y APIs (pieza 4)", "",
           "| Cuenta | Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |",
           "| --- | --- | --- | --- | --- |"]
    for c in CUENTAS:
        vars_ = ", ".join(f"`{v.nombre}`" + ("" if v.obligatoria else " (opc.)") for v in c.vars) or "(pendiente)"
        opc = "" if c.requerida else " *(opcional)*"
        out.append(f"| {c.nombre}{opc} | {vars_} | {c.donde_se_saca} | {c.donde_se_pega} | {c.que_se_prueba} |")
    sup = [f"- **{c.nombre}**: {s}" for c in CUENTAS for s in c.supuestos]
    out += ["", "Supuestos sin verificar (no se probaron con cuentas reales):", *sup, ""]
    return "\n".join(out)
