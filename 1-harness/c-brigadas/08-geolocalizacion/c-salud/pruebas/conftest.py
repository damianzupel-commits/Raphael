"""Prueba la brigada desde su src/ sin instalarla, con raphael-core del proyecto.

Ruta por defecto (la del monorepo raphael) o por variable: RAPHAEL_CORE_SRC. Los tests no usan red: todo con las fuentes
simuladas o con un transporte falso.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 08-geolocalizacion/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
core = os.environ.get("RAPHAEL_CORE_SRC") or str(ROOT / "1-harness" / "b-codigo" / "src")
if Path(core).is_dir() and core not in sys.path:
    sys.path.insert(2, core)
os.environ.pop("RAPHAEL_GEO_MODO", None)   # que el entorno de quien corre los tests no cambie el modo
