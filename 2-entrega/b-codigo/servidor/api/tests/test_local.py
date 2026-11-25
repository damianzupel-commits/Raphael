"""Sin clave solo desde la misma PC: ni el túnel, ni un proxy, ni una página ajena."""

import pytest
from fastapi.testclient import TestClient
from raphael_empresas.boot import start
from test_entorno import INSTALACION, ORCH_DEV

from raphael_empresas_api.app import create_app

LOCAL = "http://127.0.0.1:8787"


def client(tmp_path, local_open=True, base=LOCAL, ip="127.0.0.1"):
    dev = [ORCH_DEV / "15-empresas" / "b-codigo", ORCH_DEV / "00-orquestador" / "b-codigo"]
    rt, _ = start(INSTALACION, tmp_path, dev_dirs=dev, installed=False, env={})
    app = create_app(rt, tick=False, env_file=tmp_path / "raphael.env", environ={}, local_open=local_open)
    return TestClient(app, base_url=base, client=(ip, 5000))


def test_desde_la_pc_entra_sin_clave(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/v1/config").status_code == 200
    assert c.get("/api/v1/summary", headers={"Origin": LOCAL, "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert c.post("/api/v1/logout").status_code == 200


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/v1/pending/1/approve", {}),
    ("post", "/api/v1/pending/1/reject", {}),
    ("post", "/api/v1/pending/1/resolve", {}),
    ("post", "/api/v1/orders/1/status", {"status": "listo"}),
    ("post", "/api/v1/secretary", {"text": "aprobá la 1"}),
    ("put", "/api/v1/config", {"set": {}}),
    ("post", "/api/v1/config/clave", {"key": "otra-clave-larga"}),
])
def test_desde_la_pc_lo_que_ejecuta_pide_clave(tmp_path, method, path, body):
    assert client(tmp_path).request(method, path, json=body).status_code == 403


def test_con_la_clave_se_puede(tmp_path):
    c = client(tmp_path)
    c.app.state.auth.set_key("clave-segura")
    tok = c.post("/api/v1/login", json={"key": "clave-segura", "device": "t"}).json()["token"]
    r = c.post("/api/v1/secretary", json={"text": "hola"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_apagado_por_defecto(tmp_path):
    assert client(tmp_path, local_open=False).get("/api/v1/config").status_code == 401


@pytest.mark.parametrize("headers", [
    {"X-Forwarded-For": "203.0.113.5"},
    {"X-Forwarded-Host": "pc.tail.ts.net"},
    {"Tailscale-User-Login": "alguien"},
    {"Host": "pc.tail.ts.net"},
    {"Origin": "https://otra.example"},
    {"Sec-Fetch-Site": "cross-site"},
])
def test_tunel_proxy_y_paginas_ajenas_piden_clave(tmp_path, headers):
    assert client(tmp_path).get("/api/v1/config", headers=headers).status_code == 401


def test_otra_maquina_pide_clave(tmp_path):
    assert client(tmp_path, ip="192.168.1.20").get("/api/v1/config").status_code == 401
