"""Compuerta de privacidad por sensibilidad (Etapa C, decisión de Damian 2026-10-06).

El tier 2 son modelos FREE que pueden rutear data a terceros. Regla: el contenido
SENSIBLE (material personal / Fénix) NUNCA sale a un free. Esta compuerta decide, para
un contenido dado, si hay que subir de tier para proteger la privacidad.

`is_sensitive(note_ids)` → True si alguna nota vive en una carpeta sensible
(`OBSIDIAN_SENSITIVE_DIRS`). `safe_tier(note_ids, base_tier)` → sube el tier 2 al
`OBSIDIAN_SENSITIVE_TIER` (default 1 = local, privado) cuando el contenido es sensible;
los demás tiers y el contenido no sensible pasan sin cambio.

PROCESADOR: tier 0 -- cómputo PURO (chequeo de carpeta), sin modelo.
"""

from __future__ import annotations

from ..config import settings


def _sensitive_dirs() -> set[str]:
    return {d.strip() for d in str(settings.obsidian_sensitive_dirs).split(",") if d.strip()}


def is_sensitive(note_ids: list[str]) -> bool:
    """True si alguna nota pertenece a una carpeta sensible (por su primer segmento de id)."""
    sens = _sensitive_dirs()
    return any((nid or "").split("/", 1)[0] in sens for nid in note_ids)


def safe_tier(note_ids: list[str], base_tier: int) -> int:
    """Devuelve el tier a usar protegiendo la privacidad: si el contenido es sensible y el
    tier pedido es el 2 (free), lo sube a `OBSIDIAN_SENSITIVE_TIER`. Todo lo demás, igual."""
    if base_tier == 2 and is_sensitive(note_ids):
        return int(settings.obsidian_sensitive_tier)
    return base_tier
