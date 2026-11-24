"""Canal de Meta (WhatsApp e Instagram) sobre la instalación real, con la Graph API falsa (sin red)."""

import hashlib
import hmac
import json
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from test_api import runtime

from raphael_empresas_api.app import create_app
from raphael_empresas_api.meta import MetaChannel, MetaSettings, parse_webhook, settings_from_env, split_text, verify_signature

SECRET = "secreto-de-la-app"
REAL = MetaSettings(mode="real", verify_token="vt-123", app_secret=SECRET, wa_token="tok-wa", wa_phone_id="1065",
                    ig_token="tok-ig")


def wa(text, frm="5493415550000", mid="wamid.1", name="Cami", kind="text"):
    msg = {"from": frm, "id": mid, "type": kind}
    msg.update({"text": {"body": text}} if kind == "text" else {kind: {"caption": text}})
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "contacts": [{"wa_id": frm, "profile": {"name": name}}], "messages": [msg]}}]}]}


def ig(text, sender="1789", mid="m_1", echo=False):
    return {"object": "instagram", "entry": [{"messaging": [{"sender": {"id": sender}, "recipient": {"id": "999"},
                                                             "message": {"mid": mid, "text": text, "is_echo": echo}}]}]}


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


class Graph:
    """La Graph API falsa: guarda lo que llega; `fail` hace que responda error."""

    def __init__(self):
        self.calls, self.fail = [], None

    def __call__(self, url, body, headers):
        if self.fail:
            raise RuntimeError(self.fail)
        self.calls.append((url, body, headers))
        return {"messages": [{"id": "wamid.out"}]}


@pytest.fixture
def server():
    rt_holder = {}
    graph = Graph()
    channel = MetaChannel.build(REAL, graph, threaded=False)
    rt = runtime(connectors=channel.connectors())
    channel.bind(rt)
    rt_holder["rt"] = rt
    app = create_app(rt, tick=False, meta=channel)
    app.state.auth.set_key("clave-segura")
    with TestClient(app) as c:
        yield c, rt, graph, channel


def post(c, payload, signed=True):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **({"X-Hub-Signature-256": sign(body)} if signed else {})}
    return c.post("/webhook/meta", content=body, headers=headers)


def until(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_configuracion_desde_el_entorno_sin_mostrar_valores():
    s = settings_from_env({"META_MODE": "real", "META_WA_TOKEN": "x", "META_WA_PHONE_ID": "1"})
    assert s.real and s.graph_version == "v26.0" and s.ig_host == "graph.instagram.com"
    assert "falta META_APP_SECRET" in s.problems()[0] and "x" not in " ".join(s.problems())
    assert settings_from_env({}).mode == "mock" and settings_from_env({}).problems() == []


def test_firma_de_meta():
    body = b'{"a":1}'
    assert verify_signature(SECRET, body, sign(body))
    assert not verify_signature(SECRET, body, "sha256=" + "0" * 64)
    assert not verify_signature("", body, sign(body)) and not verify_signature(SECRET, body, None)


def test_lectura_de_webhooks():
    [m] = parse_webhook(wa("hola"))
    assert (m.channel, m.sender, m.text, m.name, m.attachment, m.mid) == ("whatsapp", "5493415550000", "hola", "Cami", False,
                                                                          "wamid.1")
    [foto] = parse_webhook(wa("mi vestido", kind="image"))
    assert foto.attachment and foto.text == "mi vestido"
    status = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{"id": "x"}]}}]}]}
    assert parse_webhook(status) == []
    assert parse_webhook(ig("hola", echo=True)) == []                 # lo que mandamos nosotros vuelve como eco
    assert parse_webhook(ig("hola"))[0].sender == "1789"


def test_partir_mensajes_largos():
    assert split_text("hola") == ["hola"]
    long = ("palabra " * 1200).strip()
    parts = split_text(long, 4096)
    assert len(parts) == 3 and all(len(p) <= 4096 for p in parts) and " ".join(parts) == long
    emojis = "🧵" * 400                                                 # 4 bytes cada uno: 1600 bytes
    assert all(len(p.encode()) <= 1000 for p in split_text(emojis, 4096, 1000))


