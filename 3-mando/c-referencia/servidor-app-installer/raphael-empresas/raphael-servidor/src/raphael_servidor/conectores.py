"""Canales de mensajes: WhatsApp Cloud API e Instagram (Meta Graph API).

Entrada: los webhooks de Meta (directo o a través del relay) se convierten en mensajes con `leer_meta`.
Salida: los conectores mandan las respuestas a la API de Meta. En modo mock no mandan nada.
Ventana de 24 h de WhatsApp: fuera de ella solo se pueden mandar plantillas aprobadas; los
avisos que fallan por eso quedan registrados para que la dueña los mande a mano.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Callable

from raphael_harness import Conector

log = logging.getLogger("raphael.conectores")
Transporte = Callable[[str, dict, dict], dict]


def verificar_firma(secreto: str, cuerpo: bytes, cabecera: str | None) -> bool:
    """X-Hub-Signature-256 de Meta."""
    if not secreto or not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecera[7:], esperada)


def leer_meta(payload: dict) -> list[dict]:
    """Webhook de Meta -> [{'canal', 'quien', 'texto', 'nombre', 'adjunto'}]. Ignora estados de entrega y ecos."""
    out: list[dict] = []
    objeto = payload.get("object")
    for entry in payload.get("entry", []) or []:
        if objeto == "whatsapp_business_account":
            for ch in entry.get("changes", []) or []:
                v = ch.get("value", {}) or {}
                nombres = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in v.get("contacts", []) or []}
                for m in v.get("messages", []) or []:
                    tipo = m.get("type")
                    texto = (m.get("text") or {}).get("body", "") if tipo == "text" else \
                        (m.get(tipo) or {}).get("caption", "") or f"[{tipo}]"
                    out.append({"canal": "whatsapp", "quien": m.get("from", ""), "texto": texto,
                                "nombre": nombres.get(m.get("from"), ""), "adjunto": tipo != "text"})
        elif objeto == "instagram":
            for ev in entry.get("messaging", []) or []:
                m = ev.get("message") or {}
                if not m or m.get("is_echo"):
                    continue
                adj = bool(m.get("attachments"))
                out.append({"canal": "instagram", "quien": (ev.get("sender") or {}).get("id", ""),
                            "texto": m.get("text") or ("[imagen]" if adj else ""), "nombre": "", "adjunto": adj})
    return [x for x in out if x["quien"]]


def _http(url: str, cuerpo: dict, headers: dict) -> dict:
    import httpx

    r = httpx.post(url, json=cuerpo, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


class _Meta(Conector):
    def __init__(self, token: str, graph: str, transporte: Transporte | None, al_fallar: Callable[[str, str, str], None]):
        self._token, self._graph = token, graph
        self._t = transporte or _http
        self._al_fallar = al_fallar

    def _post(self, url: str, cuerpo: dict, quien: str, texto: str) -> None:
        try:
            self._t(url, cuerpo, {"Authorization": f"Bearer {self._token}"})
        except Exception as e:  # noqa: BLE001 - un envío fallido no tumba el servidor
            log.warning("no se pudo enviar a %s: %s", quien, e)
            self._al_fallar(quien, texto, str(e))


class WhatsApp(_Meta):
    def __init__(self, token: str, phone_id: str, graph: str = "v21.0", transporte: Transporte | None = None,
                 al_fallar: Callable[[str, str, str], None] = lambda *a: None) -> None:
        super().__init__(token, graph, transporte, al_fallar)
        self._phone = phone_id

    def enviar(self, quien: str, texto: str) -> None:
        self._post(f"https://graph.facebook.com/{self._graph}/{self._phone}/messages",
                   {"messaging_product": "whatsapp", "to": quien, "type": "text", "text": {"body": texto[:4096]}}, quien, texto)


class Instagram(_Meta):
    def enviar(self, quien: str, texto: str) -> None:
        self._post(f"https://graph.facebook.com/{self._graph}/me/messages",
                   {"recipient": {"id": quien}, "message": {"text": texto[:1000]}}, quien, texto)
