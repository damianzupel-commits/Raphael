"""Curiosidad -- el primer impulso propio de Raphael (Etapa C, ver
`vision/ETAPAS-BCD-diseno.md`; principio #6, búsqueda activa de información).

El cerebro no espera pasivo: busca lo que reduce su incertidumbre. Acá Raphael detecta
sus propios HUECOS de conocimiento y los surge (modo solo-avisar por default, decisión
de Damian 2026-10-06; de bajo riesgo porque solo mira el vault):
  - **Notas faltantes:** títulos citados con [[wikilinks]] que no existen como nota.
    Si muchas notas la piden, es un hueco importante ("todos quieren X y X no está").
  - **Notas huérfanas:** notas que nadie enlaza (sin backlinks), aisladas del grafo.

Qué hacer con los huecos (investigar/ingerir/conectar) es la parte que ACTÚA: por la
regla de dos niveles, "juntar/aprender" es autónomo, pero arranca en solo-avisar. Si se
habilita el actuar, la compuerta de privacidad ([[privacy]]) decide el modelo: lo
sensible nunca va al tier 2 free.

PROCESADOR: tier 0 -- detección = cómputo de grafo PURO, sin modelo. El core
`find_gaps` es puro y testeable.
"""

from __future__ import annotations

import asyncio
import logging

from ..config import settings
from . import vault

logger = logging.getLogger("jarvis.obsidian.curiosity")

_STARTUP_DELAY_SECONDS = 150.0


def find_gaps(notes: list[dict], min_citas: int = 1) -> dict:
    """Huecos del grafo. `notes`: lista de {id, title, links} (links = títulos citados).
    Puro. Devuelve faltantes (notas citadas que no existen, ordenadas por cuántos las
    piden) y huérfanas (sin ningún enlace entrante)."""
    by_title = {n["title"].strip().lower(): n["id"] for n in notes}
    incoming: dict[str, int] = {n["id"]: 0 for n in notes}
    missing: dict[str, set[str]] = {}
    for n in notes:
        for lt in n.get("links", []):
            k = (lt or "").strip().lower()
            if not k:
                continue
            tgt = by_title.get(k)
            if tgt is not None:
                if tgt != n["id"]:
                    incoming[tgt] = incoming.get(tgt, 0) + 1
            else:
                missing.setdefault(k, set()).add(n["id"])

    faltantes = [{"tipo": "falta_nota", "titulo": t, "citada_por": len(ids)} for t, ids in missing.items() if len(ids) >= min_citas]
    faltantes.sort(key=lambda d: d["citada_por"], reverse=True)
    huerfanas = [{"tipo": "huerfana", "id": n["id"], "titulo": n["title"]} for n in notes if incoming.get(n["id"], 0) == 0]
    return {"faltantes": faltantes, "huerfanas": huerfanas}


def curiosidad(limit: int = 10) -> dict:
    """Qué le falta saber a Raphael, ahora. Lee el vault y prioriza los huecos. Read-only."""
    notes = [{"id": n.id, "title": n.title, "links": n.links} for n in vault.list_notes()]
    gaps = find_gaps(notes)
    return {
        "total_faltantes": len(gaps["faltantes"]),
        "total_huerfanas": len(gaps["huerfanas"]),
        "faltantes": gaps["faltantes"][:limit],
        "huerfanas": gaps["huerfanas"][:limit],
        "nota": "Huecos del vault (solo-avisar). Para investigarlos/conectarlos hace falta habilitar el actuar.",
    }


async def curiosity_loop() -> None:
    """Job de vida larga (default APAGADO). Cada `CURIOSITY_INTERVAL_HOURS` detecta los
    huecos y los SURGE (los loguea -- modo solo-avisar). No actúa: solo avisa."""
    if not settings.curiosity_enabled:
        logger.info("curiosidad deshabilitada (CURIOSITY_ENABLED=false)")
        return
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            c = await asyncio.to_thread(curiosidad, 8)
            top = ", ".join(f"{g['titulo']} (x{g['citada_por']})" for g in c["faltantes"][:5]) or "(sin notas faltantes)"
            logger.info("curiosidad: %s notas faltantes, %s huérfanas. Más pedidas: %s",
                        c["total_faltantes"], c["total_huerfanas"], top)
            # Centro de Mando: reporta a la brigada Memoria (2026-10-13). Best-effort, inc=0
            # (detección, no creación de conocimiento).
            try:
                from .. import mission_control

                await mission_control.report(
                    "mem",
                    f"🔎 {c['total_faltantes']} huecos · {c['total_huerfanas']} huérfanas",
                    inc=0,
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception:
            logger.exception("la detección de curiosidad falló")
        await asyncio.sleep(max(3600.0, settings.curiosity_interval_hours * 3600))
