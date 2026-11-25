"""Los pines del globo: puntos geolocalizados que la brigada junta (IPs, hosts de Shodan…) y el Centro de Mando dibuja.

Se guardan en el espacio de la brigada (colección `pines`, el más nuevo primero, con tope). Cada pin nuevo se publica
como evento `pin.agregado` para que el globo lo muestre en vivo (el harness decide quién lo escucha: la brigada no sabe
quién es).
"""

from __future__ import annotations

import uuid

from raphael_core import ActionError

from . import validar

COLECCION = "pines"
TOPE = 500


def tope(ctx) -> int:
    n = ctx.config.get("pines_max")
    return n if isinstance(n, int) and 10 <= n <= 5000 else TOPE


def agregar(ctx, lat, lon, etiqueta, tipo="ip", meta=None) -> dict | None:
    """Guarda un pin y lo publica. None si las coordenadas no sirven ((0, 0) o fuera de rango)."""
    c = validar.coordenadas(lat, lon)
    if c is None:
        return None
    pin = {"id": uuid.uuid4().hex[:12], "lat": c[0], "lon": c[1], "label": validar.limpiar(etiqueta) or "punto",
           "kind": tipo, "meta": meta or {}, "ts": ctx.now().isoformat(timespec="seconds"), "n": ctx.shared.next("pines")}
    ctx.shared.put(COLECCION, pin["id"], pin)
    sobran = listar(ctx, limite=10**6)[tope(ctx):]
    for viejo in sobran:
        ctx.shared.delete(COLECCION, viejo["id"])
    try:
        ctx.publish("pin.agregado", {k: pin[k] for k in ("id", "lat", "lon", "label", "kind")})
    except ActionError:
        pass   # el manifiesto no lo declara: el pin queda guardado igual
    return pin


def listar(ctx, tipo: str | None = None, limite: int = 100) -> list[dict]:
    pines = sorted(ctx.shared.list(COLECCION), key=lambda p: p.get("n", 0), reverse=True)
    if tipo:
        pines = [p for p in pines if p.get("kind") == tipo]
    return pines[: max(0, int(limite))]


def borrar(ctx, tipo: str | None = None) -> int:
    n = 0
    for p in listar(ctx, tipo, limite=10**6):
        n += ctx.shared.delete(COLECCION, p["id"])
    return n
