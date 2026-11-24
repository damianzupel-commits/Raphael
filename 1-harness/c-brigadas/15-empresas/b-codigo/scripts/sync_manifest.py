"""Copia el manifiesto del paquete (la fuente de verdad, va adentro del wheel) al de desarrollo (lo encuentra el
cargador al buscar en `brigadas\\`). La puerta falla si quedaron distintos.

Uso: python scripts/sync_manifest.py
"""

from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
src = HERE / "src" / "raphael_empresas" / "manifest.yaml"
dst = HERE / "manifest.yaml"
dst.write_bytes(src.read_bytes())
print(f"copiado: {src.relative_to(HERE)} -> {dst.relative_to(HERE)}")
