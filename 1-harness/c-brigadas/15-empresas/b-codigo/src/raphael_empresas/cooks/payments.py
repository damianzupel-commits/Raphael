"""Cobros: el circuito de la seña.

1. Escucha `encargo.presupuesto_enviado` y anota que ese contacto debe una seña.
2. Cuando el cliente dice que transfirió (o manda el comprobante), le agradece y deja `confirmar_pago` PENDIENTE:
   el bot nunca da un pago por recibido (etiqueta `irreversible`: la confianza progresiva no lo baja sola).
3. Cuando la dueña aprueba ("Me llegó"), publica `pago.confirmado` (Encargos pasa a confirmado y Avisos le escribe).
4. Si la dueña rechaza ("no me llegó"), la seña vuelve a esperar.
Portado de `raphael_cobros` 0.1.0 (Empresas 0.4).
"""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Cook, Reply
from raphael_core.text_es import money, normalize

from .. import config as C

R_PAYMENT = re.compile(r"\b(transferi\w*|ya (te )?pague|pague la sena|deposite|comprobante|te (mande|paso|envie) la sena|abone|"
                       r"hice la transferencia|ahi (va|te mande)|ya esta (la sena|pago)|ya (te )?transferi)\b")


class Payments(Cook):
    name = "cobros"
    version = "2.0.0"
    description = "Registra avisos de pago de seña y deja la confirmación en manos de la dueña."
    commands = {"esperando": "Señas que todavía no llegaron", "avisados": "Pagos avisados por clientes, sin confirmar"}

    def _waiting(self, contact: str, ctx) -> dict | None:
        d = ctx.shared.get("deposits", contact)
        return d if d and d["status"] in ("esperando", "avisado") else None

    def _is_payment(self, msg) -> bool:
        return bool(R_PAYMENT.search(normalize(msg.text))) or msg.attachment

    def interest(self, msg, ctx):
        return 0.95 if self._waiting(msg.contact, ctx) and self._is_payment(msg) else 0.0

    def in_progress(self, msg, ctx):
        return self.interest(msg, ctx) > 0          # un comprobante le gana a cualquier conversación abierta

    def handle(self, msg, ctx):
        d = self._waiting(msg.contact, ctx)
        if not d or not self._is_payment(msg):
            return None
        who = C.decider(ctx)
        if d["status"] == "avisado":
            return Reply(f"¡Gracias! Ya le avisé a {who}; apenas lo confirme te escribimos 🙌")
        d.update(status="avisado", notified=ctx.now().isoformat(timespec="seconds"))
        ctx.shared.put("deposits", msg.contact, d)
        return Reply(
            f"¡Gracias! 🙌 Le aviso a {who} para que confirme la transferencia y te escribimos por acá.",
            [Action("confirmar_pago", {"number": d["number"], "amount": d["deposit"]},
                    f"{d['client']} dice que transfirió la seña del encargo #{d['number']} ({money(d['deposit'])}). ¿Te llegó?")])

    def execute(self, action, ctx):
        if action.type != "confirmar_pago":
            raise ActionError(f"cobros no ejecuta '{action.type}'")
        contact = action.target
        d = ctx.shared.get("deposits", contact) if contact else None
        if not d:
            raise ActionError("no hay una seña esperando para ese cliente")
        try:
            amount = float(action.data.get("amount") or d["deposit"])
        except (TypeError, ValueError) as exc:
            raise ActionError("el monto tiene que ser un número") from exc
        if amount <= 0:
            raise ActionError("el monto tiene que ser mayor que cero")
        d.update(status="confirmado", amount=amount, confirmed=ctx.now().isoformat(timespec="seconds"))
        ctx.shared.put("deposits", contact, d)
        ctx.publish("pago.confirmado", {"number": d["number"], "amount": amount, "contact": contact})
        return None                                  # el mensaje al cliente lo manda Avisos al cambiar el estado

    def on_event(self, event, data, ctx):
        if event == "encargo.presupuesto_enviado" and data.get("deposit"):
            ctx.shared.put("deposits", data["contact"], {
                "number": data["number"], "client": data.get("client", ""), "deposit": data["deposit"],
                "status": "esperando", "since": ctx.now().isoformat(timespec="seconds")})
        elif event == "pendiente.rechazado" and data.get("type") == "confirmar_pago" and data.get("target"):
            d = ctx.shared.get("deposits", data["target"])
            if d and d["status"] == "avisado":       # la dueña dice que no le llegó: vuelve a esperar
                d["status"] = "esperando"
                ctx.shared.put("deposits", data["target"], d)

    def command(self, name, data, ctx):
        if name == "esperando":
            return ctx.shared.list("deposits", status="esperando")
        if name == "avisados":
            return ctx.shared.list("deposits", status="avisado")
        return super().command(name, data, ctx)
