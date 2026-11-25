"""Levantar Raphael personal, chequear qué falta o poner la clave de la app.

    python -m raphael_personal_api servir   --instalacion personal.installation.yaml --datos .data/personal [--port 8788]
    python -m raphael_personal_api chequear --instalacion ... --datos ...
    python -m raphael_personal_api clave    --instalacion ... --datos ...

Las claves se leen de `<datos>/raphael.env` (el mismo archivo que usa la pantalla de Configuración). En la PC escucha
solo en 127.0.0.1; para el celular se publica con Tailscale (`tailscale serve`, red privada, sin abrir puertos).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from raphael_empresas_api import permisos
from raphael_empresas_api.__main__ import first_key
from raphael_empresas_api.entorno import load_env, render

from . import boot, campos, cerebro
from .app import create_app


def load_speech(environ):
    """La voz hablada del orquestador (`speech_from`), si está instalado; si no, None (los endpoints dicen que no hay voz)."""
    try:
        from raphael_orchestrator.speech import speech_from
    except ImportError:
        return None
    return speech_from(environ.get("RAPHAEL_VOZ_MODO") or "auto", environ)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raphael-personal-api", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["servir", "clave", "chequear"])
    ap.add_argument("--instalacion", required=True)
    ap.add_argument("--datos", required=True)
    ap.add_argument("--dev", action="append", default=None, help="carpeta con brigadas sin instalar (por defecto, las del repo)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8788)
    a = ap.parse_args(argv)
    datos = Path(a.datos)
    datos.mkdir(parents=True, exist_ok=True)
    env_file = datos / "raphael.env"
    if not env_file.exists():
        env_file.write_text("# Claves de Raphael personal (no subir a git). Se editan desde la pantalla de Configuración.\n",
                            encoding="utf-8")
        permisos.restringir(env_file)
    load_env(datos)
    rt, report = boot.start(a.instalacion, datos, dev_dirs=a.dev, environ=os.environ)
    for k, v in report["errors"].items():
        print(f"ERROR {k}: {v}", file=sys.stderr)
    app = create_app(rt, report=report, env_file=env_file, local_open=os.environ.get("RAPHAEL_LOCAL_SIN_CLAVE") == "1",
                     speech=load_speech(os.environ))
    if a.accion == "servir" and not app.state.auth.has_key():
        print(first_key(app, datos).replace("{port}", str(a.port)))
    probe = cerebro.probe_local(app.state.watch.cfg)
    items = [] if a.accion == "clave" else campos.check(
        os.environ, app_key_set=app.state.auth.has_key(), probe=probe, pending=report["pending"], errors=report["errors"],
        mounted=sorted(rt.brigades), orchestrator_ok=rt.orchestrator is not None)
    if items:
        print(render(items))
    if a.accion == "chequear":
        return 2 if any(i.blocking for i in items) else 0
    if a.accion == "clave":
        k1 = getpass.getpass("Clave nueva para la app (mínimo 8): ")
        if k1 != getpass.getpass("Repetila: "):
            print("No coinciden.")
            return 1
        try:
            app.state.auth.set_key(k1)
        except ValueError as exc:
            print(exc)
            return 1
        print("Clave guardada. Las sesiones anteriores se cerraron.")
        return 0
    import uvicorn

    uvicorn.run(app, host=a.host, port=a.port, proxy_headers=True, forwarded_allow_ips="127.0.0.1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
