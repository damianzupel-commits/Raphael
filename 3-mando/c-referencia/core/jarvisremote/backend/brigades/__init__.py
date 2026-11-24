"""Jefes de brigada — la capa de mando (orquestador → jefe → skills).

Generaliza el molde de Scout a un `BrigadeChief` reusable: un supervisor por
brigada con sus tools acotadas (menor privilegio), su modelo, su vault y su
estado persistente. Las brigadas nuevas se DECLARAN con un `BrigadeSpec` (spec.py)
y las ejecuta el motor genérico (engine.py). Ver docs/BLUEPRINT-habilidades-y-defensas-brigadas.md
y docs/PLAYBOOK-brigadas.md.

Los exports son PEREZOSOS a propósito: `brigades.spec` y las escenas de validación son livianas
(solo dataclasses), y importarlas no debe cargar `app.tools` — el arranque liviano
(orquestador/slim_tools.py) tiene que poder correr ANTES de que algo importe `brigades.chief`.
"""

from __future__ import annotations

__all__ = ["BrigadeChief", "ChiefConfig", "get_chief", "available"]


def __getattr__(name: str):
    if name in ("BrigadeChief", "ChiefConfig"):
        from . import chief

        return getattr(chief, name)
    if name in ("get_chief", "available"):
        from . import registry

        return getattr(registry, name)
    raise AttributeError(f"module 'brigades' has no attribute {name!r}")
