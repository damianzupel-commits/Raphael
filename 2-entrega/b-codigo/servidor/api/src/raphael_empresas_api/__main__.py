"""Levantar la API, chequear qué claves faltan o poner la clave de la dueña.

    python -m raphael_empresas_api chequear --instalacion clienta.installation.yaml --datos datos [--real]
    python -m raphael_empresas_api clave    --instalacion clienta.installation.yaml --datos datos
    python -m raphael_empresas_api servir   --instalacion clienta.installation.yaml --datos datos [--host 127.0.0.1 --port 8787]

Las claves se leen de `<datos>/raphael.env` (y `meta.env`, `tienda.env`); ver `2-entrega/c-despliegue/QUE-CARGAR.md`.
`servir` imprime el chequeo al arrancar. En el VPS escucha en 127.0.0.1 y Caddy pone el HTTPS adelante; en la PC de
Damián lo expone el túnel. Sin clave puesta, la app no puede entrar.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from raphael_empresas.boot import start

from .app import create_app
from .entorno import check, exit_code, load_env, render
from .meta import MetaChannel, settings_from_env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raphael-empresas-api", description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["servir", "clave", "chequear"])
    ap.add_argument("--instalacion", required=True)
    ap.add_argument("--datos", required=True)
    ap.add_argument("--dev", action="append", default=[], help="carpeta con brigadas u orquestador sin instalar")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--env", action="append", default=[], help="archivo de claves extra (además de los de la carpeta de datos)")
    ap.add_argument("--real", action="store_true", help="chequear: exigir también IA, Meta real y perfil de la clienta")
    a = ap.parse_args(argv)
    env_files = load_env(a.datos, a.env)
    meta = MetaChannel.build(settings_from_env(os.environ))
    rt, report = start(a.instalacion, a.datos, dev_dirs=a.dev, connectors=meta.connectors())
    meta.bind(rt)
    for k, v in report["errors"].items():
        print(f"ERROR {k}: {v}", file=sys.stderr)
    print(f"Canal de Meta en modo {meta.settings.mode}: {', '.join(sorted(rt.connectors)) or 'sin canales'}")
    app = create_app(rt, meta=meta)
    items = [] if a.accion == "clave" else check(
        env=os.environ, installation=rt.installation, models=rt.models, meta=meta.settings,
        app_key_set=app.state.auth.has_key(), env_files=env_files, public_url=os.environ.get("RAPHAEL_PUBLIC_URL", ""))
    if items:
        print(render(items))
    if a.accion == "chequear":
        return exit_code(items, real=a.real)
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
