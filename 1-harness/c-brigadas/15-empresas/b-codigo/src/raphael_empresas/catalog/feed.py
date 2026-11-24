"""Adaptador `feed`: el catálogo en un JSON o un CSV publicado en una URL (el de por defecto).

JSON: una lista de productos, o un objeto con la lista en `products`, `items` o `data`. CSV: con encabezado.
Campos conocidos (o mapeados con `store.source.fields`): id, title, price, currency, stock, url, images, category,
description. La red se inyecta (`fetcher`) para probar sin salir a internet.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .base import CatalogError, Product, normalize_products

MAX_BYTES = 5_000_000
TIMEOUT = 20.0

#: (url) -> (código HTTP, texto)
Fetcher = Callable[[str], Awaitable[tuple[int, str]]]


async def http_fetch(url: str) -> tuple[int, str]:
    import httpx

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, headers={"Accept": "application/json, text/csv, */*"})
        if len(r.content) > MAX_BYTES:
            raise CatalogError(f"el catálogo pesa más de {MAX_BYTES // 1_000_000} MB")
        return r.status_code, r.text


def parse(text: str, fmt: str) -> list[Any]:
    if fmt == "csv":
        sample = text[:2000]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(io.StringIO(text), dialect=dialect))
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise CatalogError("el catálogo no es un JSON válido") from exc
    if isinstance(data, dict):
        data = next((data[k] for k in ("products", "items", "data", "productos") if isinstance(data.get(k), list)), None)
    if not isinstance(data, list):
        raise CatalogError("el JSON del catálogo no trae una lista de productos")
    return data


class FeedSource:
    kind = "feed"

    def __init__(self, url: str, fmt: str = "json", fields: dict[str, str] | None = None, *, limit: int = 2000,
                 fetcher: Fetcher | None = None) -> None:
        self.url, self.fmt, self.fields, self.limit = url, fmt, dict(fields or {}), limit
        self.fetcher = fetcher or http_fetch

    async def fetch(self) -> list[Product]:
        if not self.url:
            raise CatalogError("falta la URL del catálogo")
        try:
            status, text = await self.fetcher(self.url)
        except CatalogError:
            raise
        except Exception as exc:  # noqa: BLE001 - red, DNS, TLS: para la dueña es "no se pudo leer"
            raise CatalogError(f"no se pudo leer el catálogo ({type(exc).__name__})") from exc
        if status != 200:
            raise CatalogError(f"la tienda respondió {status}")
        if len(text) > MAX_BYTES:
            raise CatalogError(f"el catálogo pesa más de {MAX_BYTES // 1_000_000} MB")
        products = normalize_products(parse(text, self.fmt), self.fields, self.limit)
        if not products:
            raise CatalogError("el catálogo vino vacío o sin productos reconocibles (id y título)")
        return products


def source_from(store_cfg: Any, fetcher: Fetcher | None = None, http: Any = None, env: Any = None) -> Any:
    """El adaptador de la config de la tienda, o None si no hay catálogo configurado.
    `fetcher` es la red del feed; `http` la de las plataformas; `env` de dónde salen los tokens (por defecto, el entorno)."""
    src = store_cfg.source
    if src.kind == "feed" and src.url:
        return FeedSource(src.url, src.format, src.fields, limit=store_cfg.max_products, fetcher=fetcher)
    if src.kind in ("tiendanube", "shopify", "woocommerce"):
        from .platforms import PLATFORMS

        return PLATFORMS[src.kind](src, http=http, env=env, limit=store_cfg.max_products)
    return None
