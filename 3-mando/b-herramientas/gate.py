"""Puerta del monorepo: corre todas las suites (core, orchestrator, business, server, cada brigada y cuentas) y ruff, y resume.

Cada suite corre con pytest en su propia carpeta (cada una tiene su conftest y sus rutas). No saltea nada.

Uso (desde la carpeta raphael):
    python 3-mando\\b-herramientas\\gate.py                          # usa .venv\\Scripts\\python.exe si existe
    python 3-mando\\b-herramientas\\gate.py --python C:\\ruta\\python.exe
    python 3-mando\\b-herramientas\\gate.py --solo core business     # solo algunas suites (ruff corre igual)
Sale con 0 si todo pasa y con 2 si algo falla.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # raphael/
BRIGADAS = ROOT / "1-harness" / "c-brigadas"
#: brigadas con código propio: carpeta -> nombre de la suite. Cada una trae su `c-salud/pruebas` (pytest arranca desde ahí).
BRIGADAS_SUITES = {
    "05-seguridad": "seguridad",
    "06-antimalware": "antimalware",
    "07-investigacion": "investigacion",
    "08-geolocalizacion": "geolocalizacion",
    "09-memoria": "memoria",
    "10-ingesta": "ingesta",
    "11-trading": "trading",
    "12-operaciones": "operaciones",
    "13-autorreparacion": "autorreparacion",
    "14-contenido": "contenido",
    "16-legales": "legales",
}
SUITES = {
    "core": ROOT / "1-harness" / "b-codigo",
    "orchestrator": BRIGADAS / "00-orquestador" / "c-salud" / "pruebas",
    "business": BRIGADAS / "15-empresas" / "c-salud" / "pruebas",
    "server": ROOT / "2-entrega" / "b-codigo" / "servidor" / "api",
    **{name: BRIGADAS / carpeta / "c-salud" / "pruebas" for carpeta, name in BRIGADAS_SUITES.items()},
    "cuentas": ROOT / "2-entrega" / "c-despliegue" / "cuentas-y-apis" / "tests",
}
#: carpeta que se suma al PYTHONPATH de una suite (la de cuentas no es un paquete instalado)
SUITE_PYTHONPATH = {"cuentas": ROOT / "2-entrega" / "c-despliegue" / "cuentas-y-apis" / "codigo" / "src"}
RUFF_PATHS = [
    "1-harness",
    "2-entrega/b-codigo/servidor",
    "2-entrega/c-despliegue/cuentas-y-apis",
]


def default_python() -> str:
    for cand in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if cand.is_file():
            return str(cand)
    return sys.executable


def run(cmd: list[str], cwd: Path, pythonpath: Path | None = None) -> tuple[int, str]:
    env = None
    if pythonpath is not None:
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(pythonpath), os.environ.get("PYTHONPATH", "")]))}
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def counts(out: str) -> dict[str, int]:
    last = next((ln for ln in reversed(out.splitlines()) if re.search(r"\d+ (passed|failed|error)", ln)), "")
    return {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|errors?)", last)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", default=None, help="intérprete con las piezas instaladas, pytest y ruff")
    ap.add_argument("--solo", nargs="+", choices=sorted(SUITES), help="correr solo estas suites")
    args = ap.parse_args()
    py = args.python or default_python()
    ok = True
    total = {"passed": 0, "failed": 0}
    print(f"Puerta del monorepo  (python: {py})\n")
    for name, folder in SUITES.items():
        if args.solo and name not in args.solo:
            continue
        t0 = time.monotonic()
        code, out = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], folder, SUITE_PYTHONPATH.get(name))
        c = counts(out)
        bad = c.get("failed", 0) + c.get("error", 0) + c.get("errors", 0)
        total["passed"] += c.get("passed", 0)
        total["failed"] += bad
        state = "OK   " if code == 0 else "FALLA"
        print(f"  {state} {name:<13} {c.get('passed', 0):>4} passed  {bad:>3} failed   ({time.monotonic() - t0:.1f}s)")
        if code != 0:
            ok = False
            fails = [ln for ln in out.splitlines() if ln.startswith(("FAILED", "ERROR"))]
            print("\n".join("        " + ln for ln in (fails or out.splitlines()[-20:])))
    code, out = run([py, "-m", "ruff", "check", "--no-cache", *RUFF_PATHS], ROOT)
    print(f"  {'OK   ' if code == 0 else 'FALLA'} ruff          {out.splitlines()[-1] if out else ''}")
    if code != 0:
        ok = False
        print("\n".join("        " + ln for ln in out.splitlines()[-20:]))
    print(f"\nTotal: {total['passed']} passed, {total['failed']} failed")
    print("Puerta: " + ("EN VERDE" if ok else "EN ROJO"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
