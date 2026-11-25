"""Cobros online: la interfaz única de un proveedor de pagos y sus tipos.

Un proveedor sabe hacer tres cosas: crear un link de pago por una seña, leer un pago por su id y verificar que un aviso
(webhook) viene de verdad de él. Adaptadores: `mercadopago` (real) y `mock` (simulado, para pruebas y para andar sin
clave). Todo lo que devuelve el proveedor es dato de terceros: se valida y nunca se usa como instrucción.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class PayError(RuntimeError):
    """El proveedor no respondió bien. El mensaje es para la dueña, en castellano, y nunca lleva claves."""


@dataclass(frozen=True)
class PaymentLink:
    id: str
    url: str
    reference: str          # nuestra referencia (encargo): vuelve en el pago y sirve para saber de qué encargo es
    amount: float
    currency: str = "ARS"


@dataclass(frozen=True)
class PaymentInfo:
    id: str
    status: str             # approved | pending | rejected | cancelled | refunded | otro
    reference: str
    amount: float
    currency: str = "ARS"


class PaymentProvider(Protocol):
    kind: str

    async def create_link(self, reference: str, title: str, amount: float) -> PaymentLink: ...

    async def get_payment(self, payment_id: str) -> PaymentInfo: ...

    def verify_webhook(self, headers: dict, query: dict) -> bool: ...
