"""Servidor de Raphael.

    python -m raphael_servidor iniciar  --dir DATOS --perfil perfil.yaml   # primera vez: copia el perfil y pide la clave de la dueña
    python -m raphael_servidor correr   --dir DATOS [--puerto 8080]         # arranca el servidor
    python -m raphael_servidor backup   --dir DATOS                         # copia de la base ahora
    python -m raphael_servidor restaurar --dir DATOS ARCHIVO                # vuelve a una copia (guarda la actual antes)
"""

from __future__ import annotations

import argparse
import getpass
import shutil
from pathlib import Path

from raphael_harness import cargar_perfil

from .config import Config
from .seguridad import Secretos
from .servicios import restaurar_backup


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raphael-servidor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("iniciar")
    p.add_argument("--dir", required=True)
    p.add_argument("--perfil", required=True)
    p = sub.add_parser("correr")
    p.add_argument("--dir")
    p.add_argument("--puerto", type=int, default=8080)
    p.add_argument("--host", default="0.0.0.0")
    p = sub.add_parser("backup")
    p.add_argument("--dir")
    p = sub.add_parser("restaurar")
    p.add_argument("--dir")
    p.add_argument("archivo")
    a = ap.parse_args(argv)
    cfg = Config.desde_entorno(a.dir)

    if a.cmd == "iniciar":
        perfil = cargar_perfil(a.perfil)                # falla acá si el perfil está mal
        cfg.dir.mkdir(parents=True, exist_ok=True)
        if Path(a.perfil).resolve() != cfg.perfil:
            shutil.copy2(a.perfil, cfg.perfil)
        s = Secretos(cfg.secretos)
        if not s.tiene_clave:
            while True:
                c1 = getpass.getpass("Clave para el panel de la dueña (mínimo 8): ")
                if c1 == getpass.getpass("Repetila: "):
                    try:
                        s.poner_clave(c1)
                        break
                    except ValueError as e:
                        print(e)
                else:
                    print("No coinciden.")
        print(f"Listo: {perfil.negocio} · plan {perfil.plan} · instalación {s.instalacion}")
        return 0
    if a.cmd == "correr":
        import uvicorn

        from .app import crear_app

        uvicorn.run(crear_app(cfg), host=a.host, port=a.puerto)
        return 0
    if a.cmd == "backup":
        from .app import Raphael

        print(Raphael(Config.desde_entorno(a.dir, tareas=False)).backup())
        return 0
    if a.cmd == "restaurar":
        restaurar_backup(Path(a.archivo), cfg.base, cfg.clave_backup)
        print("Restaurado. Reiniciá el servidor.")
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
