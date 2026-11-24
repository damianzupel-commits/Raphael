"""Prueba la brigada desde su src/ sin instalarla, con raphael-core y raphael-orchestrator del proyecto.

Rutas por defecto (las del monorepo raphael) o por variable: RAPHAEL_CORE_SRC, RAPHAEL_ORCH_SRC.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "tests"))
for env, rel in (("RAPHAEL_CORE_SRC", "packages/core/src"),
                 ("RAPHAEL_ORCH_SRC", "packages/orchestrator/src")):
    p = os.environ.get(env) or str(ROOT / rel)
    if Path(p).is_dir() and p not in sys.path:
        sys.path.insert(2, p)
