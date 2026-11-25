"""Cobros online: Mercado Pago (simulado y real contra un transporte armado) y transferencia con datos de la cuenta.
Nada sale a internet y no hay claves reales: el token de estos tests es de mentira."""

import asyncio
import json

from kit import System

from raphael_empresas.pay import MercadoPago, MockProvider, PayError, provider_from, sign

QUOTE = {"number": 7, "contact": "whatsapp:1", "client": "Lu", "price": 200000, "deposit": 100000, "description": "vestido"}
MP = {"payments": {"deposit_pct": 50, "alias": "taller.ejemplo", "holder": "Ana Pérez",
                   "mercadopago": {"mode": "mock", "notification_url": "https://x.example/webhook/mercadopago"}}}


def run(coro):
    return asyncio.run(coro)


def armed(mode="mock", **kw):
    x = System({"payments": {"deposit_pct": 50, "alias": "a.b", "mercadopago": {"mode": mode, **kw}}})
    return x


def quote(x):
    x.publish("encargo.presupuesto_enviado", dict(QUOTE))
    x.rt.run(asyncio.sleep(0))       # deja correr el manejador async del evento


# --- transferencia
def test_transferencia_con_cbu_y_banco_en_el_presupuesto():
    cfg = {"payments": {"deposit_pct": 50, "alias": "", "cbu": "0" * 22, "holder": "Ana Pérez", "bank": "Banco X"}}
    x = System(cfg)
    o = x.cook("encargos")._quote_message({"client": "Lu", "description": "vestido", "number": 1, "price": 200000,
                                           "deposit": 100000}, x.ctx("encargos"))
    assert "0" * 22 in o and "Banco X" in o and "Ana Pérez" in o


def test_sin_mercadopago_no_se_ofrece_link():
    x = System()
    quote(x)
    assert x.pending() == [] and x.cmd("cobros", "mp_estado")["mode"] == "off"


# --- mercado pago simulado
def test_link_de_pago_pasa_por_la_duena_antes_de_llegar_al_cliente():
    x = System(MP)
    quote(x)
    [p] = x.pending()
    assert p["action"]["type"] == "enviar_link_pago" and p["level"] == "aprobacion"
    assert "pago.simulado.invalid/7" in p["action"]["data"]["url"]
    x.approve(p["id"])
    assert any("pago.simulado.invalid/7" in t and "Mercado Pago" in t for t in x.out("whatsapp:1"))


def test_pago_acreditado_deja_la_confirmacion_a_la_duena_y_no_duplica():
    x = System(MP)
    quote(x)
    x.approve(x.pending()[0]["id"])
    mp = x.cook("cobros")._mock
    mp.pay("555", "7", 100000)
    r = x.cmd("cobros", "mp_aviso", {"payment_id": "555"})
    assert r["ok"] and "confirme" in r["motivo"]
    [p] = x.pending()
    assert p["action"]["type"] == "confirmar_pago" and "Mercado Pago acreditó" in p["summary"]
    assert x.cmd("cobros", "mp_aviso", {"payment_id": "555"})["motivo"] == "ya estaba registrado"
    assert len(x.pending()) == 1 and x.events("pago.confirmado") == []        # nada se confirma solo
    x.approve(p["id"])
    [(_, d)] = x.events("pago.confirmado")
    assert d["number"] == 7 and d["amount"] == 100000.0


def test_monto_menor_a_la_sena_o_pago_pendiente_no_confirman():
    x = System(MP)
    quote(x)
    x.approve(x.pending()[0]["id"])
    mp = x.cook("cobros")._mock
    mp.pay("1", "7", 5000)
    assert not x.cmd("cobros", "mp_aviso", {"payment_id": "1"})["ok"]
    mp.pay("2", "7", 100000, status="pending")
    assert x.cmd("cobros", "mp_aviso", {"payment_id": "2"})["estado"] == "pending"
    mp.pay("3", "999", 100000)
    assert "ningún encargo" in x.cmd("cobros", "mp_aviso", {"payment_id": "3"})["motivo"]
    assert x.pending() == []


