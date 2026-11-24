"""python -m raphael_central [--puerto 8070]   (variables: CENTRAL_BASE, CENTRAL_ADMIN_TOKEN)

    python -m raphael_central licencia --cliente "Taller X" --plan pro --vence 2027-01-01   # crea una clave sin abrir el panel
"""

import argparse
import os

from .app import Base, crear_app

ap = argparse.ArgumentParser(prog="raphael-central")
sub = ap.add_subparsers(dest="cmd")
p = sub.add_parser("licencia")
p.add_argument("--cliente", required=True)
p.add_argument("--plan", default="basico")
p.add_argument("--vence")
ap.add_argument("--puerto", type=int, default=8070)
ap.add_argument("--host", default="0.0.0.0")
a = ap.parse_args()
if a.cmd == "licencia":
    lic = Base(os.environ.get("CENTRAL_BASE", "central.sqlite")).crear(a.cliente, a.plan, a.vence)
    print(f"{lic['clave']}  ·  {lic['cliente']} · plan {lic['plan']} · vence {lic['vence'] or 'sin vencimiento'}")
else:
    import uvicorn

    uvicorn.run(crear_app(), host=a.host, port=a.puerto)
