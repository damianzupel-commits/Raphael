"""Proveedores de cobro online (Mercado Pago real y simulado). La transferencia no es un proveedor: son datos de la
cuenta en la config y la confirmación la hace siempre la dueña."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .base import PayError, PaymentInfo, PaymentLink, PaymentProvider
from .mercadopago import MercadoPago, sign
from .mock import MockProvider

__all__ = ["MercadoPago", "MockProvider", "PayError", "PaymentInfo", "PaymentLink", "PaymentProvider", "provider_from", "sign"]


def provider_from(cfg, *, http=None, env: Mapping[str, str] | None = None, mock: MockProvider | None = None):
    """El proveedor que dice la config (`payments.mercadopago`), o None. Con `mode: real` y sin token devuelve None:
    el cocinero avisa que falta la clave y sigue solo con transferencia."""
    mp = cfg.mercadopago
    if mp.mode == "off":
        return None
    if mp.mode == "mock":
        return mock or MockProvider()
    e = os.environ if env is None else env
    token = (e.get(mp.token_env) or "").strip()
    if not token:
        return None
    return MercadoPago(token, (e.get(mp.secret_env) or "").strip(), notification_url=mp.notification_url,
                       back_url=mp.back_url, expires_hours=mp.expires_hours, http=http)
