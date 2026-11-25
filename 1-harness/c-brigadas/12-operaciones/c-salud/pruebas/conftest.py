"""Prueba la brigada desde su src/ sin instalarla, con raphael-core del proyecto.

Rutas por defecto (las del monorepo raphael) o por variable: RAPHAEL_CORE_SRC.
Todo corre con los adaptadores SIMULADOS y sin red: nada toca la PC, el celular ni internet de verdad.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 12-operaciones/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
p = os.environ.get("RAPHAEL_CORE_SRC") or str(ROOT / "1-harness/b-codigo/src")
if Path(p).is_dir() and p not in sys.path:
    sys.path.insert(2, p)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _sin_entorno_de_operaciones(monkeypatch):
    """Ninguna variable OPERACIONES_* del entorno de quien corre los tests se cuela en ellos."""
    for key in [k for k in os.environ if k.startswith("OPERACIONES_")]:
        monkeypatch.delenv(key, raising=False)
