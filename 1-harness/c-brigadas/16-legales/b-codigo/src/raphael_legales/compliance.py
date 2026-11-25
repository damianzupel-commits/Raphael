"""Checklist de cumplimiento para un pyme argentino. Los ítems son PREGUNTAS a verificar, no afirmaciones de qué dice la
ley: cada uno apunta a la norma de partida y se marca "con fuente consultada" solo si la verificación de esa norma está
vigente (ver `sources.py`). Algunos se deducen solos de lo que hay en el archivo; el resto, de `checklist.respuestas`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import archive


@dataclass(frozen=True)
class Item:
    id: str
    area: str
    text: str
    norm: str
    derive: str | None = None   # nombre de la regla que lo deduce solo


ITEMS: tuple[Item, ...] = (
    Item("dp-politica", "datos_personales", "Política de privacidad emitida y a la vista del cliente.", "ley-25326", "policy"),
    Item("dp-consentimiento", "datos_personales", "Se registra el consentimiento de cada contacto antes de usar sus datos.",
         "ley-25326", "consent"),
    Item("dp-ia-terceros", "datos_personales", "Se informa que los mensajes se procesan con un proveedor externo de IA.",
         "ley-25326", "policy"),
    Item("dp-derechos", "datos_personales", "Hay un canal para que el titular pida acceso, rectificación y supresión.", "ley-25326"),
    Item("dp-registro-base", "datos_personales",
         "Se consultó si la base de datos debe inscribirse ante la autoridad de aplicación.", "ley-25326"),
    Item("co-terminos", "consumidor", "Términos y condiciones emitidos y a la vista.", "ley-24240", "tyc"),
    Item("co-precio-final", "consumidor", "Los precios publicados son claros y finales para el consumidor.", "ley-24240"),
    Item("co-revocacion", "consumidor", "Se informa el derecho de revocación en ventas a distancia (confirmar plazo vigente).",
         "ley-24240"),
    Item("co-reclamos", "consumidor", "Datos de contacto y canal de reclamos visibles.", "ley-24240", "email"),
    Item("fa-situacion", "facturacion", "Situación frente a ARCA definida y al día.", "arca-facturacion"),
    Item("fa-cuit", "facturacion", "CUIT cargado en los datos del negocio.", "arca-facturacion", "cuit"),
    Item("fa-comprobantes", "facturacion", "Se emite comprobante electrónico por cada venta que lo requiere.", "arca-facturacion"),
    Item("wa-optin", "meta_whatsapp", "Hay consentimiento (opt-in) registrado para escribir por WhatsApp.", "whatsapp-politica",
         "consent_wa"),
    Item("wa-ventana", "meta_whatsapp", "Fuera de la ventana de 24 h solo se envían plantillas aprobadas.", "whatsapp-ventana"),
    Item("wa-baja", "meta_whatsapp", "Se respeta de inmediato el pedido de baja de un contacto.", "whatsapp-politica"),
)


def _derived(item: Item, space, cfg) -> bool | None:
    d = item.derive
    if d == "policy":
        return archive.issued(space, "politica_privacidad") is not None
    if d == "tyc":
        return archive.issued(space, "terminos_condiciones") is not None
    if d == "consent":
        return bool(archive.active_consents(space))
    if d == "consent_wa":
        return any(c["channel"] == "whatsapp" for c in archive.active_consents(space))
    if d == "email":
        return bool(cfg.negocio.email)
    if d == "cuit":
        return bool(cfg.negocio.cuit)
    return None


def source_status(space, norm_id: str, now: datetime, days: int) -> dict:
    c = space.get("norm_checks", norm_id)
    if not c:
        return {"state": "sin_verificar", "detail": "nunca se consultó la fuente"}
    if not c["ok"]:
        return {"state": "sin_verificar", "detail": c["error"] or "la consulta falló", "checked_at": c["checked_at"]}
    if datetime.fromisoformat(c["checked_at"]) + timedelta(days=days) < now:
        return {"state": "vencida", "detail": "la última consulta es vieja", "checked_at": c["checked_at"], "mode": c["mode"]}
    return {"state": "consultada", "checked_at": c["checked_at"], "mode": c["mode"], "url": c["url"]}


def build(space, cfg, now: datetime) -> dict:
    out, counted, done = [], 0, 0
    for it in ITEMS:
        derived = _derived(it, space, cfg)
        answer = cfg.checklist.respuestas.get(it.id)
        if derived is True:
            state = "cumple"
        elif answer:
            state = answer
        else:
            state = "pendiente"
        if state != "no_aplica":
            counted += 1
            done += state == "cumple"
        out.append({"id": it.id, "area": it.area, "text": it.text, "state": state, "norm": it.norm,
                    "auto": derived is True, "source": source_status(space, it.norm, now, cfg.fuentes.dias_vigencia)})
    return {"items": out, "score": f"{done}/{counted}", "pending": [i["id"] for i in out if i["state"] == "pendiente"]}
