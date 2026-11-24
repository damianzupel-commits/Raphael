"""Línea de comandos de Raphael.

    python -m raphael_harness piezas   [--dev CARPETA]
    python -m raphael_harness validar  PERFIL.yaml
    python -m raphael_harness chat     --perfil PERFIL.yaml [--datos raphael.sqlite] [--dev CARPETA]
    python -m raphael_harness estado   --perfil PERFIL.yaml [--datos raphael.sqlite] [--dev CARPETA]

En `chat` cada línea es un mensaje del cliente. Comandos de la dueña:
    /pendientes                 lista lo que espera tu decisión
    /aprobar N [json]           aprueba (con cambios opcionales, ej. {"precio": 180000})
    /rechazar N [motivo]        rechaza
    /resolver N [respuesta]     cierra un pendiente humano (la respuesta le llega al cliente)
    /cmd BRIGADA COMANDO [json] comando de una brigada, ej. /cmd encargos estado {"num":1,"estado":"listo"}
    /como CANAL QUIEN           cambia de cliente simulado
    /tick                       corre las tareas programadas (recordatorios)
    /estado                     versiones, uso y avisos
    /salir
"""

from __future__ import annotations

import argparse
import json
import sys

from .almacen import Almacen
from .cargador import descubrir
from .contrato import ErrorDeAccion
from .harness import Harness
from .perfil import cargar_perfil


def _harness(a) -> Harness:
    perfil = cargar_perfil(a.perfil)
    return Harness(perfil, almacen=Almacen(a.datos), rutas_dev=a.dev)


def _json(texto: str) -> dict:
    return json.loads(texto) if texto.strip() else {}


def _chat(h: Harness) -> None:
    canal, quien = "prueba", "cliente-1"
    for aviso in h.avisos:
        print(f"! {aviso}")
    print(f"Raphael para {h.perfil.negocio} · brigadas: {', '.join(h.brigadas) or 'ninguna'} · /salir para terminar")
    while True:
        try:
            linea = input(f"{quien}> ") if sys.stdin.isatty() else sys.stdin.readline()
        except EOFError:
            break
        if not sys.stdin.isatty() and linea == "":
            break
        linea = linea.strip()
        if not linea:
            continue
        try:
            if linea.startswith("/"):
                cmd, _, resto = linea[1:].partition(" ")
                if cmd == "salir":
                    break
                if cmd == "pendientes":
                    for p in h.pendientes():
                        print(f"  #{p['id']} [{p['nivel']}] {p['pieza']}: {p['accion']['resumen']}")
                elif cmd == "aprobar":
                    n, _, j = resto.partition(" ")
                    print(" ", h.aprobar(int(n), _json(j)))
                elif cmd == "rechazar":
                    n, _, motivo = resto.partition(" ")
                    print(" ", h.rechazar(int(n), motivo))
                elif cmd == "resolver":
                    n, _, resp = resto.partition(" ")
                    print(" ", h.resolver(int(n), resp or None))
                elif cmd == "cmd":
                    brig, _, r2 = resto.partition(" ")
                    nombre, _, j = r2.partition(" ")
                    print(json.dumps(h.comando(brig, nombre, _json(j)), ensure_ascii=False, indent=2))
                elif cmd == "como":
                    canal, _, quien = resto.partition(" ")
                elif cmd == "tick":
                    h.tick()
                elif cmd == "estado":
                    print(json.dumps(h.estado(), ensure_ascii=False, indent=2))
                else:
                    print("  comando desconocido")
                continue
            for t in h.recibir(canal, quien, linea, adjunto=linea.lower().startswith("[foto")):
                print(f"raphael> {t}")
        except (ErrorDeAccion, ValueError) as e:
            print(f"  ✗ {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raphael", description="Raphael: harness de brigadas para pymes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("piezas")
    p.add_argument("--dev")
    p = sub.add_parser("validar")
    p.add_argument("perfil")
    for nombre in ("chat", "estado"):
        p = sub.add_parser(nombre)
        p.add_argument("--perfil", required=True)
        p.add_argument("--datos", default="raphael.sqlite")
        p.add_argument("--dev")
    a = ap.parse_args(argv)

    if a.cmd == "piezas":
        orq, brig, avisos = descubrir(a.dev)
        print("orquestador:", f"{orq.nombre} {orq.version}" if orq else "(ninguno: se usa orden simple)")
        for n, cls in brig.items():
            print(f"brigada: {n} {cls.version} — {cls.descripcion}")
        for x in avisos:
            print("!", x)
        return 0
    if a.cmd == "validar":
        perfil = cargar_perfil(a.perfil)
        print(f"Perfil válido: {perfil.negocio} · plan {perfil.plan} · brigadas {perfil.brigadas}")
        return 0
    h = _harness(a)
    if a.cmd == "estado":
        print(json.dumps(h.estado(), ensure_ascii=False, indent=2))
        return 0
    _chat(h)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
