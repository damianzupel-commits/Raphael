import hashlib
import hmac
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raphael_servidor.app import Raphael, crear_app
from raphael_servidor.config import Config
from raphael_servidor.conectores import leer_meta, verificar_firma
from raphael_servidor.servicios import ColaRelay, Licencia, hacer_backup, restaurar_backup

RAIZ = Path(__file__).resolve().parents[2]
PERFIL = RAIZ / "raphael-harness" / "ejemplos" / "perfil-ropa-medida.yaml"
pytestmark = pytest.mark.skipif(not PERFIL.exists(), reason="falta raphael-harness al lado")


def wa(texto, de="5493415550000", nombre="Cami", tipo="text"):
    m = {"from": de, "type": tipo}
    m["text" if tipo == "text" else tipo] = {"body": texto} if tipo == "text" else {"caption": texto}
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": de, "profile": {"name": nombre}}], "messages": [m]}}]}]}


@pytest.fixture
def cfg(tmp_path):
    shutil.copy(PERFIL, tmp_path / "perfil.yaml")
    return Config(dir=tmp_path, dev=str(RAIZ), tareas=False, meta_verify_token="vt", meta_app_secret="sec")


@pytest.fixture
def cliente(cfg):
    with TestClient(crear_app(cfg)) as c:
        tok = c.post("/api/primera-clave", json={"clave": "clave-segura"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


def test_clave_y_sesion(cfg):
    with TestClient(crear_app(cfg)) as c:
        assert c.get("/api/inicio").json() == {"negocio": "Taller Ejemplo", "tiene_clave": False}
        assert c.post("/api/primera-clave", json={"clave": "corta"}).status_code == 400
        assert c.post("/api/primera-clave", json={"clave": "clave-segura"}).status_code == 200
        assert c.post("/api/primera-clave", json={"clave": "otra-clave!"}).status_code == 409
        assert c.get("/api/resumen").status_code == 401
        assert c.post("/api/login", json={"clave": "mal"}).status_code == 401
        tok = c.post("/api/login", json={"clave": "clave-segura"}).json()["token"]
        assert c.get("/api/resumen", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_bloquea_tras_5_intentos(cfg):
    with TestClient(crear_app(cfg)) as c:
        c.post("/api/primera-clave", json={"clave": "clave-segura"})
        for _ in range(5):
            c.post("/api/login", json={"clave": "mal"})
        assert c.post("/api/login", json={"clave": "clave-segura"}).status_code == 401


def test_webhook_meta_de_punta_a_punta(cliente):
    assert cliente.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"}).text == "42"
    assert cliente.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "x"}).status_code == 403
    for t in ("quiero un vestido largo a medida para un casamiento", "el 20 de marzo", "verde", "no",
              "busto 90 cintura 70", "Camila"):
        assert cliente.post("/webhook/meta", json=wa(t)).json() == {"procesados": 1}
    [p] = cliente.get("/api/pendientes").json()
    assert p["accion"]["tipo"] == "enviar_presupuesto"
    assert cliente.post(f"/api/pendientes/{p['id']}/aprobar", json={"cambios": {"precio": 0}}).status_code == 400
    assert cliente.post(f"/api/pendientes/{p['id']}/aprobar", json={"cambios": {"precio": 190000}}).json()["estado"] == "ejecutada"
    conv = cliente.get("/api/conversacion", params={"contacto": "whatsapp:5493415550000"}).json()
    assert conv[-1]["de"] == "raphael" and "$ 190.000" in conv[-1]["texto"]
    assert cliente.get("/api/contactos").json()[0]["nombre"] == "Cami"
    e = cliente.post("/api/comando", json={"brigada": "encargos", "nombre": "listar", "datos": {}}).json()
    assert e[0]["precio"] == 190000


def test_firma_obligatoria_en_modo_real(cfg):
    cfg.modo = "real"
    with TestClient(crear_app(cfg)) as c:
        cuerpo = json.dumps(wa("hola")).encode()
        assert c.post("/webhook/meta", content=cuerpo, headers={"Content-Type": "application/json"}).status_code == 403
        firma = "sha256=" + hmac.new(b"sec", cuerpo, hashlib.sha256).hexdigest()
        r = c.post("/webhook/meta", content=cuerpo, headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
        assert r.json() == {"procesados": 1}


def test_envio_real_y_fallas_quedan_registradas(cfg):
    cfg.modo, cfg.whatsapp_token, cfg.whatsapp_phone_id = "real", "tok", "PHONE"
    enviados = []

    def transporte(url, cuerpo, headers):
        if "fallar" in cuerpo["text"]["body"]:
            raise RuntimeError("fuera de la ventana de 24 h")
        enviados.append((url, cuerpo["to"], headers["Authorization"]))
        return {}

    r = Raphael(cfg, transporte_meta=transporte)
    r.procesar_meta(wa("hola"))
    assert enviados[0] == ("https://graph.facebook.com/v21.0/PHONE/messages", "5493415550000", "Bearer tok")
    r.harness._enviar("whatsapp:1", "esto va a fallar")
    assert r._srv.listar("envios_fallidos")[0]["error"] == "fuera de la ventana de 24 h"


def test_probador_y_estado(cliente):
    r = cliente.post("/api/probar", json={"texto": "¿qué horario tienen?"}).json()
    assert "Atendemos" in r["respuestas"][0]
    e = cliente.get("/api/resumen").json()
    assert e["licencia"]["activa"] and set(e["brigadas"]) == {"atencion", "encargos", "cobros", "agenda", "avisos"}


def test_panel_web_se_sirve(cliente):
    assert "Raphael" in cliente.get("/panel/").text
    assert cliente.get("/panel/manifest.webmanifest").status_code == 200


def test_leer_meta_whatsapp_instagram_y_ecos():
    assert leer_meta(wa("hola"))[0] == {"canal": "whatsapp", "quien": "5493415550000", "texto": "hola", "nombre": "Cami", "adjunto": False}
    assert leer_meta(wa("mirá", tipo="image"))[0]["adjunto"] is True
    ig = {"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "IG1"}, "message": {"text": "hola"}},
                                                          {"sender": {"id": "YO"}, "message": {"text": "x", "is_echo": True}}]}]}
    assert leer_meta(ig) == [{"canal": "instagram", "quien": "IG1", "texto": "hola", "nombre": "", "adjunto": False}]
    assert leer_meta({"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{}]}}]}]}) == []
    assert not verificar_firma("s", b"x", None)


def test_licencia_gracia_y_vencimiento(tmp_path):
    ahora = [datetime(2026, 11, 18)]
    respuesta = {"valida": True, "plan": "pro", "vence": "2027-01-01"}

    def post(url, cuerpo, headers=None):
        if respuesta is None:
            raise ConnectionError("central caído")
        return respuesta

    lic = Licencia("http://central", "CLAVE", "inst", tmp_path / "l.json", "0.1.0", post=post, reloj=lambda: ahora[0])
    lic.validar()
    assert lic.activa
    respuesta = None                                  # el central no responde
    ahora[0] += timedelta(days=5)
    lic.validar()
    assert lic.activa                                 # dentro de la gracia
    ahora[0] += timedelta(days=3)
    assert not lic.activa                             # pasaron 8 días sin validar
    lic2 = Licencia("http://central", "C", "i", tmp_path / "x.json", "0.1.0",
                    post=lambda *a, **k: {"valida": True, "vence": "2026-11-01"}, reloj=lambda: datetime(2026, 11, 18))
    lic2.validar()
    assert not lic2.activa                            # vencida


def test_licencia_vencida_guarda_pero_no_responde(cfg):
    cfg.central_url = "http://central"
    r = Raphael(cfg, central_post=lambda *a, **k: {"valida": False, "motivo": "impaga"})
    r.licencia.validar()
    r.procesar_meta(wa("hola"))
    assert r.harness.conversacion("whatsapp:5493415550000") == [
        {**r.harness.conversacion("whatsapp:5493415550000")[0], "de": "cliente"}]


def test_relay_trae_y_confirma(cfg):
    pedidos = []

    class Falso(ColaRelay):
        def __init__(self):
            super().__init__("http://relay", "t", get=lambda url, h: {"items": [{"id": 7, "payload": wa("hola")}]},
                             post=lambda url, cuerpo, h: pedidos.append((url, cuerpo)))

    r = Raphael(cfg, relay=Falso())
    r.traer_relay()
    assert pedidos == [("http://relay/cola/ack", {"ids": [7]})]
    assert r.harness.contactos()[0]["contacto"] == "whatsapp:5493415550000"


def test_latido_sin_datos_de_clientes(cfg):
    enviados = []
    cfg.central_url = "http://central"
    r = Raphael(cfg, central_post=lambda url, cuerpo, headers=None: enviados.append((url, cuerpo)) or {"valida": True})
    r.procesar_meta(wa("Hola soy Camila Pérez"))
    r.enviar_latido()
    url, cuerpo = enviados[-1]
    assert url == "http://central/api/latido" and "Camila" not in json.dumps(cuerpo)


def test_backup_cifrado_y_restaurar(cfg, tmp_path):
    from cryptography.fernet import Fernet

    r = Raphael(cfg)
    r.procesar_meta(wa("hola"))
    clave = Fernet.generate_key().decode()
    copia = hacer_backup(cfg.base, cfg.backups, clave)
    assert copia.suffix == ".cifrado" and b"SQLite" not in copia.read_bytes()[:16]
    destino = tmp_path / "restaurada.sqlite"
    restaurar_backup(copia, destino, clave)
    assert destino.read_bytes()[:15] == b"SQLite format 3"
    for i in range(35):
        hacer_backup(cfg.base, cfg.backups, reloj=lambda i=i: datetime(2026, 1, 1) + timedelta(minutes=i))
    assert len(list(cfg.backups.glob("raphael-*"))) == 30


def test_env_ignora_comentarios_al_final_de_la_linea(tmp_path):
    from raphael_servidor.config import Config
    (tmp_path / ".env").write_text('RAPHAEL_MODO=real     # mock o real\nWHATSAPP_TOKEN="abc # no es comentario"\nRAPHAEL_FUENTE_REPOS=\n', encoding="utf-8")
    c = Config.desde_entorno(tmp_path)
    assert c.modo == "real" and c.whatsapp_token == "abc # no es comentario" and c.fuente_repos == ""


def test_el_panel_no_se_guarda_en_cache(cliente):
    assert cliente.get("/panel/").headers["cache-control"] == "no-cache"
