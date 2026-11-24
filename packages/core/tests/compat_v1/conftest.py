"""Los tests del harness de Raphael Empresas 0.4, copiados SIN CAMBIOS, corriendo sobre el v2 por el puente."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "compat-shim"))
sys.path.insert(0, str(RAIZ / "src"))
