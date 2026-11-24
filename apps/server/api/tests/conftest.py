"""Prueba la API desde src/ con raphael-core, raphael-orchestrator y raphael-empresas del proyecto."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]   # raphael/
for p in (HERE / "src", ROOT / "brigades/business/src", ROOT / "packages/core/src",
          ROOT / "packages/orchestrator/src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
