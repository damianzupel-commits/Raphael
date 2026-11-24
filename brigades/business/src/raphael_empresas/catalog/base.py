"""Lo común a todos los adaptadores de catálogo: el producto normalizado y la limpieza de lo que llega.

Todo lo que viene de la tienda es DATO de terceros: se recorta, se valida el tipo y nunca se usa como instrucción.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

MAX_TEXT = 200
MAX_IMAGES = 5


class CatalogError(RuntimeError):
    """El catálogo no se pudo leer (red, formato). El mensaje es para la dueña, en castellano."""


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    price: float | None = None
    currency: str = "ARS"
    stock: int | None = None          # None = la tienda no informa stock
    url: str = ""
    images: tuple[str, ...] = field(default_factory=tuple)
    category: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["images"] = list(self.images)
        return d


class CatalogSource(Protocol):
    """Un adaptador de catálogo. `fetch` puede tardar (red): lo llama el cocinero en su tick, nunca en un mensaje."""

    kind: str

    async def fetch(self) -> list[Product]: ...


def _text(v: Any, n: int = MAX_TEXT) -> str:
    return " ".join(str(v if v is not None else "").split())[:n]


def _url(v: Any) -> str:
    s = _text(v, 500)
    return s if s.startswith(("https://", "http://")) else ""


def _price(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v >= 0 else None
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if "," in s and "." in s:                      # 12.500,50 -> 12500.50
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) <= 2 else s.replace(",", "")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[-1]) == 3):
        s = s.replace(".", "")                     # 12.500 -> 12500
    try:
        f = float(s)
    except ValueError:
        return None
    return f if f >= 0 else None


def _stock(v: Any) -> int | None:
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        n = int(float(str(v).strip()))
    except ValueError:
        return None
    return max(0, n)


def _images(v: Any) -> tuple[str, ...]:
    items = v if isinstance(v, list) else re.split(r"[|\s,]+", str(v or ""))
    out = []
    for i in items:
        u = _url(i.get("src") or i.get("url") if isinstance(i, dict) else i)
        if u:
            out.append(u)
    return tuple(out[:MAX_IMAGES])


FIELDS = ("id", "title", "price", "currency", "stock", "url", "images", "category", "description")
ALIASES = {"id": ("id", "sku", "codigo", "code"), "title": ("title", "name", "nombre", "titulo"),
           "price": ("price", "precio"), "currency": ("currency", "moneda"), "stock": ("stock", "cantidad", "quantity"),
           "url": ("url", "link", "permalink"), "images": ("images", "image", "imagen", "imagenes", "image_url"),
           "category": ("category", "categoria"), "description": ("description", "descripcion")}


def normalize_products(rows: list[Any], fields: dict[str, str] | None = None, limit: int = 2000) -> list[Product]:
    """Filas crudas (dicts) -> productos. Se descartan las que no tienen id o título. `fields` mapea campo nuestro ->
    campo del feed cuando no se llaman como los conocidos."""
    fields = fields or {}
    out: list[Product] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        low = {str(k).strip().lower(): v for k, v in row.items()}

        def pick(name: str, low: dict = low) -> Any:
            if name in fields:
                return low.get(fields[name].lower())
            return next((low[a] for a in ALIASES[name] if a in low), None)

        pid, title = _text(pick("id"), 80), _text(pick("title"))
        if not pid or not title or pid in seen:
            continue
        seen.add(pid)
        out.append(Product(id=pid, title=title, price=_price(pick("price")), currency=_text(pick("currency"), 8) or "ARS",
                           stock=_stock(pick("stock")), url=_url(pick("url")), images=_images(pick("images")),
                           category=_text(pick("category"), 80), description=_text(pick("description"), 400)))
        if len(out) >= limit:
            break
    return out
