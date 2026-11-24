"""Prueba la API desde src/ con raphael-core, raphael-orchestrator y raphael-empresas del proyecto."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]   # raphael/
for p in (HERE / "src", ROOT / "1-harness/c-brigadas/15-empresas/b-codigo/src", ROOT / "1-harness/b-codigo/src",
          ROOT / "1-harness/c-brigadas/00-orquestador/b-codigo/src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
