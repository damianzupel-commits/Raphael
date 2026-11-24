"""Adaptadores de Tiendanube, Shopify y WooCommerce (solo lectura) con respuestas armadas según su documentación."""

import asyncio
import base64
import json

import pytest
from kit import System

from raphael_empresas.catalog import CatalogError, ShopifySource, TiendanubeSource, WooCommerceSource
from raphael_empresas.config import business_config


class Fake:
    """La tienda falsa: responde por orden y guarda cada pedido (método, url, headers, cuerpo)."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    async def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        r = self.responses.pop(0) if self.responses else (404, {}, "[]")
        if isinstance(r, Exception):
            raise r
        status, hdrs, data = r
        return status, hdrs, data if isinstance(data, str) else json.dumps(data)


def src(**s):
    return business_config({"store": {"source": s}}).store.source


def run(source):
    return asyncio.run(source.fetch())


# --- Tiendanube ----------------------------------------------------------------------------------------------------------
TN_PAGE1 = [{"id": 11, "name": {"es": "Vestido lino", "pt": "Vestido linho"}, "canonical_url": "https://t.example/v",
             "images": [{"src": "https://t.example/v.jpg"}], "categories": [{"name": {"es": "Vestidos"}}],
             "description": {"es": "<p>Lino <b>natural</b></p>"},
             "variants": [{"price": "45000.00", "promotional_price": None, "stock": 2}, {"price": "45000.00", "stock": 1}]},
            {"id": 12, "name": {"es": "Bolso"}, "variants": [{"price": "12000.00", "stock": None}]}]
TN_PAGE2 = [{"id": 13, "name": {"es": "Pañuelo"}, "variants": [{"price": "5000", "promotional_price": "4000", "stock": 0}]}]
TN_ENV = {"TIENDANUBE_TOKEN": "tok-tn"}


def test_tiendanube_lee_paginas_y_normaliza():
    fake = Fake((200, {"link": '<https://api.tiendanube.com/v1/123/products?page=2>; rel="next"'}, TN_PAGE1),
                (200, {}, TN_PAGE2))
    ps = {p.id: p for p in run(TiendanubeSource(src(kind="tiendanube", store_id="123", contact="ana@taller.example"),
                                                http=fake, env=TN_ENV))}
    method, url, headers, _ = fake.calls[0]
    assert method == "GET" and url.startswith("https://api.tiendanube.com/v1/123/products?published=true")
    assert headers["Authentication"] == "bearer tok-tn" and headers["User-Agent"] == "Raphael Empresas (ana@taller.example)"
    assert ps["11"].title == "Vestido lino" and ps["11"].stock == 3 and ps["11"].price == 45000.0
    assert ps["11"].category == "Vestidos" and "Lino" in ps["11"].description and "<" not in ps["11"].description
    assert ps["12"].stock is None                                   # stock infinito en Tiendanube = no se informa
    assert ps["13"].price == 4000.0 and ps["13"].stock == 0          # precio promocional
    assert len(fake.calls) == 2


def test_tiendanube_pide_lo_que_exige_la_api():
    with pytest.raises(CatalogError, match="store_id"):
        run(TiendanubeSource(src(kind="tiendanube", contact="x@y"), http=Fake(), env=TN_ENV))
    with pytest.raises(CatalogError, match="User-Agent"):
        run(TiendanubeSource(src(kind="tiendanube", store_id="1"), http=Fake(), env=TN_ENV))
    with pytest.raises(CatalogError, match="TIENDANUBE_TOKEN"):
        run(TiendanubeSource(src(kind="tiendanube", store_id="1", contact="x@y"), http=Fake(), env={}))
    with pytest.raises(CatalogError, match="credenciales"):
        run(TiendanubeSource(src(kind="tiendanube", store_id="1", contact="x@y"), http=Fake((401, {}, {})), env=TN_ENV))


# --- Shopify ------------------------------------------------------------------------------------------------------------
def shop_page(nodes, more=False, cursor=None):
    return 200, {}, {"data": {"products": {"pageInfo": {"hasNextPage": more, "endCursor": cursor}, "nodes": nodes}}}


SH1 = [{"id": "gid://shopify/Product/101", "title": "Blazer negro", "onlineStoreUrl": "https://s.example/blazer",
        "productType": "Sacos", "totalInventory": 4, "tracksInventory": True,
        "priceRangeV2": {"minVariantPrice": {"amount": "89000.0", "currencyCode": "ARS"}},
        "featuredMedia": {"preview": {"image": {"url": "https://cdn.example/b.jpg"}}}}]
SH2 = [{"id": "gid://shopify/Product/102", "title": "Gift card", "onlineStoreUrl": None, "productType": "",
        "totalInventory": 0, "tracksInventory": False,
        "priceRangeV2": {"minVariantPrice": {"amount": "10.0", "currencyCode": "USD"}}, "featuredMedia": None}]


def test_shopify_graphql_con_cursor():
    fake = Fake(shop_page(SH1, True, "c1"), shop_page(SH2))
    ps = {p.id: p for p in run(ShopifySource(src(kind="shopify", shop="mi-tienda.myshopify.com"), http=fake,
                                             env={"SHOPIFY_TOKEN": "shpat"}))}
    method, url, headers, body = fake.calls[0]
    assert method == "POST" and url == "https://mi-tienda.myshopify.com/admin/api/2026-07/graphql.json"
    assert headers["X-Shopify-Access-Token"] == "shpat" and "products(first: 100" in body["query"]
    assert fake.calls[1][3]["variables"] == {"cursor": "c1"}
    assert ps["101"].price == 89000.0 and ps["101"].stock == 4 and ps["101"].images == ("https://cdn.example/b.jpg",)
    assert ps["102"].stock is None and ps["102"].currency == "USD"   # no lleva inventario: no se informa stock


def test_shopify_errores():
    with pytest.raises(CatalogError, match="myshopify"):
        run(ShopifySource(src(kind="shopify", shop="https://evil.example"), http=Fake(), env={"SHOPIFY_TOKEN": "x"}))
    with pytest.raises(CatalogError, match="rechazó la consulta"):
        run(ShopifySource(src(kind="shopify", shop="t.myshopify.com"), http=Fake((200, {}, {"errors": [{"message": "x"}]})),
                          env={"SHOPIFY_TOKEN": "x"}))


# --- WooCommerce --------------------------------------------------------------------------------------------------------
WC1 = [{"id": 7, "name": "Pollera plisada", "price": "28000", "manage_stock": True, "stock_quantity": 1,
        "permalink": "https://w.example/p", "images": [{"src": "https://w.example/p.jpg"}],
        "categories": [{"name": "Polleras"}], "short_description": "<p>Plisada</p>"},
       {"id": 8, "name": "Top", "price": "9000", "manage_stock": False, "stock_status": "outofstock"}]
WC2 = [{"id": 9, "name": "Kimono", "price": "15000", "manage_stock": False, "stock_status": "instock"}]


def test_woocommerce_basic_auth_y_paginas():
    fake = Fake((200, {"x-wp-totalpages": "2"}, WC1), (200, {"x-wp-totalpages": "2"}, WC2))
    ps = {p.id: p for p in run(WooCommerceSource(src(kind="woocommerce", url="https://w.example"), http=fake,
                                                 env={"WOO_KEY": "ck_1", "WOO_SECRET": "cs_2"}))}
    method, url, headers, _ = fake.calls[0]
    assert url == "https://w.example/wp-json/wc/v3/products?status=publish&per_page=100&page=1"
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"ck_1:cs_2").decode()
    assert ps["7"].stock == 1 and ps["8"].stock == 0 and ps["9"].stock is None and len(fake.calls) == 2
    with pytest.raises(CatalogError, match="https"):
        run(WooCommerceSource(src(kind="woocommerce", url="http://w.example"), http=Fake(), env={"WOO_KEY": "a",
                                                                                            "WOO_SECRET": "b"}))


def test_los_tokens_no_van_en_la_config():
    with pytest.raises(Exception):  # noqa: B017 - pydantic: token_env tiene que ser un NOMBRE de variable
        business_config({"store": {"source": {"kind": "shopify", "token_env": "shpat_123secreto"}}})


def test_la_tienda_contesta_a_un_cliente_con_tiendanube():
    x = System({"store": {"source": {"kind": "tiendanube", "store_id": "123", "contact": "ana@taller.example"}}})
    x.cook("tienda").http = Fake((200, {}, TN_PAGE1))
    x.cook("tienda").env = TN_ENV
    x.tick()
    assert x.cmd("tienda", "catalogo")["source"] == "tiendanube"
    out = x.receive("¿cuánto sale el vestido de lino?")
    assert "Vestido lino" in out[0] and "$ 45.000" in out[0] and "3 disponibles" in out[0]


def test_sin_token_la_secretaria_avisa_que_el_catalogo_no_anda():
    x = System({"store": {"source": {"kind": "shopify", "shop": "t.myshopify.com"}}})
    x.cook("tienda").env = {}
    x.tick()
    t = next(t for t in x.say("tareas").tasks if t["kind"] == "catalogo_caido")
    assert "SHOPIFY_TOKEN" in t["reason"]
