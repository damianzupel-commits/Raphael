"""Atención: responde SOLO con la información cargada, anota lo que no sabe y deriva reclamos.

- Pregunta con respuesta cargada (horarios, envíos, medios de pago, ubicación, preguntas frecuentes) -> responde.
- Pregunta sin respuesta cargada -> "te lo confirma {dueña}" + pendiente humano `responder_duda`.
- Reclamo o pedido de hablar con alguien -> se retira, avisa al cliente y crea `derivar_humano`.
- Saludo suelto -> saluda y ofrece ayuda.

Es el cocinero de red de la instalación (`routing.fallback_cook: empresas/atencion`): ve el mensaje si nadie más lo tomó.
Portado de `raphael_atencion` 0.1.0 (Empresas 0.4).
"""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Cook, Reply
from raphael_core.text_es import clean, is_question, normalize

from .. import config as C
from ..signals import R_COMPLAINT

R_GREETING = re.compile(r"^\s*(hola|holis|buenas|buen dia|buenos dias|buenas tardes|buenas noches|que tal)\W*$")

TOPICS = {
    "hours": r"\b(horario|horarios|abren|abris|cierran|atienden|atendes|a que hora|que dias)\b",
    "shipping": r"\b(envio|envios|envian|envias|mandan|mandas|despachan|llega a|llegan a|correo|retiro|retirar)\b",
    "payment_methods": r"\b(pago|pagos|pagar|transferencia|tarjeta|efectivo|mercado ?pago|cuotas|medios de pago)\b",
    "location": r"\b(donde (estan|queda|quedan)|direccion|ubicacion|local|showroom|zona)\b",
}


def _tokens(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 3}


class Attention(Cook):
    name = "atencion"
    version = "2.0.0"
    description = "Responde con la información cargada, anota dudas y deriva reclamos a una persona."
    commands = {"dudas": "Las preguntas que el bot no supo responder ({'status': 'abierta'|'respondida'} opcional)"}

    # --- qué sabe
    def known_answer(self, t: str, ctx) -> str | None:
        info = C.of(ctx).info
        for faq in info.faq:
            keys = {normalize(k) for k in faq.keywords} or _tokens(normalize(faq.question))
            if keys and (any(re.search(rf"\b{re.escape(k)}\b", t) for k in keys if faq.keywords)
                         or len(keys & _tokens(t)) / len(keys) >= 0.6):
                return faq.answer
        parts = []
        for topic, rx in TOPICS.items():
            if re.search(rx, t):
                value = getattr(info, topic)
                if isinstance(value, tuple):
                    value = ", ".join(value)
                if value:
                    parts.append(value if value.endswith((".", "!", "?")) else value + ".")
        return " ".join(parts) or None

    def interest(self, msg, ctx):
        t = normalize(msg.text)
        if R_COMPLAINT.search(t):
            return 0.95
        if self.known_answer(t, ctx):
            return 0.6
        return 0.3 if is_question(msg.text) else 0.1

    # --- atender
    def handle(self, msg, ctx):
        t = normalize(msg.text)
        who = C.decider(ctx)
        if R_COMPLAINT.search(t):
            ctx.publish("conversacion.derivada", {"contact": msg.contact, "reason": "reclamo"})
            return Reply(
                f"Te entiendo, y lamento lo que pasó. Ya le aviso a {who} para que te escriba personalmente enseguida.",
                [Action("derivar_humano", {"text": clean(msg.text, 400), "name": msg.name},
                        f"Reclamo de {msg.name or msg.contact}: «{clean(msg.text, 140)}»")])
        known = self.known_answer(t, ctx)
        if known:
            return Reply(known)
        if R_GREETING.search(t):
            return Reply(f"¡Hola! 😊 Gracias por escribir a {C.business_name(ctx)}. ¿En qué te puedo ayudar?")
        if is_question(msg.text):
            n = ctx.shared.next("questions")
            ctx.shared.put("questions", n, {"number": n, "contact": msg.contact, "question": clean(msg.text, 300),
                                            "status": "abierta", "at": ctx.now().isoformat(timespec="seconds")})
            return Reply(f"Eso te lo confirma {who} personalmente, ya se lo anoto 😊",
                         [Action("responder_duda", {"question_number": n, "question": clean(msg.text, 300)},
                                 f"Pregunta sin respuesta cargada: «{clean(msg.text, 140)}»")])
        return None

    # --- cuando la dueña resuelve
    def execute(self, action, ctx):
        if action.type == "responder_duda":
            reply = action.data.get("reply")
            if not reply:
                raise ActionError("falta la respuesta para el cliente")
            n = action.data.get("question_number")
            q = ctx.shared.get("questions", n) if n else None
            if q:
                ctx.shared.put("questions", n, {**q, "status": "respondida", "reply": reply})
            return reply
        if action.type == "derivar_humano":
            return action.data.get("reply")
        raise ActionError(f"atención no ejecuta '{action.type}'")

    def command(self, name, data, ctx):
        if name == "dudas":
            status = data.get("status") or data.get("estado")
            return ctx.shared.list("questions", **({"status": status} if status else {}))
        return super().command(name, data, ctx)
