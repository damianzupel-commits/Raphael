"""Convierte el `perfil.yaml` de Raphael Empresas 0.4 en la instalación v2 de la clienta.

Uso (desde raphael-empresas, con raphael-core instalado o en el PYTHONPATH):
    python scripts/perfil_a_instalacion.py ruta\\perfil.yaml ..\\instalacion\\clienta.installation.yaml
    python scripts/perfil_a_instalacion.py perfil.yaml salida.yaml --id clienta-ropa --catalogo https://.../productos.json
No toca el perfil ni ninguna base: solo escribe la salida. Lo valida contra los esquemas del harness y de la brigada.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from raphael_empresas.migrate import convert  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("perfil")
    ap.add_argument("salida")
    ap.add_argument("--id", default=None, help="id de la instalación (por defecto, el nombre del negocio)")
    ap.add_argument("--edicion", default="cloud", choices=["cloud", "personal"])
    ap.add_argument("--catalogo", default="", help="URL del feed JSON o CSV de la tienda (opcional)")
    a = ap.parse_args()
    if Path(a.salida).exists():
        print(f"{a.salida} ya existe: no lo piso. Borralo o elegí otro nombre.")
        return 2
    notes = convert(a.perfil, a.salida, inst_id=a.id, edition=a.edicion, store_url=a.catalogo)
    print(f"Listo: {a.salida}")
    for n in notes:
        print(f"  aviso: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
