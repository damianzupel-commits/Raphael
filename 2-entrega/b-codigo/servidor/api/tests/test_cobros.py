"""Mercado Pago y transferencia en el servidor de Empresas: variables nuevas, puentes de nombres y webhook."""

import time

import yaml
from test_configuracion import api  # noqa: F401  (fixture)
from test_entorno import INSTALACION

from raphael_empresas_api import puentes

CBU = "0000003100012345678901"


def esperar(cond, segundos=3.0):
    """El aviso se procesa en segundo plano (el servidor contesta antes): se espera a que pase."""
    fin = time.monotonic() + segundos
    while not cond() and time.monotonic() < fin:
        time.sleep(0.02)


def test_los_dos_nombres_de_mercado_pago_valen():
    env = {"MP_ACCESS_TOKEN": "APP_USR-1", "MERCADOPAGO_WEBHOOK_SECRET": "sec"}
    puentes.apply_aliases(env)
    assert env["MERCADOPAGO_ACCESS_TOKEN"] == "APP_USR-1" and env["MP_WEBHOOK_SECRET"] == "sec"
    env = {"MP_ACCESS_TOKEN": "uno", "MERCADOPAGO_ACCESS_TOKEN": "dos"}
    puentes.apply_aliases(env)
    assert env["MERCADOPAGO_ACCESS_TOKEN"] == "dos"          # el explícito no se pisa


def test_transferencia_y_mp_se_vuelcan_a_una_copia_de_la_instalacion(tmp_path):
    env = {"TRANSFER_TITULAR": "Marta López", "TRANSFER_ALIAS": "ana.taller", "TRANSFER_CBU_CVU": CBU, "MP_MODE": "mock",
           "RAPHAEL_PUBLIC_URL": "https://pc.tail1234.ts.net/"}
    out = puentes.efectiva(INSTALACION, tmp_path / "efectiva.yaml", env)
    pay = yaml.safe_load(out.read_text(encoding="utf-8"))["brigades"]["empresas"]["config"]["payments"]
    assert pay["holder"] == "Marta López" and pay["alias"] == "ana.taller" and pay["cbu"] == CBU
    assert pay["mercadopago"] == {"mode": "mock", "notification_url": "https://pc.tail1234.ts.net/webhook/mercadopago"}
    assert "Marta López" not in INSTALACION.read_text(encoding="utf-8")        # el original no se toca


def test_sin_variables_la_copia_queda_igual_en_cobros(tmp_path):
    out = puentes.efectiva(INSTALACION, tmp_path / "e.yaml", {})
    a = yaml.safe_load(out.read_text(encoding="utf-8"))["brigades"]["empresas"]["config"]["payments"]
    b = yaml.safe_load(INSTALACION.read_text(encoding="utf-8"))["brigades"]["empresas"]["config"]["payments"]
    assert a == b


def test_pantalla_acepta_las_variables_nuevas_y_valida(api):  # noqa: F811
    c, rt, meta, env_file, environ = api
    ok = c.put("/api/v1/config", json={"set": {"MP_ACCESS_TOKEN": "APP_USR-123456789", "MP_WEBHOOK_SECRET": "secreto123",
                                                 "TRANSFER_CBU_CVU": "0000003100012 345678901", "TRANSFER_TITULAR": "Ana",
                                                 "DUCKDNS_DOMAIN": "mitaller", "HCLOUD_TOKEN": "hc-abcdefghijkl"}})
    assert ok.status_code == 200, ok.text
    assert "APP_USR-123456789" not in ok.text and "hc-abcdefghijkl" not in ok.text
    assert environ["MERCADOPAGO_ACCESS_TOKEN"] == "APP_USR-123456789" and environ["TRANSFER_CBU_CVU"] == CBU
    assert set(ok.json()["restart_needed"]) >= {"MP_ACCESS_TOKEN", "TRANSFER_CBU_CVU"}
    c.put("/api/v1/config", json={"clear": ["MP_ACCESS_TOKEN"]})
    assert "MERCADOPAGO_ACCESS_TOKEN" not in environ
    for malo in ({"TRANSFER_CBU_CVU": "123"}, {"MP_MODE": "quizás"}, {"LOCAL_LLM_URL": "http://10.0.0.9:11434"}):
        assert c.put("/api/v1/config", json={"set": malo}).status_code == 400


def test_el_chequeo_habla_de_cobros(api):  # noqa: F811
    c, *_ = api
    c.put("/api/v1/config", json={"set": {"MP_ACCESS_TOKEN": "APP_USR-123456789"}})
    cobros = [i for i in c.get("/api/v1/config").json()["checks"] if i["area"] == "Cobros"]
    assert any(i["status"] == "aviso" and "MP_WEBHOOK_SECRET" in i["text"] for i in cobros)


def test_webhook_de_mercado_pago_se_pasa_a_la_brigada_sin_confirmar_nada(api):  # noqa: F811
    c, rt, *_ = api
    vistos = []

    async def command(brigade, cook, name, data=None, who=""):
        vistos.append((brigade, cook, name, data))
        return {"ok": True}

    rt.command = command
    c.headers.pop("Authorization")                       # sin sesión: lo firma Mercado Pago
    r = c.post("/webhook/mercadopago?data.id=123&type=payment", json={"type": "payment", "data": {"id": "123"}},
               headers={"x-signature": "ts=1,v1=abc", "x-request-id": "r1"})
    assert r.json() == {"received": 1}
    esperar(lambda: vistos)
    (brigade, cook, name, data), = vistos
    assert (brigade, cook, name) == ("empresas", "cobros", "mp_aviso") and data["payment_id"] == "123"
    assert data["headers"]["x-signature"] == "ts=1,v1=abc" and data["query"]["data.id"] == "123"


def test_webhook_ignora_lo_que_no_es_un_pago_o_viene_roto(api):  # noqa: F811
    c, rt, *_ = api
    assert c.post("/webhook/mercadopago?topic=merchant_order&id=5").json() == {"received": 0}
    assert c.post("/webhook/mercadopago?data.id=abc&type=payment").json() == {"received": 0}
    assert c.post("/webhook/mercadopago", content=b"no es json").json() == {"received": 0}


def test_webhook_que_falla_no_tumba_el_servidor_y_queda_auditado(api):  # noqa: F811
    c, rt, *_ = api
    c.post("/webhook/mercadopago?data.id=7&type=payment")        # la brigada de este árbol todavía no tiene `mp_aviso`
    time.sleep(0.3)
    assert c.get("/api/v1/health").status_code == 200