def test_firma_invalida_se_descarta():
    x = System(MP)
    quote(x)
    x.cook("cobros")._mock.webhook_ok = False
    assert x.cmd("cobros", "mp_aviso", {"payment_id": "1"})["motivo"] == "firma inválida"


def test_si_la_duena_rechaza_el_pago_de_mp_vuelve_a_esperar():
    x = System(MP)
    quote(x)
    x.approve(x.pending()[0]["id"])
    x.cook("cobros")._mock.pay("9", "7", 100000)
    x.cmd("cobros", "mp_aviso", {"payment_id": "9"})
    x.reject(x.pending()[0]["id"], "no me llegó")
    assert x.cmd("cobros", "esperando")[0]["number"] == 7


# --- modo real sin clave / con transporte armado
def test_modo_real_sin_clave_cae_a_transferencia_y_lo_avisa():
    x = armed("real")
    x.cook("cobros").env = {}
    quote(x)
    assert x.pending() == []
    st = x.cmd("cobros", "mp_estado")
    assert st["mode"] == "real" and st["con_clave"] is False and "MERCADOPAGO_ACCESS_TOKEN" in st["error"]


def test_adaptador_real_crea_preferencia_y_lee_pago():
    seen = []

    async def http(method, url, headers, body):
        seen.append((method, url, headers, body))
        if method == "POST":
            return 201, json.dumps({"id": "pref-1", "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref-1"})
        return 200, json.dumps({"id": 123, "status": "approved", "external_reference": "7", "transaction_amount": 100000,
                                "currency_id": "ARS"})

    mp = MercadoPago("TEST-token", "sec", notification_url="https://x.example/hook", http=http)
    link = run(mp.create_link("7", "Seña", 100000))
    assert link.url.startswith("https://www.mercadopago.com.ar/") and link.reference == "7"
    method, url, headers, body = seen[0]
    assert url.endswith("/checkout/preferences") and headers["Authorization"] == "Bearer TEST-token"
    assert body["external_reference"] == "7" and body["items"][0]["unit_price"] == 100000.0
    assert body["notification_url"] == "https://x.example/hook"
    pay = run(mp.get_payment("123"))
    assert (pay.status, pay.reference, pay.amount) == ("approved", "7", 100000.0)
    assert "TEST-token" not in repr(mp)


def test_adaptador_real_errores_en_castellano_y_sin_filtrar_el_token():
    async def http401(*a):
        return 401, "{}"

    async def boom(*a):
        raise OSError("TEST-token reventó")

    mp = MercadoPago("TEST-token", http=http401)
    try:
        run(mp.get_payment("1"))
        raise AssertionError
    except PayError as e:
        assert "credenciales" in str(e)
    mp = MercadoPago("TEST-token", http=boom)
    try:
        run(mp.create_link("7", "x", 10))
        raise AssertionError
    except PayError as e:
        assert "TEST-token" not in str(e)
    try:
        MercadoPago("")
        raise AssertionError
    except PayError:
        pass


def test_firma_del_webhook_correcta_incorrecta_y_cerrada_sin_secreto():
    mp = MercadoPago("t", "sec")
    h = {"x-signature": sign("sec", "ABC123", "req-1", "1700000000"), "x-request-id": "req-1"}
    assert mp.verify_webhook(h, {"data.id": "ABC123"})
    assert not mp.verify_webhook(h, {"data.id": "OTRO"})
    assert not mp.verify_webhook({**h, "x-request-id": "otro"}, {"data.id": "ABC123"})
    assert not MercadoPago("t", "").verify_webhook(h, {"data.id": "ABC123"})
    assert not mp.verify_webhook({}, {})


def test_provider_from_respeta_el_modo():
    from raphael_empresas.config import business_config
    p = lambda mode: business_config({"payments": {"mercadopago": {"mode": mode}}}).payments  # noqa: E731
    assert provider_from(p("off")) is None
    assert isinstance(provider_from(p("mock")), MockProvider)
    assert provider_from(p("real"), env={}) is None
    assert isinstance(provider_from(p("real"), env={"MERCADOPAGO_ACCESS_TOKEN": "t"}), MercadoPago)
