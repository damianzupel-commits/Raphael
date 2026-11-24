"""Endpoints HTTP de Raphael Scout (brigada de Investigación/intel) para la Suite.

Separado del chat del maestro: la Suite (docs/raphael/suite-raphael.html) tiene su
propia vista de Scout y habla con estos endpoints. Scout corre con su modelo BYOM
propio (ej. Groq free) y su vault de investigación. Ver backend/scout/ y
docs/SPEC-PRODUCTO-INVESTIGACION.md.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import verify_api_key, verify_read
from ..obsidian import profile as vault_profile
from ..obsidian import vault

logger = logging.getLogger("jarvis.scout")
router = APIRouter(prefix="/api/scout", tags=["scout"])


def _scout_profile():
    """VaultProfile del vault de investigación de Scout (según su config BYOM)."""
    from scout.config import load_scout_config

    cfg = load_scout_config()
    prof = vault_profile.VaultProfile(vault_path=cfg.vault_path, embeddings_path=cfg.embeddings_path)
    return prof, cfg


@router.get("/meta", dependencies=[Depends(verify_read)])
async def scout_meta() -> dict:
    """Modelo/endpoint BYOM y carpetas de Scout, para el header de la vista."""
    from scout.config import load_scout_config
    from scout.identity import SCOUT_NAME

    cfg = load_scout_config()
    return {
        "name": SCOUT_NAME,
        "model": cfg.model,
        "endpoint": cfg.base_url,
        "capture_dir": cfg.capture_dir,
        "vault": cfg.vault_path,
    }


@router.get("/notes", dependencies=[Depends(verify_read)])
async def scout_notes(limit: int = 30) -> dict:
    """Notas capturadas por Scout (tag 'investigacion'), más recientes primero."""
    prof, _ = _scout_profile()
    try:
        with vault_profile.use_profile(prof):
            notes = vault.list_notes(tag="investigacion")
    except Exception as exc:  # noqa: BLE001 — vault aún inexistente, etc.: la vista no debe romperse
        logger.warning("No se pudieron listar notas de Scout: %s", exc)
        return {"notes": []}
    limit = max(1, min(limit, 200))
    return {"notes": [n.to_summary_dict() for n in notes[:limit]]}


class ResearchIn(BaseModel):
    topic: str


@router.post("/research", dependencies=[Depends(verify_api_key)])
async def scout_research(body: ResearchIn):
    """Corre una investigación de Scout y streamea el feed en vivo como NDJSON
    (una línea JSON por evento: start / tool / tool_result / final / error).
    La UI lo lee con fetch + ReadableStream. El engine ya emite el evento 'final'.
    """
    from scout.engine import run_scout

    topic = (body.topic or "").strip()
    queue: asyncio.Queue = asyncio.Queue()

    async def on_event(ev: dict) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            if not topic:
                await queue.put({"type": "error", "message": "El tema está vacío."})
            else:
                await run_scout(topic, on_event=on_event)
        except Exception as exc:  # noqa: BLE001 — se reporta como evento, no se traga
            logger.exception("Scout research falló")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # centinela de fin de stream

    async def gen():
        task = asyncio.create_task(runner())
        try:
            while True:
                ev = await queue.get()
                if ev is None:
                    break
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(gen(), media_type="application/x-ndjson")
