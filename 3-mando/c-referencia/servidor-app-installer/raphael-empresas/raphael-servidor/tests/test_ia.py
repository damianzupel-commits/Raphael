"""La dueña le pone IA al orquestador desde el panel: se guarda local, la clave no vuelve a salir y el secretario la usa."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from raphael_servidor.app import Raphael, crear_app
from raphael_servidor.config import Config

RAIZ = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (RAIZ / "raphael-orquestador").is_dir(), reason="faltan los repos vecinos")


class Falla(Exception):
    def __init__(self, estado):
        self.response = type("R", (), {"status_code": estado})()


@pytest.fixture
def entorno(tmp_path):
    piezas = tmp_path / "piezas"
    piezas.mkdir()
    for base in ("raphael-harness", "raphael-orquestador"):
        shutil.copytree(RAIZ / base, piezas / base, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    datos = tmp_path / "datos"
    datos.mkdir()
    perfil = yaml.safe_load((RAIZ / "raphael-harness" / "ejemplos" / "perfil-ropa-medida.yaml").read_text(encoding="utf-8"))
    perfil["brigadas"] = []
    (datos / "perfil.yaml").write_text(yaml.safe_dump(perfil, allow_unicode=True), encoding="utf-8")
    llamadas = []
    respuestas = {"siguiente": json.dumps({"decir": "Hoy no hay nada urgente, tranqui.", "hacer": []}), "error": None}

    def transporte(url, cuerpo, headers):
        llamadas.append((url, cuerpo, headers))
        if respuestas["error"]:
            raise respuestas["error"]
        return {"choices": [{"message": {"content": respuestas["siguiente"]}}], "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    cfg = Config(dir=datos, piezas=str(piezas), tareas=False)
    with TestClient(crear_app(cfg, Raphael(cfg, transporte_ia=transporte))) as c:
        c.headers["Authorization"] = "Bearer " + c.post("/api/primera-clave", json={"clave": "clave-segura"}).json()["token"]
        yield c, datos, llamadas, respuestas


NVIDIA = {"proveedor": "nvidia", "base_url": "https://integrate.api.nvidia.com/v1", "model": "nvidia/nemotron", "api_key": "nvapi-secreta"}


def test_sin_ia_arranca_en_reglas_y_ofrece_los_proveedores(entorno):
    c, *_ = entorno
    d = c.get("/api/ia").json()
    assert d["configurada"] is False and "sin IA" in d["activa"]
    assert {p["id"] for p in d["presets"]} >= {"nvidia", "ollama", "lmstudio", "otro"}


def test_probar_usa_la_clave_y_traduce_los_errores(entorno):
    c, _, llamadas, resp = entorno
    resp["siguiente"] = "listo"
    ok = c.post("/api/ia/probar", json=NVIDIA).json()
    assert ok == {"ok": True, "respuesta": "listo"}
    assert llamadas[0][0].endswith("/v1/chat/completions") and llamadas[0][2]["Authorization"] == "Bearer nvapi-secreta"
    resp["error"] = Falla(401)
    assert "rechazó la clave" in c.post("/api/ia/probar", json=NVIDIA).json()["error"]
    resp["error"] = Falla(404)
    assert "modelo" in c.post("/api/ia/probar", json=NVIDIA).json()["error"]
    assert "Falta el nombre" in c.post("/api/ia/probar", json={**NVIDIA, "model": ""}).json()["error"]


def test_guardar_activa_la_ia_sin_reiniciar_y_la_clave_no_vuelve_a_salir(entorno):
    c, datos, _, _ = entorno
    r = c.post("/api/ia", json=NVIDIA).json()
    assert r["configurada"] and r["tiene_clave"] and "nvidia/nemotron" in r["activa"]
    assert "nvapi-secreta" not in c.get("/api/ia").text and "nvapi-secreta" not in c.get("/api/resumen").text
    assert json.loads((datos / "ia.json").read_text(encoding="utf-8"))["api_key"] == "nvapi-secreta"
    c.post("/api/ia", json={**NVIDIA, "model": "otro/modelo", "api_key": ""})              # sin clave nueva: conserva la anterior
    assert json.loads((datos / "ia.json").read_text(encoding="utf-8"))["api_key"] == "nvapi-secreta"
    assert "otro/modelo" in c.get("/api/resumen").json()["ia"]


def test_validaciones_al_guardar(entorno):
    c, *_ = entorno
    assert c.post("/api/ia", json={**NVIDIA, "base_url": "integrate.nvidia.com"}).status_code == 400
    assert c.post("/api/ia", json={**NVIDIA, "model": ""}).status_code == 400
    assert c.get("/api/ia").json()["configurada"] is False


def test_el_secretario_usa_el_modelo_configurado_y_sin_modelo_cae_a_reglas(entorno):
    c, _, llamadas, _ = entorno
    c.post("/api/ia", json=NVIDIA)
    n = len(llamadas)
    r = c.post("/api/secretaria", json={"texto": "che, ¿cómo ves el panorama de la semana que viene en general?"}).json()
    assert r["texto"].startswith("Hoy no hay nada urgente, tranqui") and len(llamadas) == n + 1
    sistema = llamadas[-1][1]["messages"][0]["content"]
    assert "TAREAS DE HOY" in sistema and llamadas[-1][1]["model"] == "nvidia/nemotron"
    c.post("/api/ia/quitar")
    assert "sin IA" in c.get("/api/resumen").json()["ia"]
    assert "No te entendí" in c.post("/api/secretaria", json={"texto": "che, ¿cómo ves el panorama de la semana que viene?"}).json()["texto"]


def test_local_no_pide_clave(entorno):
    c, *_ = entorno
    r = c.post("/api/ia", json={"proveedor": "ollama", "base_url": "http://localhost:11434/v1", "model": "llama3.1"}).json()
    assert r["configurada"] and not r["tiene_clave"] and "llama3.1" in r["activa"]
