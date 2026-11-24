"""Prueba el paquete desde su src/ sin instalarlo, con raphael-core del proyecto (1-harness/b-codigo)."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 00-orquestador/b-codigo
sys.path.insert(0, str(HERE / "src"))
_core = os.environ.get("RAPHAEL_CORE_SRC") or str(HERE.parents[3] / "b-codigo" / "src")   # 1-harness/b-codigo/src
if Path(_core).is_dir() and _core not in sys.path:
    sys.path.insert(1, _core)
