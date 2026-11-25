"""Avisos: cuando cambia el estado de un encargo, el cliente se entera solo.

Escucha `encargo.estado_cambiado` y pide `avisar_estado` (automático por manifiesto, etiqueta `external`). Solo avisa a
clientes que llegaron por un canal de mensajes (WhatsApp, Instagram). Un aviso por cambio de estado.
Portado de `raphael_avisos` 0.1.0 (Empresas 0.4).
"""

from __future__ import annotations

from raphael_core import Action, ActionError, Cook
from raphael_core.text_es import first_name

from .. import legal

CHANNELS = ("whatsapp", "instagram", "prueba")
TEXTS = {
    "confirmado": ("¡Hola {c}! Recibimos tu seña, ya queda confirmado tu {p} (encargo #{n}). "
                   "Te avisamos cuando empiece la confección 🧵"),
    "en_confeccion": "¡Hola {c}! Ya estamos trabajando en tu {p} ✂️ Te contamos cómo va.",
    "prueba": "¡Hola {c}! Tu {p} está para probártelo 👗 ¿Qué día podés pasar?",
    "listo": "¡Hola {c}! Tu {p} está listo 🎀 ¿Cuándo lo retirás o coordinamos el envío?",
    "entregado": "¡Gracias {c}! Esperamos que disfrutes tu {p} 💛",
}


class Notices(Cook):
    name = "avisos"
    version = "2.0.0"
    description = "Avisa automáticamente al cliente cada vez que cambia el estado de su pedido."
    commands = {"enviados": "Avisos enviados a clientes"}

    def on_event(self, event, data, ctx):
        if event != "encargo.estado_cambiado":
            return
        status = data.get("status")
        if status not in TEXTS or data.get("channel") not in CHANNELS or not data.get("contact"):
            return
        key = f"{data['number']}:{status}"
        if ctx.shared.get("notices", key):
            return                                   # un solo aviso por cambio
        ctx.shared.put("notices", key, {"number": data["number"], "status": status, "contact": data["contact"],
                                        "at": ctx.now().isoformat(timespec="seconds")})
        ctx.request(Action("avisar_estado", {"number": data["number"], "status": status, "client": data.get("client", ""),
                                             "description": data.get("description", "pedido")},
                           f"Aviso a {data.get('client')}: encargo #{data['number']} pasó a {status}", data["contact"]))

    def execute(self, action, ctx):
        if action.type != "avisar_estado":
            raise ActionError(f"avisos no ejecuta '{action.type}'")
        d = action.data
        template = TEXTS.get(d.get("status"))
        if not template:
            return None
        text = template.format(c=first_name(d.get("client", "")) or "", p=d.get("description", "pedido"),
                               n=d.get("number")).replace("¡Hola !", "¡Hola!").replace("¡Gracias !", "¡Gracias!")
        legal.review(ctx, text, f"aviso-{d.get('number')}-{d.get('status')}")
        return text

    def command(self, name, data, ctx):
        if name == "enviados":
            return ctx.shared.list("notices")
        return super().command(name, data, ctx)
