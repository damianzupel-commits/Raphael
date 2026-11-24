"""Prueba el paquete desde su src/ sin instalarlo, con raphael-core del proyecto (packages/core)."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
_core = os.environ.get("RAPHAEL_CORE_SRC") or str(HERE.parent / "core" / "src")
if Path(_core).is_dir() and _core not in sys.path:
    sys.path.insert(1, _core)
