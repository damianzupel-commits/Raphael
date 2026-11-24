"""Tarea proactiva de Cerebro (paso 3) — lo que hace SOLO.

Reusa los loops/funciones que ya existen (no duplica): reindexa la memoria unificada
(que lo capturado por las brigadas sea buscable semánticamente) y corre la
consolidación "sueño" (que ESCRIBE las notas de síntesis/conclusión de Cerebro).
Todo aditivo y reversible (nunca borra). Registra cada acción en cerebro_activity
(feed "lo que hizo solo" de la Suite) y lo reporta a la brigada Memoria del panel.

Apagado por default (CEREBRO_PROACTIVE_ENABLED=false), misma norma del proyecto para
los jobs autónomos: escribe notas solo y la consolidación usa el LLM local (pesado en
CPU). Prenderlo con la var + reiniciar = Cerebro trabaja por su cuenta cada
CEREBRO_PROACTIVE_INTERVAL_MINUTES. La autonomía la va a acotar el store de directrices
(paso 4).
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("brigades.cerebro.proactive")


def _enabled() -> bool:
    return os.getenv("CEREBRO_PROACTIVE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _interval_minutes() -> int:
    try:
        return max(5, int(os.getenv("CEREBRO_PROACTIVE_INTERVAL_MINUTES", "180")))
    except ValueError:
        return 180


async def _report(msg: str) -> None:
    try:
        from app import mission_control

        await mission_control.report("mem", msg)
    except Exception:  # noqa: BLE001
        pass


async def cerebro_pass() -> dict:
    """Una pasada proactiva: reindexa + consolida. Devuelve un resumen. Defensivo:
    un fallo de un paso no frena el otro ni rompe el loop."""
    from app.obsidian import consolidation, vault

    from . import cerebro_activity

    summary: dict = {}

    # 1. Reindexar (que las capturas de las brigadas sean buscables por semántica).
    try:
        res = await asyncio.to_thread(vault.reindex_all)
        n = sum(v for v in res.values() if isinstance(v, int)) if isinstance(res, dict) else 0
        cerebro_activity.log("reindex", f"Reindexé la memoria ({n} notas).", res if isinstance(res, dict) else None)
        await _report(f"🧠 reindexó la memoria ({n})")
        summary["reindex"] = res
    except Exception as exc:  # noqa: BLE001
        logger.warning("reindex falló: %s", exc)
        cerebro_activity.log("info", f"Reindex falló: {exc}")

    # 2. Consolidación "sueño" = escribe las notas de conclusión de Cerebro.
    try:
        res = await consolidation.run_once(dry_run=False)
        creados = res.get("consolidados") or []
        for c in creados:
            cerebro_activity.log(
                "conclusion", f"Nueva conclusión: {c.get('title')}", {"note_id": c.get("note_id")}
            )
        if creados:
            await _report(f"🧠 escribió {len(creados)} conclusión(es)")
        else:
            cerebro_activity.log("consolidacion", f"Consolidación sin clusters nuevos ({res.get('status')}).")
        summary["consolidacion"] = res
    except Exception as exc:  # noqa: BLE001
        logger.warning("consolidación falló: %s", exc)
        cerebro_activity.log("info", f"Consolidación falló: {exc}")

    return summary


async def cerebro_loop() -> None:
    """Loop de fondo de Cerebro. Apagado por default; prenderlo con
    CEREBRO_PROACTIVE_ENABLED=true + reiniciar el backend."""
    if not _enabled():
        logger.info("cerebro proactivo deshabilitado (CEREBRO_PROACTIVE_ENABLED=false)")
        return
    interval = _interval_minutes() * 60
    logger.info("cerebro proactivo arrancado (cada %s min)", _interval_minutes())
    while True:
        try:
            await cerebro_pass()
        except Exception:  # noqa: BLE001
            logger.warning("cerebro_pass falló", exc_info=True)
        await asyncio.sleep(interval)
