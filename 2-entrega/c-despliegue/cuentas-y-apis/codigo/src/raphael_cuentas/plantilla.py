"""Genera `.env.plantilla` desde el catálogo (así la lista de claves y la plantilla nunca se separan)."""

from __future__ import annotations

from .catalogo import CUENTAS

ENCABEZADO = """\
# Claves y datos de cuentas de Raphael (pieza 4 · Cuentas y APIs). GENERADO desde catalogo.py: no editar a mano.
# Copiá como `raphael.env` en la carpeta de datos (PC de Damián: .data\\empresas\\) y completá lo que tengas.
# NUNCA subir a GitHub ni pegar en un chat. Lo que quede vacío no rompe nada: Raphael cae a reglas o a modo mock.
# Ver qué falta: python -m raphael_cuentas chequear      Probar en vivo (solo lectura): python -m raphael_cuentas probar
"""


def generar() -> str:
    out = [ENCABEZADO]
    for c in CUENTAS:
        if not c.vars:
            continue
        out.append(f"# ---- {c.nombre} [{c.edicion}]{'' if c.requerida else ' (opcional)'} " + "-" * 8)
        out.append(f"# Dónde se saca: {c.donde_se_saca}")
        for v in c.vars:
            if v.ayuda:
                out.append(f"# {v.nombre}: {v.ayuda}")
            out.append(f"{v.nombre}={v.defecto}")
        out.append("")
    return "\n".join(out)
