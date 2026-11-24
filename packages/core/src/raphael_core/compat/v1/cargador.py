"""Encuentra las piezas v1 instaladas (brigadas y orquestador). Copia de raphael-harness 0.4 sobre el v2.

1. Producción: paquetes instalados que declaran entry points en los grupos
   `raphael.brigadas` y `raphael.orquestador` (ver el pyproject.toml de cada repo).
2. Desarrollo: una carpeta con los repos `raphael-*` lado a lado (variable RAPHAEL_DEV o
   `rutas_dev`). Se usa el `src/` de cada repo sin instalar nada.
"""

from __future__ import annotations

import importlib
import os
import sys
from importlib.metadata import entry_points
from pathlib import Path

from .contrato import CONTRATO, Brigada, Orquestador

GRUPO_BRIGADAS = "raphael.brigadas"
GRUPO_ORQUESTADOR = "raphael.orquestador"


def _de_entry_points() -> tuple[list[type], list[type]]:
    brig = [ep.load() for ep in entry_points(group=GRUPO_BRIGADAS)]
    orq = [ep.load() for ep in entry_points(group=GRUPO_ORQUESTADOR)]
    return brig, orq


def _de_carpeta(raiz: Path) -> tuple[list[type], list[type]]:
    brig, orq = [], []
    for repo in sorted(raiz.glob("raphael-*")):
        src = repo / "src"
        if not src.is_dir() or repo.name == "raphael-harness":
            continue
        for pkg in sorted(src.glob("raphael_*")):
            if not (pkg / "__init__.py").exists():
                continue
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            mod = importlib.import_module(pkg.name)
            if getattr(mod, "BRIGADA", None):
                brig.append(mod.BRIGADA)
            if getattr(mod, "ORQUESTADOR", None):
                orq.append(mod.ORQUESTADOR)
    return brig, orq


def descubrir(rutas_dev: str | Path | None = None) -> tuple[type | None, dict[str, type], list[str]]:
    """(clase del orquestador, {nombre: clase de brigada}, avisos)."""
    avisos: list[str] = []
    brig, orq = _de_entry_points()
    raiz = rutas_dev or os.environ.get("RAPHAEL_DEV")
    if raiz:
        b2, o2 = _de_carpeta(Path(raiz))
        brig += [b for b in b2 if b.nombre not in {x.nombre for x in brig}]
        orq += [o for o in o2 if o not in orq]
    brigadas: dict[str, type] = {}
    for cls in brig:
        if not (isinstance(cls, type) and issubclass(cls, Brigada)):
            avisos.append(f"{cls!r} no es una Brigada: se ignora")
        elif getattr(cls, "contrato", None) != CONTRATO:
            avisos.append(f"brigada '{cls.nombre}' usa el contrato {cls.contrato}; el harness usa {CONTRATO}: no se carga")
        else:
            brigadas[cls.nombre] = cls
    orquestador = None
    for cls in orq:
        if isinstance(cls, type) and issubclass(cls, Orquestador) and getattr(cls, "contrato", None) == CONTRATO:
            orquestador = cls
            break
        avisos.append(f"orquestador {cls!r} incompatible: se ignora")
    return orquestador, brigadas, avisos
