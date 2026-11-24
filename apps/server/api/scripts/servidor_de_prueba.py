"""Servidor de PRUEBA para la app: instalación de ejemplo en memoria, clave fija, unos mensajes de clientes cargados.
Lo usa el test de contrato de la app Android (`ApiContractTest`). NO es para producción.

    python scripts/servidor_de_prueba.py --port 8799
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]   # raphael/
for p in (HERE / "src", ROOT / "brigades/business/src", ROOT / "packages/core/src",
          ROOT / "packages/orchestrator/src"):
    sys.path.insert(0, str(p))

import uvicorn  # noqa: E402
from raphael_core import Loader, Runtime  # noqa: E402
from raphael_core.installation import installation_from  # noqa: E402
from raphael_core.testing import Clock  # noqa: E402
from raphael_empresas.sample import MINIMAL  # noqa: E402

from raphael_empresas_api.app import create_app  # noqa: E402

KEY = "clave-de-prueba"


def build() -> Runtime:
    cfg = {**MINIMAL, "orders": {**MINIMAL["orders"], "required_steps": ["prenda", "nombre"]}}
    inst = installation_from({"id": "prueba", "edition": "cloud", "identity": {"user": "Ana"},
                              "brigades": {"empresas": {"config": cfg}},
                              "orchestrator": {"entry": "raphael_orchestrator.orchestrator:RaphaelOrchestrator",
                                               "config": {"mode": "secretary", "routing": {
                                                   "fallback_cook": "empresas/atencion", "classifier": False}}}})
    rt = Runtime(inst, clock=Clock(datetime(2026, 11, 18, 9, 0)))
    rt.run(Loader(rt, [HERE.parent / "raphael-empresas"], installed=False).apply())
    for who, text, name in (("549341", "quiero un vestido a medida", ""), ("549341", "Lu", ""),
                            ("9", "me llegó roto, quiero hablar con alguien", "Marta")):
        rt.run(rt.receive("whatsapp", who, text, name))
    return rt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    a = ap.parse_args()
    app = create_app(build(), tick=False)
    app.state.auth.set_key(KEY)
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
