"""Puerta del monorepo: corre las cuatro suites (core, orchestrator, business, server) y ruff, y resume.

Cada suite corre con pytest en su propia carpeta (cada una tiene su conftest y sus rutas). No saltea nada.

Uso (desde la carpeta raphael):
    python tools\\gate.py                          # usa .venv\\Scripts\\python.exe si existe, si no el actual
    python tools\\gate.py --python C:\\ruta\\python.exe
    python tools\\gate.py --solo core business     # solo algunas suites (ruff corre igual)
Sale con 0 si todo pasa y con 2 si algo falla.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "core": ROOT / "packages" / "core",
    "orchestrator": ROOT / "packages" / "orchestrator",
    "business": ROOT / "brigades" / "business",
    "server": ROOT / "apps" / "server" / "api",
}
RUFF_PATHS = ["packages", "brigades/business", "apps/server"]


def default_python() -> str:
    for cand in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if cand.is_file():
            return str(cand)
    return sys.executable


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def counts(out: str) -> dict[str, int]:
    last = next((ln for ln in reversed(out.splitlines()) if re.search(r"\d+ (passed|failed|error)", ln)), "")
    return {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|errors?)", last)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--python", default=None, help="intérprete con las cuatro piezas instaladas, pytest y ruff")
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
        code, out = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], folder)
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
