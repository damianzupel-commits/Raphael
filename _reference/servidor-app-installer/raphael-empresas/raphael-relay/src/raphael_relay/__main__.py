"""python -m raphael_relay [--puerto 8090]  (variables: RELAY_INSTALACIONES, RELAY_BASE, META_APP_SECRET, META_VERIFY_TOKEN)"""

import argparse

import uvicorn

from .app import crear_app

ap = argparse.ArgumentParser(prog="raphael-relay")
ap.add_argument("--puerto", type=int, default=8090)
ap.add_argument("--host", default="0.0.0.0")
a = ap.parse_args()
uvicorn.run(crear_app(), host=a.host, port=a.puerto)
