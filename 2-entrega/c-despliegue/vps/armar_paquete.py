"""Arma `raphael-v2-nube.tgz`: lo que se sube al VPS para instalar Raphael Empresas v2.

Junta, desde la carpeta del proyecto, los cuatro paquetes (harness, orquestador, brigada Empresas y su API) sin tests,
cachés ni datos, más los scripts de esta carpeta y la instalación de la clienta. No incluye `.env`, claves ni bases.

Uso (en la PC, desde cualquier lado):
    python armar_paquete.py                          # deja el paquete en <proyecto>\\dist\\raphael-v2-nube.tgz
    python armar_paquete.py --instalacion ruta\\clienta-real.installation.yaml --salida D:\\otra\\carpeta
Después:  scp raphael-v2-nube.tgz root@<IP>:  y en el VPS:  tar xzf raphael-v2-nube.tgz && cd raphael-v2-nube &&
          sudo ./instalar-v2.sh <dominio>
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]                     # raphael/
PIECES = {
    "raphael-core": "1-harness/b-codigo",
    "raphael-orchestrator": "1-harness/c-brigadas/00-orquestador/b-codigo",
    "raphael-empresas": "1-harness/c-brigadas/15-empresas/b-codigo",
    "raphael-empresas-api": "2-entrega/b-codigo/servidor/api",
}
KEEP_TOP = {"src", "pyproject.toml", "README.md", "API.md", "manifest.yaml"}
SKIP = ["__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", ".datos", "*.sqlite", "*.env", ".env*", "*.egg-info",
        "claves", "*.jks", "*.key", "*.pem"]
SCRIPTS = ["instalar-v2.sh", "actualizar-v2.sh", "copia.sh", "raphael-empresas.service", "raphael-copia.service",
           "raphael-copia.timer", "Caddyfile.plantilla", "meta.env.plantilla", "tienda.env.plantilla", "LEEME.md"]
ROOT = "raphael-v2-nube"


def skipped(path: Path) -> bool:
    return any(fnmatch.fnmatch(part, pat) for part in path.parts for pat in SKIP)


def files_of(piece_dir: Path) -> list[Path]:
    out = []
    for p in sorted(piece_dir.rglob("*")):
        rel = p.relative_to(piece_dir)
        if p.is_file() and rel.parts[0] in KEEP_TOP and not skipped(rel):
            out.append(p)
    return out


def add(tar: tarfile.TarFile, src: Path, arc: str, mode: int = 0o644) -> None:
    data = src.read_bytes()
    if src.suffix in (".sh", ".service", ".timer", ".plantilla") or src.name == "Caddyfile.plantilla":
        data = data.replace(b"\r\n", b"\n")          # si se editó en Windows, que no rompa bash ni systemd
    info = tarfile.TarInfo(arc)
    info.size, info.mode, info.mtime = len(data), mode, int(src.stat().st_mtime)
    tar.addfile(info, io.BytesIO(data))


def build(installation: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{ROOT}.tgz"
    sums = []
    with tarfile.open(out, "w:gz") as tar:
        for name in SCRIPTS:
            add(tar, HERE / name, f"{ROOT}/{name}", 0o755 if name.endswith(".sh") else 0o644)
        add(tar, installation, f"{ROOT}/clienta.installation.yaml")
        for name, rel in PIECES.items():
            base = PROJECT / rel
            if not (base / "pyproject.toml").is_file():
                raise SystemExit(f"No encuentro {base}")
            for f in files_of(base):
                arc = f"{ROOT}/piezas/{name}/{f.relative_to(base).as_posix()}"
                add(tar, f, arc)
                sums.append(f"{hashlib.md5(f.read_bytes()).hexdigest()}  {arc}")
    (out_dir / f"{ROOT}.md5.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--instalacion", type=Path, default=HERE.parent / "instalacion-clienta" / "clienta.installation.yaml")
    ap.add_argument("--salida", type=Path, default=PROJECT / "dist")
    a = ap.parse_args()
    out = build(a.instalacion, a.salida)
    with tarfile.open(out) as t:
        n = len(t.getnames())
    print(f"Listo: {out} ({out.stat().st_size // 1024} KB, {n} archivos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
