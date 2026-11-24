"""Prueba el paquete desde su src/ sin instalarlo."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
