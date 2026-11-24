"""Tienda: el catálogo de productos de la clienta, agnóstico a la plataforma. Solo lectura en la v1.

- `tick`: cada `store.refresh_minutes` lee el catálogo con su adaptador (`feed` JSON o CSV por URL, Tiendanube, Shopify o
  WooCommerce) y guarda una copia
  en los datos de la brigada (`products`, `catalog_state`). Si falla, sigue con la última copia buena y la Secretaria
  lo muestra como tarea ("el catálogo no se está actualizando"). Nunca tumba la brigada.
- Con clientes: contesta precio, stock y link de un producto SOLO con lo que está en la copia del catálogo. Si no lo
  encuentra, no contesta (lo toma Atención, que anota la duda). Nunca promete stock que no figura.
- No tiene acciones: no vende, no reserva, no cambia precios.
"""

from __future__ import annotations

import re

from raphael_core import ActionError, Cook, Reply
from raphael_core.text_es import money, normalize

from .. import config as C
from ..catalog import CatalogError, source_from
from ..signals import complaint

R_ASK = re.compile(r"\b(precio|precios|cuanto (sale|cuesta|esta|vale|salen|cuestan)|valor|stock|tenes|tienen|hay|queda|quedan|"
                   r"disponible|talle|talles|colores|vend(en|es)|catalogo|productos|tienda)\b")
R_CATALOG = re.compile(r"\b(catalogo|que (productos|cosas) (tenes|tienen|venden|vendes)|que venden|que vendes|tienda online|"
                       r"pagina web|link de la tienda)\b")
STOP = {"precio", "precios", "cuanto", "sale", "cuesta", "esta", "vale", "salen", "cuestan", "valor", "stock", "tenes", "tienen",
        "hay", "queda", "quedan", "disponible", "talle", "talles", "color", "colores", "venden", "vendes", "hola", "buenas",
        "quiero", "queria", "tengo", "para", "como", "cual", "cuales", "algun", "alguna", "alguno", "unos", "unas", "este",
        "esto", "esos", "esas", "todavia", "ahora", "porfa", "favor", "gracias", "catalogo", "productos", "tienda", "medida"}
MAX_SHOWN = 3


def _stem(w: str) -> str:
    return w[:-2] if w.endswith("es") and len(w) > 5 else w[:-1] if w.endswith("s") and len(w) > 4 else w


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", normalize(text)) if len(w) >= 3 and w not in STOP}


class Store(Cook):
    name = "tienda"
    version = "2.0.0"
    description = "Contesta precio, stock y link de los productos del catálogo de la tienda (solo lectura)."
    commands = {"productos": "Productos del catálogo ({'q': texto} para filtrar)",
                "catalogo": "Estado del catálogo: última actualización, cantidad de productos y error si lo hay",
                "sincronizar": "Vuelve a leer el catálogo ahora"}

    #: lo cambian los tests para no salir a internet: async (url) -> (código, texto) para el feed;
    #: async (método, url, headers, cuerpo) -> (código, headers, texto) para las plataformas; y de dónde salen los tokens
    fetcher = None
    http = None
    env = None

    # --- catálogo
    def _state(self, ctx) -> dict:
        return ctx.shared.get("catalog_state", "state") or {}

    async def sync(self, ctx) -> dict:
        cfg = C.of(ctx).store
        src = source_from(cfg, fetcher=self.fetcher, http=self.http, env=self.env)
        state = self._state(ctx)
        now = ctx.now().isoformat(timespec="seconds")
        if src is None:
            return state
        state["last_try"] = now
        try:
            products = await src.fetch()
        except CatalogError as exc:
            state["error"] = str(exc)[:200]
            ctx.shared.put("catalog_state", "state", state)
            ctx.record("catalogo_fallido", error=str(exc)[:200])
            return state
        keep = {p.id for p in products}
        for old in ctx.shared.list("products"):
            if old.get("id") not in keep:
                ctx.shared.delete("products", old["id"])
        for p in products:
            ctx.shared.put("products", p.id, p.to_dict())
        state.update(last_ok=now, error=None, count=len(products), source=src.kind)
        ctx.shared.put("catalog_state", "state", state)
        ctx.record("catalogo_actualizado", productos=len(products))
        return state

    async def tick(self, now, ctx):
        cfg = C.of(ctx).store
        if cfg.source.kind == "none":
            return
        last = self._state(ctx).get("last_try")
        if last:
            from datetime import datetime
            try:
                if (now - datetime.fromisoformat(last)).total_seconds() < cfg.refresh_minutes * 60:
                    return
            except ValueError:
                pass
        await self.sync(ctx)

    def search(self, text: str, ctx, limit: int = MAX_SHOWN) -> list[dict]:
        q = _words(text)
        if not q:
            return []
        scored = []
        for p in ctx.shared.list("products"):
            words = _words(f"{p.get('title', '')} {p.get('category', '')}")
            hits = len(q & words)
            if hits:
                scored.append((hits / len(q), -len(words), p))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        best = scored[0][0] if scored else 0
        return [p for s, _, p in scored if s == best][:limit]

    # --- clientes
    def _for_me(self, text: str) -> bool:
        t = normalize(text)
        return bool(R_ASK.search(t)) and not complaint(text) and "a medida" not in t

    def interest(self, msg, ctx):
        if C.of(ctx).store.source.kind == "none" or not self._for_me(msg.text):
            return 0.0
        if self.search(msg.text, ctx):
            return 0.65
        return 0.4 if R_CATALOG.search(normalize(msg.text)) and C.of(ctx).store.public_url else 0.0

    def handle(self, msg, ctx):
        cfg = C.of(ctx).store
        if cfg.source.kind == "none" or not self._for_me(msg.text):
            return None
        found = self.search(msg.text, ctx)
        if not found:
            if R_CATALOG.search(normalize(msg.text)) and cfg.public_url:
                return Reply(f"¡Mirá todo lo que tenemos acá! 🛍️ {cfg.public_url}")
            return None
        lines = [self._line(p) for p in found]
        head = "Te paso lo que tengo en el catálogo:" if len(found) > 1 else "Sí, mirá:"
        tail = "\n¿Te interesa alguno? 😊" if any((p.get("stock") or 0) > 0 or p.get("stock") is None for p in found) else ""
        return Reply(head + "\n" + "\n".join(lines) + tail)

    @staticmethod
    def _line(p: dict) -> str:
        price = f" — {money(p['price'])}" if p.get("price") else ""
        if p.get("currency") and p.get("currency") != "ARS" and p.get("price"):
            price = f" — {p['currency']} {p['price']:g}"
        stock = p.get("stock")
        avail = "" if stock is None else (" (sin stock por ahora)" if stock == 0 else
                                          " (queda 1)" if stock == 1 else f" ({stock} disponibles)")
        link = f"\n  {p['url']}" if p.get("url") else ""
        return f"• {p['title']}{price}{avail}{link}"

    # --- comandos
    async def command(self, name, data, ctx):
        if name == "productos":
            q = str(data.get("q") or "")
            return self.search(q, ctx, limit=50) if q else ctx.shared.list("products")
        if name == "catalogo":
            return {**self._state(ctx), "configured": C.of(ctx).store.source.kind != "none"}
        if name == "sincronizar":
            return await self.sync(ctx)
        raise ActionError(f"tienda no tiene el comando '{name}'")

    def execute(self, action, ctx):
        raise ActionError("la tienda solo lee el catálogo: no ejecuta acciones")
