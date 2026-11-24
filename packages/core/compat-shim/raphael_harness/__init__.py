"""Puente: el paquete `raphael_harness` de Raphael Empresas, servido por raphael-core (harness v2).

Poné esta carpeta (`compat-shim/`) en el path en lugar del raphael-harness viejo y las brigadas de Empresas
corren sobre el v2 sin cambiar una línea. Implementación en `raphael_core.compat.v1`.
"""

import sys
from pathlib import Path

try:
    import raphael_core  # noqa: F401
except ImportError:  # desarrollo: raphael-core sin instalar, al lado
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from raphael_core.compat.v1 import *  # noqa: E402, F403
from raphael_core.compat.v1 import __all__, __version__  # noqa: E402, F401
