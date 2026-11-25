"""Prueba la brigada desde su src/ sin instalarla, con raphael-core del proyecto.

Rutas por defecto (las del monorepo raphael) o por variable: RAPHAEL_CORE_SRC.
"""

import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[2] / "b-codigo"   # 14-contenido/b-codigo
ROOT = HERE.parents[3]   # .../raphael
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
_core = os.environ.get("RAPHAEL_CORE_SRC") or str(ROOT / "1-harness/b-codigo/src")
if Path(_core).is_dir() and _core not in sys.path:
    sys.path.insert(2, _core)


@pytest.fixture(autouse=True)
def _sin_estado_global():
    """El módulo de video guarda carpeta, ffmpeg y Whisper inyectados: cada test arranca limpio."""
    from raphael_contenido.video import edicion
    edicion.configure()
    yield
    edicion.configure()
