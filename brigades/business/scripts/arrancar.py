"""Arranca la instalación de la clienta (harness v2 + orquestador `secretary` + brigada Empresas) y la prueba.

Uso:
    python scripts/arrancar.py --instalacion ..\\..\\infra\\client-install\\clienta.installation.yaml --datos datos --estado
    python scripts/arrancar.py --instalacion ... --datos ... --probar     # recorrido de humo sin red, en una base aparte
En el VPS lo llama el servidor (pieza 03) con `raphael_empresas.boot.start`; este script es para revisar a mano.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from raphael_empresas.boot import start  # noqa: E402

SMOKE = [("cliente", "Hola! qué horario tienen?"), ("cliente", "quiero un vestido largo a medida para un casamiento"),
         ("cliente", "¿hacen envíos?"), ("duena", "buen día, ¿qué tareas tenemos hoy?")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instalacion", required=True)
    ap.add_argument("--datos", required=True, help="carpeta de datos (ahí queda raphael.sqlite)")
    ap.add_argument("--dev", action="append", default=[], help="carpeta con brigadas o el orquestador sin instalar")
    ap.add_argument("--estado", action="store_true", help="mostrar el estado (sin datos de clientes)")
    ap.add_argument("--probar", action="store_true", help="recorrido de humo, sin red, en una base temporal")
    a = ap.parse_args()
    data = tempfile.mkdtemp(prefix="raphael-humo-") if a.probar else a.datos
    rt, report = start(a.instalacion, data, dev_dirs=a.dev, models=not a.probar)
    print(f"Montado: {', '.join(report['mounted']) or 'nada'} · orquestador: "
          f"{rt.orchestrator.name + ' ' + rt.orchestrator.version if rt.orchestrator else 'ninguno'}")
    for k, v in report["errors"].items():
        print(f"  ERROR {k}: {v}")
    for w in report["warnings"] + rt.warnings:
        print(f"  aviso: {w}")
    if a.probar:
        for who, text in SMOKE:
            if who == "cliente":
                out = rt.run(rt.receive("prueba", "humo", text, "Prueba"))
            else:
                out = [rt.run(rt.talk_to_owner(text, session="humo")).text]
            print(f"\n[{who}] {text}\n" + "\n".join(f"  > {o}" for o in out))
    if a.estado:
        st = rt.status()
        print(json.dumps({k: st[k] for k in ("core", "contract", "edition", "plan", "orchestrator", "brigades", "pending",
                                             "warnings")}, ensure_ascii=False, indent=2))
    ok = not report["errors"] and "empresas" in rt.brigades and rt.orchestrator is not None
    print("\n" + ("OK: lista para recibir mensajes." if ok else "FALLA: revisá los errores de arriba."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
