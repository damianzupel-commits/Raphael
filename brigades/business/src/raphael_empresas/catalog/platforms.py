"""Adaptadores de plataformas de tienda (solo lectura): Tiendanube, Shopify y WooCommerce.

Fuentes revisadas el 23 nov 2026:
  - Tiendanube: GET https://api.tiendanube.com/v1/{store_id}/products con `Authentication: bearer <token>` (así, con ese
    nombre de encabezado) y un `User-Agent` con el nombre de la app y un contacto (sin él responde 400). Paginado con
    `page` y `per_page`; el encabezado `Link` trae rel="next". Nombres multilenguaje ({"es": ...}).
  - Shopify: Admin GraphQL API (la REST quedó como legada), POST https://{tienda}.myshopify.com/admin/api/{versión}/
    graphql.json con `X-Shopify-Access-Token`. Consulta `products` con cursor (pageInfo.hasNextPage / endCursor).
    Versión configurable (por defecto 2026-07; Shopify saca una por trimestre y mantiene cada una unos 12 meses).
  - WooCommerce: GET {sitio}/wp-json/wc/v3/products con HTTP Basic (consumer key y consumer secret) sobre HTTPS;
    `X-WP-TotalPages` dice cuántas páginas hay.
No se probaron contra tiendas reales (no hay credenciales): están probados con respuestas armadas según la documentación.

Los tokens NO van en la instalación: la config dice en qué variable de entorno están (`token_env`, `secret_env`), y en
el servidor viven en `datos/tienda.env`. Todo lo que devuelve la tienda es dato: pasa por `normalize_products`.
"""

from __future__ import annotations

import base64
import json
import os
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .base import CatalogError, Product, normalize_products

#: (método, url, headers, cuerpo json o None) -> (código, headers en minúscula, texto)
Http = Callable[[str, str, dict, dict | None], Awaitable[tuple[int, dict, str]]]

TIMEOUT = 25.0
MAX_PAGES = 100
SHOPIFY_VERSION = "2026-07"


async def http_request(method: str, url: str, headers: dict, body: dict | None = None) -> tuple[int, dict, str]:
    import httpx

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        r = await client.request(method, url, headers=headers, json=body)
        return r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.text


def _secret(env: Mapping[str, str], name: str, what: str) -> str:
    v = (env.get(name) or "").strip()
    if not v:
        raise CatalogError(f"falta {what}: poné la variable {name} en el servidor (datos/tienda.env)")
    return v


def _json(status: int, text: str, platform: str) -> Any:
    if status in (401, 403):
        raise CatalogError(f"{platform} no aceptó las credenciales ({status}): revisá el token")
    if status == 429:
        raise CatalogError(f"{platform} pidió esperar (demasiados pedidos): se reintenta en el próximo refresco")
    if status != 200:
        raise CatalogError(f"{platform} respondió {status}")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise CatalogError(f"{platform} devolvió algo que no es JSON") from exc


def _lang(v: Any) -> str:
    """Los textos multilenguaje de Tiendanube: {"es": ..., "pt": ...} -> el castellano o el primero."""
    if isinstance(v, dict):
        return str(v.get("es") or next((x for x in v.values() if x), "") or "")
    return str(v or "")


class _Base:
    kind = ""

    def __init__(self, cfg: Any, *, http: Http | None = None, env: Mapping[str, str] | None = None, limit: int = 2000) -> None:
        self.cfg, self.http, self.limit = cfg, http or http_request, limit
        self.env = os.environ if env is None else env

    async def fetch(self) -> list[Product]:
        try:
            rows = await self._rows()
        except CatalogError:
            raise
        except Exception as exc:  # noqa: BLE001 - red, DNS, TLS: para la dueña es "no se pudo leer"
            raise CatalogError(f"no se pudo leer la tienda ({type(exc).__name__})") from exc
        products = normalize_products(rows, limit=self.limit)
        if not products:
            raise CatalogError(f"{self.kind}: la tienda no devolvió productos publicados")
        return products

    async def _rows(self) -> list[dict]:  # pragma: no cover - lo implementa cada plataforma
        raise NotImplementedError


