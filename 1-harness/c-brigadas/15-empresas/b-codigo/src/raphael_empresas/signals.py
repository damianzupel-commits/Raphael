"""Señales que usan varios cocineros de la brigada (una sola definición).

`complaint`: un reclamo o un pedido de hablar con una persona. En Empresas 0.4 lo miraba el orquestador para mandar el
mensaje primero a Atención; en el v2 Atención es el cocinero de red (va al final), así que los cocineros que tienen una
conversación abierta lo chequean antes y le pasan el mensaje a Atención (`ctx.consult`).
"""

from __future__ import annotations

import re

from raphael_core.text_es import normalize

R_COMPLAINT = re.compile(
    r"\b(reclamo|queja|me quejo|estafa|me estafaron|vino roto|llego (mal|roto|danado|fallado)|esta (roto|fallado|mal hecho)|"
    r"no (me )?(llego|respondieron|contestan)|devolucion|devuelvan|reembolso|"
    r"(quiero|necesito) hablar con (alguien|una persona|un humano|la duena|el duen\w+|vos)|me cobraron (de mas|mal))\b")

ATTENTION = "atencion"


def complaint(text: str) -> bool:
    return bool(R_COMPLAINT.search(normalize(text)))