def test_verificacion_del_webhook(server):
    c, *_ = server
    ok = c.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "vt-123", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    assert c.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "1"}
                 ).status_code == 403


def test_sin_firma_o_con_firma_mala_no_entra(server):
    c, rt, graph, _ = server
    assert post(c, wa("hola"), signed=False).status_code == 403
    body = json.dumps(wa("hola")).encode()
    assert c.post("/webhook/meta", content=body, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64}).status_code == 403
    assert rt.contacts() == []


def test_mensaje_de_whatsapp_entra_y_la_respuesta_sale_por_la_graph_api(server):
    c, rt, graph, _ = server
    assert post(c, wa("¿qué horario tienen?")).json() == {"received": 1}
    assert until(lambda: graph.calls)
    url, body, headers = graph.calls[0]
    assert url == "https://graph.facebook.com/v26.0/1065/messages" and headers["Authorization"] == "Bearer tok-wa"
    assert body["to"] == "5493415550000" and body["messaging_product"] == "whatsapp" and "10 a 19" in body["text"]["body"]
    assert rt.contacts()[0]["name"] == "Cami"


def test_instagram_responde_por_graph_instagram(server):
    c, rt, graph, _ = server
    post(c, ig("hola"))
    assert until(lambda: graph.calls)
    url, body, headers = graph.calls[0]
    assert url == "https://graph.instagram.com/v26.0/me/messages" and body["recipient"] == {"id": "1789"}
    assert headers["Authorization"] == "Bearer tok-ig" and "Taller Ejemplo" in body["message"]["text"]


def test_meta_reintenta_y_no_se_procesa_dos_veces(server):
    c, rt, graph, _ = server
    post(c, wa("hola", mid="wamid.X"))
    assert until(lambda: len(graph.calls) == 1)
    assert post(c, wa("hola", mid="wamid.X")).json() == {"received": 0}
    time.sleep(0.2)
    assert len(graph.calls) == 1 and rt.contacts()[0]["messages"] == 1


def test_fuera_de_las_24_horas_no_se_manda_y_se_le_avisa_a_la_duena(server):
    c, rt, graph, _ = server
    post(c, wa("quiero un vestido a medida"))
    assert until(lambda: graph.calls)
    post(c, wa("Lu", mid="wamid.2"))
    assert until(lambda: rt.approvals.list())
    rt.clock.now += timedelta(hours=30)                                     # la dueña aprueba al otro día
    graph.calls.clear()
    tok = c.post("/api/v1/login", json={"key": "clave-segura"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.get("/api/v1/pending", headers=h).json()["items"][0]["id"]
    assert c.post(f"/api/v1/pending/{pid}/approve", json={}, headers=h).json()["state"] == "executed"
    assert graph.calls == []                                                # no salió nada
    ch = c.get("/api/v1/channels", headers=h).json()
    assert ch["mode"] == "real" and ch["channels"] == ["instagram", "whatsapp"]
    [n] = [x for x in rt.notices() if x["data"].get("kind") == "envio_fallido"]
    assert "24 h" in n["text"] and "whatsapp:5493415550000" in n["text"]


def test_si_meta_rechaza_el_envio_queda_el_aviso(server):
    c, rt, graph, _ = server
    graph.fail = "Meta respondió 401: token vencido"
    post(c, wa("hola"))
    assert until(lambda: any("token vencido" in n["text"] for n in rt.notices()))


def test_en_modo_mock_no_sale_nada_a_internet():
    channel = MetaChannel.build(MetaSettings(), threaded=False)
    rt = runtime(connectors=channel.connectors())
    channel.bind(rt)
    with TestClient(create_app(rt, tick=False, meta=channel)) as c:
        assert c.post("/webhook/meta", json=wa("hola")).json() == {"received": 1}       # sin secreto, mock acepta sin firma
        assert until(lambda: channel.outbox.sent)
        assert channel.outbox.sent[0][1]["to"] == "5493415550000"
