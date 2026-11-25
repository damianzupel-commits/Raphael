"""Prueba la brigada desde su src/ sin instalarla, con raphael-core del proyecto.

Ruta por defecto (la del monorepo raphael) o por variable: RAPHAEL_CORE_SRC."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 05-seguridad/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
p = os.environ.get("RAPHAEL_CORE_SRC") or str(ROOT / "1-harness/b-codigo/src")
if Path(p).is_dir() and p not in sys.path:
    sys.path.insert(2, p)
