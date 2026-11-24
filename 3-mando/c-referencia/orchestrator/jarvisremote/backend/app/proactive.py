"""Aprendizaje proactivo (2026-10-13, ítem 5 del plan).

Cuando PROACTIVE_LEARNING_ENABLED está ON, un loop de fondo hace que Raphael, por iniciativa
propia y cada tanto:
  1. AMPLÍE un caso de investigación abierto (research_cases) — le suma un hallazgo nuevo, o
  2. si no hay casos, LLENE un hueco del vault (crea una nota sobre una nota citada que no
     existe todavía — curiosity).

Default OFF: gasta LLM/red. Fail-soft: un ciclo que falla se loguea y no corta el loop. Las
acciones pasan por el agente normal (con sus gates intactos) y por la compuerta de privacidad.

Nota de diseño: los prompts NO usan verbos de investigación ("investigá", "research"…) a
propósito, para no re-disparar la creación de un caso nuevo (ver research_cases.looks_like_research)
y entrar en un bucle de casos.
"""

from __future__ import annotations

import asyncio
import logging

from .config import settings

logger = logging.getLogger("jarvis.proactive")

_STARTUP_DELAY_SECONDS = 120.0
_CONV_ID = "proactive"


async def run_once() -> dict:
    """Un ciclo: amplía un caso abierto, o si no hay, llena un hueco del vault. Aislado para testear."""
    from .agent import run_agent
    from . import research_cases

    abiertas = [c for c in research_cases.list_cases() if c.get("status") == "abierta"]
    if abiertas:
        caso = abiertas[-1]  # el menos reciente -> rota entre todos con el tiempo
        prompt = (
            f"Ampliá lo que sabemos sobre este tema y sumá UN dato nuevo, concreto y verificable "
            f"(con fuente si podés): «{caso['title']}». Respondé solo con el dato nuevo, breve."
        )
        _, reply, _ = await run_agent(prompt, conversation_id=_CONV_ID)
        if reply:
            research_cases.add_finding(caso["id"], reply[:500])
        try:
            from . import mission_control

            await mission_control.report("inv", f"🔎 amplié: {caso['title'][:60]}", inc=0)
        except Exception:  # noqa: BLE001
            pass
        return {"accion": "amplio_caso", "caso": caso["id"]}

    # Sin casos abiertos: llenar un hueco del vault.
    from .obsidian import curiosity

    gaps = (await asyncio.to_thread(curiosity.curiosidad, 3)).get("faltantes", [])
    if gaps:
        titulo = gaps[0].get("titulo") or ""
        if titulo:
            prompt = (
                f"Creá una nota de conocimiento clara y bien enlazada sobre: «{titulo}». "
                f"Buscá información si hace falta y guardala en el vault."
            )
            await run_agent(prompt, conversation_id=_CONV_ID)
            try:
                from . import mission_control

                await mission_control.report("mem", f"🧠 llené un hueco: {titulo[:60]}", inc=1)
            except Exception:  # noqa: BLE001
                pass
            return {"accion": "lleno_hueco", "titulo": titulo}
    return {"accion": "nada_que_hacer"}


async def proactive_loop() -> None:
    """Loop de vida larga (default OFF, PROACTIVE_LEARNING_ENABLED). Arrancado desde el startup
    de FastAPI. Un fallo se loguea y no corta el loop."""
    if not settings.proactive_learning_enabled:
        logger.info("aprendizaje proactivo deshabilitado (PROACTIVE_LEARNING_ENABLED=false)")
        return
    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            out = await run_once()
            logger.info("proactivo: %s", out)
        except Exception:  # noqa: BLE001
            logger.exception("el ciclo proactivo falló")
        await asyncio.sleep(max(1800.0, settings.proactive_interval_hours * 3600))
