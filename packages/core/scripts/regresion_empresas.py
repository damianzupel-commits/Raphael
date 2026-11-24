"""Puerta de H3: corre TODA la suite de Raphael Empresas sobre el harness v2, sin tocar su código.

Copia a una carpeta temporal (los originales no se tocan):
    - _reference/business/raphael-empresas/raphael-*      (las 6 brigadas y sus tests)
    - _reference/core/raphael-empresas/raphael-harness/tests      (los tests del harness viejo)
    - _reference/core/raphael-empresas/raphael-harness/ejemplos
y en lugar del raphael-harness viejo pone el puente `compat-shim/raphael_harness` (que usa raphael-core).
Después corre pytest en cada repo y resume.

Uso (desde la carpeta raphael-core):
    python scripts/regresion_empresas.py                    # busca la carpeta del proyecto hacia arriba
    python scripts/regresion_empresas.py --proyecto "D:\\Raphael Ultimate\\raphael"
Sale con código 1 si algo falla.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
EMPRESAS = Path("_reference/business/raphael-empresas")
HARNESS_VIEJO = Path("_reference/core/raphael-empresas/raphael-harness")


def proyecto_por_defecto() -> Path | None:
    for p in [CORE, *CORE.parents]:
        if (p / "_reference").is_dir() and (p / "packages").is_dir():
            return p
    return None


def contar(salida: str) -> dict[str, int]:
    ultima = salida.strip().splitlines()[-1] if salida.strip() else ""
    return {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|error|errors)", ultima)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--proyecto", type=Path, default=None, help="carpeta del proyecto (la carpeta raphael, la que tiene _reference/ y packages/)")
    ap.add_argument("--python", default=sys.executable, help="intérprete con pytest, pydantic, pyyaml y httpx")
    args = ap.parse_args()
    raiz = args.proyecto or proyecto_por_defecto()
    if raiz is None or not (raiz / EMPRESAS).is_dir() or not (raiz / HARNESS_VIEJO).is_dir():
        print(f"No encontré el código de Empresas en {raiz}. Pasá --proyecto.")
        return 2

    total: dict[str, int] = {}
    fallos: list[str] = []
    with tempfile.TemporaryDirectory(prefix="regresion-empresas-") as tmp:
        tmp_path = Path(tmp)
        for repo in sorted((raiz / EMPRESAS).glob("raphael-*")):
            shutil.copytree(repo, tmp_path / repo.name, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        h = tmp_path / "raphael-harness"
        shutil.copytree(CORE / "compat-shim" / "raphael_harness", h / "src" / "raphael_harness",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for sub in ("tests", "ejemplos"):
            shutil.copytree(raiz / HARNESS_VIEJO / sub, h / sub, ignore=shutil.ignore_patterns("__pycache__"))
        env = {**os.environ, "PYTHONPATH": str(CORE / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
        print(f"Raphael Empresas sobre el harness v2 ({CORE.name}), desde {raiz}\n")
        for repo in sorted(tmp_path.glob("raphael-*")):
            r = subprocess.run([args.python, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=repo, env=env,
                               capture_output=True, text=True)
            n = contar(r.stdout)
            for k, v in n.items():
                total[k] = total.get(k, 0) + v
            ok = r.returncode == 0
            if not ok:
                fallos.append(repo.name)
            ultima = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
            print(f"  {'OK   ' if ok else 'FALLA'} {repo.name:<22} {ultima}")
            if not ok:
                print("\n".join("        " + ln for ln in r.stdout.strip().splitlines()[-25:]))
    errores = total.get("error", 0) + total.get("errors", 0)
    print(f"\nTotal: {total.get('passed', 0)} pasan, {total.get('failed', 0)} fallan, {total.get('skipped', 0)} salteados"
          f"{f', {errores} con error' if errores else ''}.")
    return 1 if fallos or total.get("failed") or total.get("error") or total.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
