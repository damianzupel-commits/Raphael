"""Normas de partida y dónde se consultan. NO guarda el contenido de las normas: guarda a qué fuente oficial hay que
ir a mirar. Las URLs son las oficiales encontradas el 25 nov 2026; se pueden pisar en `fuentes.urls` de la config.

`expect`: palabras que tiene que contener la página para darla por la norma correcta (no prueba vigencia)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Norm:
    id: str
    title: str
    url: str
    expect: tuple[str, ...]
    area: str


NORMS: dict[str, Norm] = {n.id: n for n in (
    Norm("ley-25326", "Ley 25.326 · Protección de los Datos Personales (texto actualizado)",
         "https://www.argentina.gob.ar/normativa/nacional/ley-25326-64790/actualizacion",
         ("25326", "25.326", "datos personales"), "datos_personales"),
    Norm("ley-24240", "Ley 24.240 · Defensa del Consumidor (texto actualizado)",
         "https://www.argentina.gob.ar/normativa/nacional/norma-638/actualizacion",
         ("24240", "24.240", "consumidor"), "consumidor"),
    Norm("arca-facturacion", "ARCA · Facturación, régimen general (modalidades de comprobantes)",
         "https://www.arca.gob.ar/facturacion/regimen-general/modalidades.asp",
         ("factura", "comprobante"), "facturacion"),
    Norm("whatsapp-politica", "WhatsApp Business · Política comercial (Business Policy)",
         "https://business.whatsapp.com/policy", ("whatsapp", "policy"), "meta_whatsapp"),
    Norm("whatsapp-ventana", "Meta · WhatsApp Business Platform: mensajes de servicio y ventana de atención",
         "https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages",
         ("whatsapp", "service"), "meta_whatsapp"),
)}


def norm_url(norm: Norm, overrides: dict[str, str]) -> str:
    return overrides.get(norm.id) or norm.url
