"""Cobros: el circuito de la seña.

1. Escucha `encargo.presupuesto_enviado` y anota que ese contacto debe una seña.
2. Cuando el cliente dice que transfirió (o manda el comprobante), le agradece y deja `confirmar_pago` PENDIENTE:
   el bot nunca da un pago por recibido (etiqueta `irreversible`: la confianza progresiva no lo baja sola).
3. Cuando la dueña aprueba ("Me llegó"), publica `pago.confirmado` (Encargos pasa a confirmado y Avisos le escribe).
4. Si la dueña rechaza ("no me llegó"), la seña vuelve a esperar.
Portado de `raphael_cobros` 0.1.0 (Empresas 0.4).

Dos formas de pagar la seña, las dos con la dueña como quien confirma:
- Transferencia: los datos de la cuenta (alias, CBU, titular, banco) salen de `payments` en la config.
- Mercado Pago (`payments.mercadopago.mode`: off, mock o real): al enviarse el presupuesto se crea un link de pago y se
  le ofrece a la dueña mandárselo al cliente (`enviar_link_pago`, con aprobación). Cuando Mercado Pago avisa que el pago
  se acreditó (comando `mp_aviso`, que llama el servidor desde su webhook), se verifica la firma, se lee el pago, se
  chequea que sea del encargo y alcance la seña, y se deja `confirmar_pago` PENDIENTE para la dueña. Nunca se confirma solo.
Sin clave de Mercado Pago (modo real) cae a transferencia sola y lo avisa en el estado (`mp_estado`).
"""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Cook, Reply
from raphael_core.text_es import money, normalize

from .. import config as C
from ..pay import MockProvider, PayError, provider_from

R_PAYMENT = re.compile(r"\b(transferi\w*|ya (te )?pague|pague la sena|deposite|comprobante|te (mande|paso|envie) la sena|abone|"
                       r"hice la transferencia|ahi (va|te mande)|ya esta (la sena|pago)|ya (te )?transferi)\b")


