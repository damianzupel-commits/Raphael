"""Emparejamiento PC<->celular por QR (Etapa 1, 2026-10-12, pedido de Damian).

El backend arma un payload con su API key + las URLs locales candidatas (LAN/hotspot/
Tailscale, nunca IP pública — ver network_info) y lo codifica en un QR. La app del celular
lo escanea y queda configurada sola: cero IPs ni tokens a mano ("instalá la app y sincronizá").

El QR revela la API key, así que SOLO se genera detrás de un endpoint autenticado
(/api/pairing con Bearer). Quien no tenga la key no puede sacarla escaneando la pantalla
de casualidad. El payload es JSON compacto:  {"v":1,"k":<apikey>,"u":[<url1>,<url2>,...]}.
"""

from __future__ import annotations

import base64
import io
import json

from .config import settings
from .network_info import network_candidates


# Token de emparejamiento pendiente, cacheado en memoria (token_id, token_en_claro).
# El store solo guarda el HASH, así que no se puede re-mostrar un token viejo; para no emitir
# uno nuevo cada vez que se abre el QR, reusamos el último mientras siga SIN usar (last_seen==0).
_pending: tuple[str, str] | None = None


def payload() -> dict:
    """Datos que viajan dentro del QR. Emite (o reusa) un token POR DISPOSITIVO, revocable,
    en vez de la API key maestra: cada celular pareado queda con su propio token."""
    global _pending
    from . import device_tokens

    reuse = False
    if _pending:
        tid, raw = _pending
        dev = next((d for d in device_tokens.list_devices() if d["token_id"] == tid), None)
        if dev and not dev.get("revoked") and not dev.get("last_seen"):
            reuse = True
    if reuse:
        token = _pending[1]  # type: ignore[index]
    else:
        tid, token = device_tokens.issue(label="Celular (QR)", scope="full")
        _pending = (tid, token)

    cands = network_candidates(settings.port)
    urls = [c["url"] for c in cands]  # ya ordenadas: directo (LAN/hotspot) primero, Tailscale al final
    return {"v": 1, "k": token, "u": urls}


def _qr_data_uri(data: str) -> str:
    """PNG del QR como data: URI, para embeber directo en el HTML sin otro request."""
    import qrcode  # dep liviana; Pillow (ya presente) hace el PNG

    img = qrcode.make(data, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def pairing_response() -> dict:
    """Lo que devuelve GET /api/pairing: las URLs (para mostrarlas) + el QR ya renderizado."""
    p = payload()
    data = json.dumps(p, separators=(",", ":"), ensure_ascii=False)
    return {"urls": p["u"], "qr": _qr_data_uri(data)}
