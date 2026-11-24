"""Catálogo de la Tienda: una interfaz única para cualquier plataforma (solo lectura en la v1).

`CatalogSource.fetch()` devuelve productos normalizados. Adaptadores: `feed` (JSON o CSV por URL, el de por defecto) y,
desde el 23 nov 2026, `tiendanube`, `shopify` y `woocommerce` (`platforms.py`), todos de solo lectura.
"""

from .base import CatalogError, CatalogSource, Product, normalize_products
from .feed import FeedSource, source_from
from .platforms import PLATFORMS, ShopifySource, TiendanubeSource, WooCommerceSource

__all__ = ["PLATFORMS", "CatalogError", "CatalogSource", "FeedSource", "Product", "ShopifySource", "TiendanubeSource",
           "WooCommerceSource", "normalize_products", "source_from"]
