"""Endpoints HTTP de la console multiagente (la pestaña "Brigada" de la ventana
de Raphael, tray-app). Exponen el registro de modelo por estación (ver/asignar)
y corren la brigada devolviendo el estado por estación.

Capa A parte 2 + backend de la console (2026-09-21). La UI (Qt / web) consume esto.
Las API keys NUNCA se exponen en las respuestas (snapshot sin secretos).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import verify_api_key
from ..harness.audit_brigade import run_audit_brigade
from ..harness.model_registry import LLM_STATIONS, StationModel, registry

router = APIRouter(prefix="/api/brigada", tags=["brigada"], dependencies=[Depends(verify_api_key)])


class StationModelIn(BaseModel):
    station: str
    model: str | None = None  # vacío/None => quitar el override (volver al global)
    base_url: str | None = None
    api_key: str | None = None
    timeout: float | None = None
    temperature: float | None = None


class RunIn(BaseModel):
    path: str


@router.get("/model-config")
async def get_model_config() -> dict:
    """Estado del registro: modelo por estación + default. SIN API keys."""
    return registry.snapshot()


@router.post("/model-config")
async def set_model_config(cfg: StationModelIn) -> dict:
    """Asigna (o quita, si model viene vacío) el modelo de una estación con LLM."""
    if cfg.station not in LLM_STATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"'{cfg.station}' no es una estación con LLM (validas: {list(LLM_STATIONS)})",
        )
    if not cfg.model:
        registry.unset(cfg.station)  # volver al modelo global
    else:
        d = registry.default
        registry.set(
            cfg.station,
            StationModel(
                model=cfg.model,
                base_url=cfg.base_url or d.base_url,
                api_key=cfg.api_key or d.api_key,
                timeout=cfg.timeout if cfg.timeout is not None else d.timeout,
                temperature=cfg.temperature,
            ),
        )
    return registry.snapshot()


@router.post("/run")
async def run_brigada(body: RunIn) -> dict:
    """Corre la brigada sobre un proyecto ya escaneado. Devuelve el estado por
    estación (para prender las estaciones en la UI) + el reporte."""
    return await run_audit_brigade(body.path)
