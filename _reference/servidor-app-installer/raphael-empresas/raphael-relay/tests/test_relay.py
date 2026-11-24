import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from raphael_relay.app import Cola, Rutas, crear_app

INST = [{"instalacion": "taller", "token": "tok-taller", "whatsapp_phone_ids": ["111"], "instagram_ids": ["IG9"]},
        {"instalacion": "academia", "token": "tok-acad", "whatsapp_phone_ids": ["222"]}]


def cliente(tmp_path):
    return TestClient(crear_app(Rutas(INST), Cola(str(tmp_path / "r.sqlite")), app_secret="sec", verify_token="vt"))


def firmar(cuerpo: bytes) -> dict:
    return {"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=" + hmac.new(b"sec", cuerpo, hashlib.sha256).hexdigest()}


def wa(phone_id, texto="hola"):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone_id}, "messages": [{"from": "549", "type": "text", "text": {"body": texto}}]}}]}]}


def test_reparte_por_instalacion_y_cada_una_ve_solo_lo_suyo(tmp_path):
    c = cliente(tmp_path)
    for p in (wa("111"), wa("222"), wa("999")):
        cuerpo = json.dumps(p).encode()
        c.post("/webhook/meta", content=cuerpo, headers=firmar(cuerpo))
    items = c.get("/cola", headers={"Authorization": "Bearer tok-taller"}).json()["items"]
    assert len(items) == 1 and items[0]["payload"]["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] == "111"
    assert len(c.get("/cola", headers={"Authorization": "Bearer tok-acad"}).json()["items"]) == 1
    assert c.get("/cola", headers={"Authorization": "Bearer otro"}).status_code == 401


def test_ack_borra_y_no_vuelve(tmp_path):
    c = cliente(tmp_path)
    cuerpo = json.dumps(wa("111")).encode()
    c.post("/webhook/meta", content=cuerpo, headers=firmar(cuerpo))
    h = {"Authorization": "Bearer tok-taller"}
    ids = [i["id"] for i in c.get("/cola", headers=h).json()["items"]]
    assert c.post("/cola/ack", json={"ids": ids}, headers={"Authorization": "Bearer tok-acad"}).json() == {"borrados": 0}
    assert c.post("/cola/ack", json={"ids": ids}, headers=h).json() == {"borrados": 1}
    assert c.get("/cola", headers=h).json()["items"] == []


def test_firma_y_verificacion(tmp_path):
    c = cliente(tmp_path)
    assert c.post("/webhook/meta", json=wa("111")).status_code == 403
    assert c.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "7"}).text == "7"


def test_instagram_por_id_de_cuenta(tmp_path):
    ig = {"object": "instagram", "entry": [{"id": "IG9", "messaging": [{"sender": {"id": "u"}, "message": {"text": "hola"}}]}]}
    assert Rutas(INST).repartir(ig)[0][0] == "taller"
