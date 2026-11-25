"""CLI: `python -m raphael_cuentas <chequear|probar|plantilla|lienzo> [opciones]`.

Códigos de salida: 0 bien, 2 algo mal (problema de formato, prueba fallida o, con --estricto, falta algo requerido).
"""

from __future__ import annotations

import argparse
import sys

from . import catalogo, entorno, lienzo, plantilla
from .adaptadores import AdaptadorReal, AdaptadorSimulado


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raphael_cuentas", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("chequear", "probar"):
        p = sub.add_parser(nombre)
        p.add_argument("--env", action="append", default=[], help="archivo de claves (se puede repetir)")
        p.add_argument("--edicion", choices=["personal", "empresas", "ambas"], default="ambas")
        p.add_argument("--estricto", action="store_true")
        if nombre == "probar":
            p.add_argument("cuentas", nargs="*", help="ids a probar (por defecto, todas las cargadas)")
            p.add_argument("--simulado", action="store_true", help="no sale a la red")
    sub.add_parser("plantilla")
    sub.add_parser("lienzo")
    args = ap.parse_args(argv)

    if args.cmd == "plantilla":
        print(plantilla.generar())
        return 0
    if args.cmd == "lienzo":
        print(lienzo.generar())
        return 0

    env = entorno.cargar(args.env)
    estados = entorno.chequear(env, args.edicion)
    if args.cmd == "chequear":
        print(entorno.render(estados, env))
        return entorno.codigo_salida(estados, estricto=args.estricto)

    ver = AdaptadorSimulado() if args.simulado else AdaptadorReal()
    ids = args.cuentas or [e.cuenta.id for e in estados if e.estado in {"lista", "parcial"} or e.cuenta.id == "local_llm"]
    mal = False
    for i in ids:
        r = ver.probar(catalogo.cuenta(i), env)
        print(f"{r.estado.upper():<8} {i:<16} {r.detalle}")
        mal = mal or r.estado == "falla"
    return 2 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
