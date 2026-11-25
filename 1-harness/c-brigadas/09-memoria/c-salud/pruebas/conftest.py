"""Prueba la brigada desde su src/ sin instalarla, con raphael-core del proyecto.

Rutas por defecto (las del monorepo raphael) o por variable: RAPHAEL_CORE_SRC. Nada toca el vault real: cada test usa una
carpeta temporal, y las variables de entorno de Memoria se limpian para que ningún valor del entorno cambie un resultado.
"""

import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 09-memoria/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
p = os.environ.get("RAPHAEL_CORE_SRC") or str(ROOT / "1-harness/b-codigo/src")
if Path(p).is_dir() and p not in sys.path:
    sys.path.insert(2, p)


@pytest.fixture(autouse=True)
def _env_limpio(monkeypatch):
    for k in list(os.environ):
        if k.startswith("MEMORIA_") or k == "RAPHAEL_DATA_DIR":
            monkeypatch.delenv(k, raising=False)