class TiendanubeSource(_Base):
    kind = "tiendanube"

    async def _rows(self) -> list[dict]:
        s = self.cfg
        if not re.fullmatch(r"\d{1,12}", s.store_id or ""):
            raise CatalogError("tiendanube: falta el número de tienda (store.source.store_id)")
        if not s.contact:
            raise CatalogError("tiendanube: falta un contacto para el User-Agent (store.source.contact), lo exige la API")
        token = _secret(self.env, s.token_env or "TIENDANUBE_TOKEN", "el token de Tiendanube")
        headers = {"Authentication": f"bearer {token}", "User-Agent": f"Raphael Empresas ({s.contact})",
                   "Accept": "application/json"}
        base = f"https://api.tiendanube.com/v1/{s.store_id}/products"
        out: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            status, hdrs, text = await self.http("GET", f"{base}?published=true&per_page=200&page={page}", headers, None)
            if status == 404 and page > 1:            # Tiendanube responde 404 cuando se pide una página que no existe
                break
            data = _json(status, text, "Tiendanube")
            if not isinstance(data, list):
                raise CatalogError("Tiendanube devolvió un formato inesperado")
            for p in data:
                variants = p.get("variants") or []
                stocks = [v.get("stock") for v in variants]
                price = next((v.get("promotional_price") or v.get("price") for v in variants
                              if v.get("promotional_price") or v.get("price")), None)
                out.append({"id": p.get("id"), "title": _lang(p.get("name")), "price": price,
                            "stock": None if (not stocks or any(x is None for x in stocks)) else sum(int(x) for x in stocks),
                            "url": p.get("canonical_url"), "images": [i.get("src") for i in p.get("images") or []],
                            "category": _lang((p.get("categories") or [{}])[0].get("name")),
                            "description": re.sub(r"<[^>]+>", " ", _lang(p.get("description")))})
            if len(out) >= self.limit or 'rel="next"' not in hdrs.get("link", ""):
                break
        return out


SHOPIFY_QUERY = """query Productos($cursor: String) {
  products(first: 100, after: $cursor, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title onlineStoreUrl productType totalInventory tracksInventory
      priceRangeV2 { minVariantPrice { amount currencyCode } }
      featuredMedia { preview { image { url } } }
    }
  }
}"""


class ShopifySource(_Base):
    kind = "shopify"

    async def _rows(self) -> list[dict]:
        s = self.cfg
        shop = (s.shop or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", shop):
            raise CatalogError("shopify: store.source.shop tiene que ser 'tu-tienda.myshopify.com'")
        token = _secret(self.env, s.token_env or "SHOPIFY_TOKEN", "el token de Shopify")
        url = f"https://{shop}/admin/api/{s.api_version or SHOPIFY_VERSION}/graphql.json"
        headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json", "Accept": "application/json"}
        out: list[dict] = []
        cursor = None
        for _ in range(MAX_PAGES):
            status, _h, text = await self.http("POST", url, headers, {"query": SHOPIFY_QUERY, "variables": {"cursor": cursor}})
            data = _json(status, text, "Shopify")
            if data.get("errors"):
                msg = data["errors"][0].get("message", "") if isinstance(data["errors"], list) else str(data["errors"])
                raise CatalogError(f"Shopify rechazó la consulta: {msg[:160]}")
            conn = ((data.get("data") or {}).get("products")) or {}
            for p in conn.get("nodes") or []:
                price = (((p.get("priceRangeV2") or {}).get("minVariantPrice")) or {})
                img = (((p.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url")
                out.append({"id": str(p.get("id", "")).rsplit("/", 1)[-1], "title": p.get("title"),
                            "price": price.get("amount"), "currency": price.get("currencyCode"),
                            "stock": p.get("totalInventory") if p.get("tracksInventory") else None,
                            "url": p.get("onlineStoreUrl"), "images": [img] if img else [], "category": p.get("productType")})
            info = conn.get("pageInfo") or {}
            if len(out) >= self.limit or not info.get("hasNextPage"):
                break
            cursor = info.get("endCursor")
        return out


class WooCommerceSource(_Base):
    kind = "woocommerce"

    async def _rows(self) -> list[dict]:
        s = self.cfg
        site = (s.url or "").rstrip("/")
        if not site.startswith("https://"):
            raise CatalogError("woocommerce: store.source.url tiene que ser la dirección https:// del sitio")
        key = _secret(self.env, s.token_env or "WOO_KEY", "la consumer key de WooCommerce")
        secret = _secret(self.env, s.secret_env or "WOO_SECRET", "el consumer secret de WooCommerce")
        auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
        out: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            status, hdrs, text = await self.http(
                "GET", f"{site}/wp-json/wc/v3/products?status=publish&per_page=100&page={page}", headers, None)
            data = _json(status, text, "WooCommerce")
            if not isinstance(data, list):
                raise CatalogError("WooCommerce devolvió un formato inesperado")
            for p in data:
                if p.get("manage_stock"):
                    stock = p.get("stock_quantity")
                else:
                    stock = 0 if p.get("stock_status") == "outofstock" else None
                out.append({"id": p.get("id"), "title": p.get("name"), "price": p.get("price"), "stock": stock,
                            "url": p.get("permalink"), "images": [i.get("src") for i in p.get("images") or []],
                            "category": ((p.get("categories") or [{}])[0]).get("name"),
                            "description": re.sub(r"<[^>]+>", " ", p.get("short_description") or "")})
            try:
                pages = int(hdrs.get("x-wp-totalpages", "1"))
            except ValueError:
                pages = 1
            if len(out) >= self.limit or page >= pages or not data:
                break
        return out


PLATFORMS = {"tiendanube": TiendanubeSource, "shopify": ShopifySource, "woocommerce": WooCommerceSource}
