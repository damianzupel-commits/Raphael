"""Tests de los endpoints de la console (llamando los handlers directo, sin HTTP)."""

from __future__ import annotations

import asyncio

import fastapi

from app.harness.model_registry import registry
from app.routers import brigada as br


def test_get_model_config_no_expone_secretos():
    snap = asyncio.run(br.get_model_config())
    assert "default" in snap and "stations" in snap and "llm_stations" in snap
    assert "api_key" not in snap["default"]


def test_set_model_config_asigna_y_quita():
    try:
        snap = asyncio.run(br.set_model_config(
            br.StationModelIn(station="E5_redaccion", model="deepseek-r1",
                              base_url="http://x/v1", api_key="secreto")
        ))
        assert snap["stations"]["E5_redaccion"]["model"] == "deepseek-r1"
        assert "api_key" not in snap["stations"]["E5_redaccion"]  # la key no se filtra
        assert registry.for_station("E5_redaccion").model == "deepseek-r1"

        snap2 = asyncio.run(br.set_model_config(br.StationModelIn(station="E5_redaccion", model="")))
        assert "E5_redaccion" not in snap2["stations"]  # override quitado
    finally:
        registry.unset("E5_redaccion")


def test_set_model_config_rechaza_estacion_sin_llm():
    try:
        asyncio.run(br.set_model_config(br.StationModelIn(station="E1_reconocimiento", model="x")))
        assert False, "debería rechazar una estación sin LLM"
    except fastapi.HTTPException as e:
        assert e.status_code == 400
