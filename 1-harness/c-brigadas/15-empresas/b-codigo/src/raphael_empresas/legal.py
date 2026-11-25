"""Puntos de contacto con Legales (pieza 16), todo por eventos: esta brigada no importa a ninguna otra.

- `revision.pedida` {text, ref}: antes de mandarle un texto a un cliente. Es un aviso: Legales marca riesgos
  (`riesgo.detectado`) pero no frena el envío; lo irreversible sigue pidiendo aprobación por el manifiesto.
- `consentimiento.recibido` {contact, purpose, channel, evidence}: el cliente aceptó recibir avisos.
- `baja.solicitada` {contact, channel}: el cliente pidió no recibir más. Si Legales no está montado, no pasa nada.
"""

from __future__ import annotations

import re

from raphael_core.text_es import clean, normalize

R_OPTOUT = re.compile(
    r"\b(dar(me)? de baja|me doy de baja|desuscrib\w+|desinscrib\w+|"
    r"no quiero (recibir )?(mas )?(mensajes|avisos|novedades|promos|promociones|ofertas)|"
    r"(dejen|deja|dejame|dejame de) de (escribir|mandar|molestar)\w*)\b|^\W*(baja|stop|basta)\W*$")
R_OPTIN = re.compile(
    r"\b(quiero recibir|acepto recibir|si,? quiero recibir|me gustaria recibir|avisenme|mandenme)\b.*"
    r"\b(avisos|novedades|promos|promociones|ofertas)\b")

PURPOSE = "avisos"


def optout(text: str) -> bool:
    return bool(R_OPTOUT.search(normalize(text)))


def optin(text: str) -> bool:
    t = normalize(text)
    return bool(R_OPTIN.search(t)) and not R_OPTOUT.search(t)


def review(ctx, text: str, ref: str) -> None:
    """Pide revisión de un texto que está por salir al cliente (no bloquea)."""
    if text and text.strip():
        ctx.publish("revision.pedida", {"text": clean(text, 2000), "ref": ref})
