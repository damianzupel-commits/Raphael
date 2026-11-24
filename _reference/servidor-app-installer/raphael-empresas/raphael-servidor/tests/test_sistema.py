"""Servidor + relay + central juntos (si los repos están al lado)."""

import hashlib
import hmac
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[2]
for r in ("raphael-relay", "raphael-central"):
    sys.path.insert(0, str(RAIZ / r / "src"))
pytest.importorskip("raphael_relay")
pytest.importorskip("raphael_central")

from raphael_central.app import Base, crear_app as app_central  # noqa: E402
from raphael_relay.app import Cola, Rutas, crear_app as app_relay  # noqa: E402
from raphael_servidor.app import Raphael  # noqa: E402
from raphael_servidor.config import Config  # noqa: E402
from raphael_servidor.servicios import ColaRelay  # noqa: E402

ADMIN = {"Authorization": "Bearer " + "a" * 20}


def puente(cliente):
    """Convierte las llamadas http del servidor en llamadas al TestClient de la otra app."""
    def post(url, cuerpo, headers=None):
        return cliente.post(urlparse(url).path, json=cuerpo, headers=headers or {}).json()

    def get(url, headers=None):
        return cliente.get(urlparse(url).path, headers=headers or {}).json()
    return post, get


def test_mensaje_por_relay_con_licencia_y_latido(tmp_path):
    central = TestClient(app_central(Base(str(tmp_path / "c.sqlite")), admin_token="a" * 20))
    clave = central.post("/admin/licencias", json={"cliente": "Taller Ejemplo", "plan": "basico"}, headers=ADMIN).json()["clave"]

    d = tmp_path / "cliente"
    d.mkdir()
    shutil.copy(RAIZ / "raphael-harness" / "ejemplos" / "perfil-ropa-medida.yaml", d / "perfil.yaml")
    cpost, _ = puente(central)
    cfg = Config(dir=d, dev=str(RAIZ), tareas=False, central_url="http://central", licencia=clave,
                 relay_url="http://relay", relay_token="tok")
    r0 = Raphael(cfg, central_post=cpost)
    inst = r0.secretos.instalacion

    relay = TestClient(app_relay(Rutas([{"instalacion": inst, "token": "tok", "whatsapp_phone_ids": ["111"]}]),
                                 Cola(str(tmp_path / "r.sqlite")), app_secret="s", verify_token="v"))
    rpost, rget = puente(relay)
    r = Raphael(cfg, central_post=cpost, relay=ColaRelay("http://relay", "tok", get=rget, post=rpost))

    assert r.licencia.validar()["valida"] and r.licencia.activa
    p = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "111"},
         "messages": [{"from": "549", "type": "text", "text": {"body": "¿qué horario tienen?"}}]}}]}]}
    cuerpo = json.dumps(p).encode()
    firma = "sha256=" + hmac.new(b"s", cuerpo, hashlib.sha256).hexdigest()
    assert relay.post("/webhook/meta", content=cuerpo, headers={"Content-Type": "application/json",
                                                                   "X-Hub-Signature-256": firma}).json() == {"encolados": 1}
    r.traer_relay()
    assert "Atendemos" in r.harness.conversacion("whatsapp:549")[-1]["texto"]
    assert relay.get("/salud").json()["en_cola"] == 0

    r.enviar_latido()
    [x] = central.get("/admin/instalaciones", headers=ADMIN).json()
    assert x["instalacion"] == inst and x["uso"]["mensajes"] == 1 and x["alertas"] == []
