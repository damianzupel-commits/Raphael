"""Proveedor simulado: sin red y sin clave. Lo usan los tests y el modo `mock` de la config (para probar el circuito
completo sin cuenta de Mercado Pago). Los links son de mentira (`https://pago.simulado.invalid/...`)."""

from __future__ import annotations

from .base import PayError, PaymentInfo, PaymentLink


class MockProvider:
    kind = "mock"

    def __init__(self) -> None:
        self.payments: dict[str, PaymentInfo] = {}
        self.links: list[PaymentLink] = []
        self.webhook_ok = True

    async def create_link(self, reference: str, title: str, amount: float) -> PaymentLink:
        if amount <= 0:
            raise PayError("el monto tiene que ser mayor que cero")
        link = PaymentLink(f"mock-pref-{len(self.links) + 1}", f"https://pago.simulado.invalid/{reference}", reference,
                           float(amount))
        self.links.append(link)
        return link

    def pay(self, payment_id: str, reference: str, amount: float, status: str = "approved") -> None:
        """Atajo de los tests: deja registrado un pago como si el cliente hubiera pagado."""
        self.payments[payment_id] = PaymentInfo(payment_id, status, reference, float(amount))

    async def get_payment(self, payment_id: str) -> PaymentInfo:
        if payment_id not in self.payments:
            raise PayError("Mercado Pago (simulado) no conoce ese pago")
        return self.payments[payment_id]

    def verify_webhook(self, headers: dict, query: dict) -> bool:
        return self.webhook_ok
