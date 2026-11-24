"""Prueba este repo solo: usa su src/ y, si raphael-harness no está instalado, el repo vecino."""

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI / "src"))
try:
    import raphael_harness  # noqa: F401
except ImportError:  # desarrollo: repos lado a lado en la misma carpeta
    sys.path.insert(0, str(AQUI.parent / "raphael-harness" / "src"))
