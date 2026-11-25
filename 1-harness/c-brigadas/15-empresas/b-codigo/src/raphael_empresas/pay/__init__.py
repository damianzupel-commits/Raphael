"""Proveedores de cobro online (Mercado Pago real y simulado). La transferencia no es un proveedor: son datos de la
cuenta en la config y la confirmación la hace siempre la dueña."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .base import PayError, PaymentInfo, PaymentLink, PaymentProvider
from .mercadopago import MercadoPago, sign
from .mock import MockProvider

__all__ = ["MercadoPago", "MockProvider", "PayError", "PaymentInfo", "PaymentLink", "PaymentProvider", "provider_from", "sign"]


def _env(e: Mapping[str, str], name: str, legacy: str) -> str:
    """El nombre oficial (`MP_*`, el del catálogo de cuentas y el servidor) y, si no está, el alias viejo `MERCADOPAGO_*`."""
    return (e.get(name) or e.get(legacy) or "").strip()


def provider_from(cfg, *, http=None, env: Mapping[str, str] | None = None, mock: MockProvider | None = None):
    """El proveedor que dice la config (`payments.mercadopago`), o None. Con `mode: real` y sin token devuelve None:
    el cocinero avisa que falta la clave y sigue solo con transferencia."""
    mp = cfg.mercadopago
    if mp.mode == "off":
        return None
    if mp.mode == "mock":
        return mock or MockProvider()
    e = os.environ if env is None else env
    token = _env(e, mp.token_env, "MERCADOPAGO_ACCESS_TOKEN")
    if not token:
        return None
    return MercadoPago(token, _env(e, mp.secret_env, "MERCADOPAGO_WEBHOOK_SECRET"), notification_url=mp.notification_url,
                       back_url=mp.back_url, expires_hours=mp.expires_hours, http=http)
