"""Mercado Pago (Checkout Pro) para la seña de un encargo.

Flujo: `create_link` crea una preferencia (POST /checkout/preferences) y devuelve el link de pago (`init_point`); cuando
el cliente paga, Mercado Pago avisa por webhook con el id del pago; `get_payment` lo lee (GET /v1/payments/{id}) y de
ahí sale el estado y la referencia (`external_reference` = nuestro número de encargo).

Qué está verificado y qué no (25 nov 2026, contra la documentación pública):
  - Confirmado: GET https://api.mercadopago.com/v1/payments/{id} con `Authorization: Bearer <access token>`; la respuesta
    trae `status` ("approved", etc.), `currency_id` y `transaction_amount`. El aviso trae `type: payment` y `data.id`; el
    encabezado `x-signature` tiene la forma `ts=...,v1=...` y llega con `x-request-id`.
  - SUPUESTO sin confirmar (de memoria, no se pudo leer la página): el texto que se firma
    (`id:<data.id en minúscula>;request-id:<x-request-id>;ts:<ts>;`), HMAC-SHA256 en hexa con la "clave secreta" de la
    app, y los campos de la preferencia (`items[]` con title/quantity/unit_price/currency_id, `external_reference`,
    `notification_url`, `back_urls`, `expires`, `init_point`). Hay que probarlo con una cuenta de prueba antes de cobrar.
Nunca se loguea ni se devuelve el token. Nada de esto cobra solo: aprobar la seña lo decide siempre la dueña.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable

from .base import PayError, PaymentInfo, PaymentLink

API = "https://api.mercadopago.com"
TIMEOUT = 20.0
#: (método, url, headers, cuerpo json o None) -> (código, texto)
Http = Callable[[str, str, dict, dict | None], Awaitable[tuple[int, str]]]
KNOWN = {"approved", "pending", "in_process", "rejected", "cancelled", "refunded", "charged_back", "authorized"}


async def http_request(method: str, url: str, headers: dict, body: dict | None = None) -> tuple[int, str]:
    import httpx

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        r = await client.request(method, url, headers=headers, json=body)
        return r.status_code, r.text


class MercadoPago:
    kind = "mercadopago"

    def __init__(self, access_token: str, webhook_secret: str = "", *, notification_url: str = "", back_url: str = "",
                 expires_hours: int = 48, http: Http | None = None) -> None:
        if not access_token:
            raise PayError("falta el access token de Mercado Pago (MP_ACCESS_TOKEN)")
        self._token = access_token
        self._secret = webhook_secret
        self.notification_url = notification_url
        self.back_url = back_url
        self.expires_hours = expires_hours
        self._http = http or http_request

    def __repr__(self) -> str:            # que el token no salga ni por un log
        return "MercadoPago(token=***)"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    @staticmethod
    def _json(status: int, text: str):
        if status in (401, 403):
            raise PayError(f"Mercado Pago no aceptó las credenciales ({status}): revisá el access token")
        if status == 404:
            raise PayError("Mercado Pago no encontró ese pago")
        if status == 429:
            raise PayError("Mercado Pago pidió esperar (demasiados pedidos): reintentá en un rato")
        if status not in (200, 201):
            raise PayError(f"Mercado Pago respondió {status}")
        try:
            data = json.loads(text)
        except ValueError:
            raise PayError("Mercado Pago devolvió algo que no se entiende") from None
        if not isinstance(data, dict):
            raise PayError("Mercado Pago devolvió algo que no se entiende")
        return data

    async def create_link(self, reference: str, title: str, amount: float) -> PaymentLink:
        if amount <= 0:
            raise PayError("el monto tiene que ser mayor que cero")
        body: dict = {"items": [{"title": title[:120], "quantity": 1, "unit_price": float(amount), "currency_id": "ARS"}],
                      "external_reference": reference}
        if self.notification_url:
            body["notification_url"] = self.notification_url
        if self.back_url:
            body["back_urls"] = {"success": self.back_url, "pending": self.back_url, "failure": self.back_url}
        try:
            status, text = await self._http("POST", f"{API}/checkout/preferences", self._headers(), body)
        except PayError:
            raise
        except Exception:  # noqa: BLE001 - red caída, timeout, DNS
            raise PayError("no se pudo hablar con Mercado Pago (sin red o demorado)") from None
        data = self._json(status, text)
        url = str(data.get("init_point") or "")
        if not data.get("id") or not url.startswith("https://"):
            raise PayError("Mercado Pago no devolvió el link de pago")
        return PaymentLink(str(data["id"]), url, reference, float(amount))

    async def get_payment(self, payment_id: str) -> PaymentInfo:
        pid = str(payment_id).strip()
        if not pid.isdigit():
            raise PayError("el id del pago no es válido")
        try:
            status, text = await self._http("GET", f"{API}/v1/payments/{pid}", self._headers(), None)
        except PayError:
            raise
        except Exception:  # noqa: BLE001
            raise PayError("no se pudo hablar con Mercado Pago (sin red o demorado)") from None
        d = self._json(status, text)
        st = str(d.get("status") or "")
        try:
            amount = float(d.get("transaction_amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        return PaymentInfo(pid, st if st in KNOWN else "otro", str(d.get("external_reference") or "")[:80], amount,
                           str(d.get("currency_id") or "ARS"))

    def verify_webhook(self, headers: dict, query: dict) -> bool:
        """Firma del aviso. Sin clave secreta configurada NO se acepta nada (falla cerrado)."""
        if not self._secret:
            return False
        h = {str(k).lower(): str(v) for k, v in headers.items()}
        parts = dict(p.split("=", 1) for p in h.get("x-signature", "").split(",") if "=" in p)
        ts, v1 = parts.get("ts", "").strip(), parts.get("v1", "").strip()
        data_id = str(query.get("data.id") or query.get("data_id") or "")
        if not ts or not v1 or not data_id:
            return False
        manifest = f"id:{data_id.lower()};request-id:{h.get('x-request-id', '')};ts:{ts};"
        mine = hmac.new(self._secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(mine, v1)


def sign(secret: str, data_id: str, request_id: str, ts: str) -> str:
    """Arma un `x-signature` válido (para los tests y para probar el webhook a mano)."""
    m = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    return f"ts={ts},v1={hmac.new(secret.encode(), m.encode(), hashlib.sha256).hexdigest()}"
