"""Rastreo de direcciones cripto: balance y actividad de una dirección BTC o ETH en explorers públicos.

Solo datos públicos de la blockchain (blockchain.info para BTC, blockchair para ETH). No desanonimiza a nadie.
Portado de `crypto_address_trace` de JarvisRemote.
"""

from __future__ import annotations

import re

from raphael_core import Message, Reply
from raphael_core.text_es import normalize

from .. import validar
from .comun import CocineroGeo

CANDIDATA = re.compile(r"\b(0x[0-9a-fA-F]{40}|bc1[0-9a-z]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")


def direccion_en(texto: str) -> str | None:
    m = CANDIDATA.search(texto or "")
    return m.group(1) if m else None


def linea(r: dict) -> str:
    nota = " (DATOS DE MUESTRA, modo simulado)" if r.get("simulado") else ""
    if not r.get("ok"):
        return f"{r.get('aviso')} Fuente: {r.get('fuente')}."
    u = "eth" if r["cadena"] == "ethereum" else "btc"
    return (f"{r['cadena'].capitalize()} {r['direccion'][:10]}…: balance {r[f'balance_{u}']} {u.upper()}, recibido "
            f"{r[f'recibido_{u}']}, enviado {r[f'enviado_{u}']}, {r.get('transacciones')} transacciones. "
            f"Fuente: {r['fuente']} (blockchain pública).{nota}")


class Cripto(CocineroGeo):
    name = "cripto"
    description = "Traza direcciones de Bitcoin y Ethereum con datos públicos de la blockchain."
    commands = {"cripto": "rastrea una dirección BTC o ETH {'address': '0x…'}"}

    def _rastrear(self, texto: str, ctx) -> dict:
        direccion, cadena = validar.direccion_cripto(texto)
        if direccion is None:
            return {"ok": False, "fuente": "validación",
                    "aviso": "No reconozco el formato (¿Bitcoin 1…/3…/bc1… o Ethereum 0x…?)."}
        return self.fuentes(ctx).cripto(direccion, cadena)

    def interest(self, msg: Message, ctx) -> float:
        if direccion_en(msg.text):
            return 0.95
        t = normalize(msg.text)
        return 0.5 if "cripto" in t and "direccion" in t else 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        d = direccion_en(msg.text)
        if d is None:
            if self.interest(msg, ctx) > 0:
                return Reply("Pasame la dirección (Bitcoin 1…/3…/bc1… o Ethereum 0x…) y la rastreo.")
            return None
        return Reply(linea(self._rastrear(d, ctx)))

    def command(self, name: str, data: dict, ctx):
        if name == "cripto":
            return self._rastrear(str(data.get("address", "")), ctx)
        return super().command(name, data, ctx)
