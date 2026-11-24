"""Guardrail de LÍNEAS ROJAS del auto-rediseño (Etapa D, decisión de Damian 2026-10-06).

Formaliza en CÓDIGO (no solo en política) la regla: la auto-modificación de Raphael
NUNCA puede tocar nada que debilite la seguridad -- ni con confirmación. Los archivos
protegidos (`settings.self_protected_paths`): el scope de pentest (`authorized_targets.yaml`),
el gate de confirmación en sí, la auth, los secretos (`.env`) y la config (que tiene los
flags de los gates). Si de verdad hay que cambiar uno, lo hace Damian a mano, fuera del
camino de self-repair.

Se chequea en DOS puntos: al proponer (`selfrepair_propose_fix`) y al aplicar
(`code_apply_fix`), para que ni se proponga ni se aplique, pase lo que pase.

PROCESADOR: tier 0 -- chequeo de ruta PURO, sin modelo.
"""

from __future__ import annotations

from ..config import settings


def _protected_fragments() -> list[str]:
    return [p.strip().replace("\\", "/").lower() for p in str(settings.self_protected_paths).split(",") if p.strip()]


def is_protected(file: str) -> bool:
    """True si `file` matchea alguna línea roja (substring de ruta, normalizado)."""
    f = (file or "").replace("\\", "/").lower()
    return any(frag in f for frag in _protected_fragments())


def check(file: str) -> str | None:
    """Motivo si el archivo es intocable (línea roja), o None si se puede modificar."""
    if is_protected(file):
        return (
            f"'{file}' es una LÍNEA ROJA de seguridad: la auto-modificación NO puede tocarlo "
            f"(scope/gates/auth/config/secretos), ni con confirmación. Si hay que cambiarlo, "
            f"lo hace Damian a mano, fuera del camino de self-repair."
        )
    return None
