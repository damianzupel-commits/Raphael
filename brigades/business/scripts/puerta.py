"""Puerta automática de la brigada Empresas: si algo da mal, la tanda no cierra.

Corre: pytest (con cada intérprete que encuentre: 3.12 y 3.13 si están), ruff, y resume. Los tests ya incluyen la
suite de contrato del harness en las dos ediciones, el chequeo de imports, el de autonomía (ninguna acción con efecto
sin su nivel, nada no automático sin OK, comandos de escritura fuera del alcance del orquestador, lo irreversible no
baja solo) y los 74 tests de Empresas 0.4 portados.

Uso (desde la carpeta raphael-empresas):
    python scripts/puerta.py                 # usa los python3.12 / python3.13 que haya, o el actual
    python scripts/puerta.py --python C:\\ruta\\python.exe
Sale con código 1 si algo falla.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", action="append", help="intérprete a usar (se puede repetir)")
    ap.add_argument("--min", type=int, default=0, help="mínimo de tests que tienen que pasar (la puerta final usa 74+)")
    args = ap.parse_args()
    pythons = args.python or [p for p in (shutil.which("python3.12"), shutil.which("python3.13")) if p] or [sys.executable]
    ok = True
    for py in pythons:
        code, out = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
        summary = re.findall(r"^=*\s*(\d+ passed.*?)\s*=*$|^(\d+ failed.*?)$", out, re.M)
        last = next((a or b for a, b in reversed(summary)), out.splitlines()[-1] if out else "")
        ver = run([py, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"])[1]
        print(f"  {'OK   ' if code == 0 else 'FALLA'} pytest (Python {ver}): {last}")
        if code != 0:
            ok = False
            print("\n".join("        " + ln for ln in out.splitlines()[-30:]))
        m = re.search(r"(\d+) passed", last)
        if args.min and (not m or int(m.group(1)) < args.min):
            print(f"  FALLA pasaron menos de {args.min} tests")
            ok = False
    ruff = shutil.which("ruff")
    if ruff:
        code, out = run([ruff, "check", "src", "tests", "scripts"])
        print(f"  {'OK   ' if code == 0 else 'FALLA'} ruff: {out.splitlines()[-1] if out else ''}")
        ok = ok and code == 0
    else:
        print("  (ruff no está instalado: se saltea)")
    print("\nPuerta: " + ("EN VERDE" if ok else "EN ROJO"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
