"""El cocinero de la brigada de ejemplo."""

from __future__ import annotations

from raphael_core import Action, Cook, Health, Message, Reply
from raphael_core.text_es import normalize

GREETINGS = ("hola", "buen dia", "buenas", "que tal")


class Greeter(Cook):
    name = "saludador"
    version = "1.0.0"
    description = "Contesta saludos y lleva la cuenta de visitas por contacto."
    commands = {"visitas": "cuántas veces escribió cada contacto", "olvidar": "borra la cuenta de un contacto"}

    def interest(self, msg: Message, ctx) -> float:
        text = normalize(msg.text)
        return 0.9 if any(g in text for g in GREETINGS) or "regalo" in text else 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        text = normalize(msg.text)
        if not (any(g in text for g in GREETINGS) or "regalo" in text):
            return None
        visits = (ctx.shared.get("visitas", msg.contact) or {}).get("n", 0) + 1
        ctx.shared.put("visitas", msg.contact, {"contact": msg.contact, "n": visits})
        greeting = ctx.config.get("saludo") or "¡Hola"
        text_out = f"{greeting}, {msg.name}!" if msg.name else f"{greeting}!"
        reply = Reply(text_out + (" Qué bueno verte de nuevo." if visits > 1 else ""))
        if "regalo" in text:
            reply.actions.append(Action("regalar", {"para": msg.contact}, summary=f"Mandar un regalo a {msg.contact}",
                                        target=msg.contact))
        ctx.publish("saludo.hecho", {"contact": msg.contact, "visits": visits})
        return reply

    def execute(self, action: Action, ctx) -> str | None:
        if action.type == "regalar":
            ctx.shared.put("regalos", action.data.get("para", "?"), {"estado": "enviado"})
            return "¡Te mandamos un regalo! 🎁"
        return super().execute(action, ctx)

    def command(self, name: str, data: dict, ctx):
        if name == "visitas":
            return {d["contact"]: d["n"] for d in ctx.shared.list("visitas")}
        if name == "olvidar":
            return ctx.shared.delete("visitas", data.get("contact", ""))
        return super().command(name, data, ctx)


def check(ctx=None) -> Health:
    return Health(True, "la brigada de saludo no depende de nada externo")
