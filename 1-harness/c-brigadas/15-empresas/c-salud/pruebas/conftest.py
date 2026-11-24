"""Prueba la brigada desde su src/ sin instalarla, con raphael-core y raphael-orchestrator del proyecto.

Rutas por defecto (las del monorepo raphael) o por variable: RAPHAEL_CORE_SRC, RAPHAEL_ORCH_SRC.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 15-empresas/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
for env, rel in (("RAPHAEL_CORE_SRC", "1-harness/b-codigo/src"),
                 ("RAPHAEL_ORCH_SRC", "1-harness/c-brigadas/00-orquestador/b-codigo/src")):
    p = os.environ.get(env) or str(ROOT / rel)
    if Path(p).is_dir() and p not in sys.path:
        sys.path.insert(2, p)