class Payments(Cook):
    name = "cobros"
    version = "2.0.0"
    description = "Registra avisos de pago de seña y deja la confirmación en manos de la dueña."
    commands = {"esperando": "Señas que todavía no llegaron", "avisados": "Pagos avisados por clientes, sin confirmar",
                "mp_aviso": "Aviso de Mercado Pago ({'payment_id', 'headers', 'query'}): deja la confirmación a la dueña",
                "mp_estado": "Estado de Mercado Pago: modo, si tiene clave y el último error"}

    #: los tests inyectan estos para no salir a internet: `http` (método, url, headers, cuerpo) -> (código, texto),
    #: `env` (de dónde salen las claves) y `provider` (un proveedor ya armado)
    http = None
    env = None
    provider = None
    _mock = None

    def _provider(self, ctx):
        if self.provider is not None:
            return self.provider
        cfg = C.of(ctx).payments
        if cfg.mercadopago.mode == "mock":
            if self._mock is None:
                self._mock = MockProvider()
            return self._mock
        return provider_from(cfg, http=self.http, env=self.env)

    def _mp_state(self, ctx) -> dict:
        return ctx.shared.get("mp_state", "state") or {}

    def _mp_error(self, ctx, what: str, detail: str) -> None:
        st = self._mp_state(ctx)
        st.update(error=detail[:200], error_at=ctx.now().isoformat(timespec="seconds"))
        ctx.shared.put("mp_state", "state", st)
        ctx.record(what, error=detail[:200])

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
        if action.type == "enviar_link_pago":
            url = str(action.data.get("url") or "")
            if not url.startswith("https://"):
                raise ActionError("el link de pago no es válido")
            try:
                amount = float(action.data.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            return (f"Si preferís pagar con Mercado Pago, acá tenés el link para la seña de tu encargo "
                    f"#{action.data.get('number')}{' (' + money(amount) + ')' if amount > 0 else ''}: {url}\n"
                    "Cuando se acredite te escribimos por acá 🙌")
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

    async def on_event(self, event, data, ctx):
        if event == "encargo.presupuesto_enviado" and data.get("deposit"):
            ctx.shared.put("deposits", data["contact"], {
                "number": data["number"], "contact": data["contact"], "client": data.get("client", ""),
                "deposit": data["deposit"], "status": "esperando", "since": ctx.now().isoformat(timespec="seconds")})
            await self._offer_link(data, ctx)
        elif event == "pendiente.rechazado" and data.get("type") == "confirmar_pago" and data.get("target"):
            d = ctx.shared.get("deposits", data["target"])
            if d and d["status"] == "avisado":       # la dueña dice que no le llegó: vuelve a esperar
                d["status"] = "esperando"
                d.pop("mp_payment_id", None)
                ctx.shared.put("deposits", data["target"], d)

    async def _offer_link(self, data: dict, ctx) -> None:
        """Con Mercado Pago activo: crea el link de la seña y le propone a la dueña mandárselo al cliente."""
        cfg = C.of(ctx).payments
        if cfg.mercadopago.mode == "off":
            return
        prov = self._provider(ctx)
        if prov is None:
            self._mp_error(ctx, "mp_sin_clave", f"falta la clave {cfg.mercadopago.token_env}: se cobra solo por transferencia")
            return
        title = f"Seña del encargo #{data['number']}" + (f" ({data['description']})" if data.get("description") else "")
        try:
            link = await prov.create_link(str(data["number"]), title, float(data["deposit"]))
        except PayError as exc:
            self._mp_error(ctx, "mp_fallido", str(exc))
            return
        d = ctx.shared.get("deposits", data["contact"]) or {}
        d.update(link=link.url, preference=link.id)
        ctx.shared.put("deposits", data["contact"], d)
        ctx.request(Action("enviar_link_pago", {"number": data["number"], "url": link.url, "amount": link.amount,
                                                "client": data.get("client", "")},
                           f"Mandarle a {data.get('client') or 'el cliente'} el link de Mercado Pago para la seña del encargo "
                           f"#{data['number']} ({money(link.amount)})", data["contact"]))

    async def command(self, name, data, ctx):
        if name == "esperando":
            return ctx.shared.list("deposits", status="esperando")
        if name == "avisados":
            return ctx.shared.list("deposits", status="avisado")
        if name == "mp_estado":
            cfg = C.of(ctx).payments.mercadopago
            return {"mode": cfg.mode, "con_clave": self._provider(ctx) is not None if cfg.mode != "off" else False,
                    **self._mp_state(ctx)}
        if name == "mp_aviso":
            return await self._mp_notice(data, ctx)
        return super().command(name, data, ctx)

    async def _mp_notice(self, data: dict, ctx) -> dict:
        """Mercado Pago avisó de un pago. Devuelve qué pasó; nunca confirma: deja `confirmar_pago` para la dueña."""
        prov = self._provider(ctx)
        if prov is None:
            return {"ok": False, "motivo": "mercado pago no está activo o falta la clave"}
        if not prov.verify_webhook(data.get("headers") or {}, data.get("query") or {}):
            ctx.record("mp_firma_invalida")
            return {"ok": False, "motivo": "firma inválida"}
        try:
            pay = await prov.get_payment(str(data.get("payment_id") or ""))
        except PayError as exc:
            self._mp_error(ctx, "mp_fallido", str(exc))
            return {"ok": False, "motivo": str(exc)}
        if pay.status != "approved":
            return {"ok": True, "estado": pay.status, "motivo": "todavía no está acreditado"}
        found = [(k, d) for k, d in self._deposits(ctx) if str(d.get("number")) == pay.reference]
        if not found:
            return {"ok": False, "motivo": "el pago no es de ningún encargo conocido"}
        contact, d = found[0]
        if d["status"] == "confirmado" or d.get("mp_payment_id") == pay.id:
            return {"ok": True, "motivo": "ya estaba registrado"}
        if pay.currency != "ARS" or pay.amount + 0.01 < float(d["deposit"]):
            return {"ok": False, "motivo": f"el monto ({money(pay.amount)}) no alcanza la seña ({money(d['deposit'])})"}
        d.update(status="avisado", mp_payment_id=pay.id, notified=ctx.now().isoformat(timespec="seconds"))
        ctx.shared.put("deposits", contact, d)
        ctx.request(Action("confirmar_pago", {"number": d["number"], "amount": pay.amount},
                           f"Mercado Pago acreditó {money(pay.amount)} del encargo #{d['number']} ({d['client']}). "
                           "¿Lo confirmás?", contact))
        return {"ok": True, "estado": "approved", "motivo": "queda para que la dueña confirme"}

    @staticmethod
    def _deposits(ctx):
        out = []
        for d in ctx.shared.list("deposits"):
            out.append((d.get("contact") or "", d))
        return out
