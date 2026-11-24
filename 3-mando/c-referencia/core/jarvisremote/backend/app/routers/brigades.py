"""Endpoints HTTP genéricos de las brigadas (capa jefe de brigada).

Generaliza el router de Scout a cualquier brigada registrada (brigades/registry.py):
la Suite le habla al jefe de la brigada <id> por acá. Mismo patrón que /api/scout/*
(que queda para la vista de Scout ya andando); las vistas nuevas usan esto.

  GET  /api/brigade/list            -> brigadas con jefe disponible
  GET  /api/brigade/{id}/meta       -> nombre, modelo, nº de tools, persistencia
  POST /api/brigade/{id}/chat       -> corre un turno del jefe, stream NDJSON del feed
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import verify_api_key, verify_read

logger = logging.getLogger("jarvis.brigades")
router = APIRouter(prefix="/api/brigade", tags=["brigades"])


@router.get("/list", dependencies=[Depends(verify_read)])
async def brigade_list() -> dict:
    from brigades.registry import available

    return {"brigades": available()}


@router.get("/{brigade_id}/meta", dependencies=[Depends(verify_read)])
async def brigade_meta(brigade_id: str) -> dict:
    from brigades.registry import get_chief

    try:
        chief = get_chief(brigade_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"brigada desconocida: {brigade_id}")
    return {
        "id": chief.config.id,
        "name": chief.config.name,
        "model": chief.model,
        "tools": len(chief.config.tool_names),
        "persistent": chief.config.persistent,
    }


@router.get("/{brigade_id}/activity", dependencies=[Depends(verify_read)])
async def brigade_activity(brigade_id: str, limit: int = 40) -> dict:
    """"Lo que hizo solo" una brigada (feed proactivo). Hoy: Cerebro."""
    if brigade_id == "cerebro":
        from brigades.cerebro_activity import recent

        return {"items": recent(limit)}
    return {"items": []}


@router.get("/investigacion/skills", dependencies=[Depends(verify_read)])
async def investigacion_skills() -> dict:
    """Skills de la brigada de Investigación, por ayudante efímero (Scout / Forense)."""
    from brigades.investigacion import describe_skills

    return {"skills": describe_skills()}


@router.get("/cerebro/directrices", dependencies=[Depends(verify_read)])
async def cerebro_get_directrices() -> dict:
    from brigades.directrices import load_directrices

    return {"text": load_directrices()}


class DirectricesIn(BaseModel):
    text: str


@router.post("/cerebro/directrices", dependencies=[Depends(verify_api_key)])
async def cerebro_set_directrices(body: DirectricesIn) -> dict:
    from brigades.directrices import save_directrices

    ok = save_directrices(body.text or "")
    return {"ok": ok}


class ChatIn(BaseModel):
    message: str


@router.post("/{brigade_id}/chat", dependencies=[Depends(verify_api_key)])
async def brigade_chat(brigade_id: str, body: ChatIn):
    """Corre un turno de la brigada y streamea el feed en vivo (NDJSON). Mismo flujo que el orquestador liviano
    (orquestador/turno.py): el jefe reporta y el `final` lo produce la voz del orquestador; ningún texto de jefe o
    ayudante le llega al usuario directo."""
    from brigades.registry import get_chief

    try:
        chief = get_chief(brigade_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"brigada desconocida: {brigade_id}")

    message = (body.message or "").strip()
    queue: asyncio.Queue = asyncio.Queue()

    async def on_event(ev: dict) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            if not message:
                await queue.put({"type": "error", "message": "El mensaje está vacío."})
            else:
                from brigades.registry import get_spec
                from orquestador.turno import run_turno

                try:
                    spec = get_spec(brigade_id)
                except KeyError:  # jefe legacy sin spec (Scout)
                    spec = None
                await run_turno(chief, message, on_event, brigade=brigade_id, spec=spec)
        except Exception as exc:  # noqa: BLE001
            logger.exception("jefe %s falló", brigade_id)
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

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
