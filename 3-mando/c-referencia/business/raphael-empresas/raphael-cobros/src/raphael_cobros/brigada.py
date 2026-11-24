"""Brigada Cobros: el circuito de la seña.

1. Escucha `encargo.presupuesto_enviado` y anota que ese contacto debe una seña.
2. Cuando el cliente dice que transfirió (o manda el comprobante), le agradece y deja
   `confirmar_pago` PENDIENTE: el bot nunca da un pago por recibido.
3. Cuando la dueña aprueba ("Me llegó"), publica `pago.confirmado` (Encargos pasa a confirmado
   y Avisos le escribe al cliente).
"""

from __future__ import annotations

import re

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta
from raphael_harness.texto import normalizar, plata

from . import __version__

R_PAGO = re.compile(r"\b(transferi\w*|ya (te )?pague|pague la sena|deposite|comprobante|te (mande|paso|envie) la sena|abone|"
                    r"hice la transferencia|ahi (va|te mande)|ya esta (la sena|pago)|ya (te )?transferi)\b")


class Cobros(Brigada):
    nombre = "cobros"
    version = __version__
    descripcion = "Registra avisos de pago de seña y deja la confirmación en manos de la dueña."
    acciones = {"confirmar_pago": Nivel.APROBACION}
    eventos = ("encargo.presupuesto_enviado", "pendiente.rechazado")
    comandos = {"esperando": "Señas que todavía no llegaron", "avisados": "Pagos avisados por clientes, sin confirmar"}

    def _espera(self, contacto: str, ctx) -> dict | None:
        e = ctx.datos.obtener("esperas", contacto)
        return e if e and e["estado"] in ("esperando", "avisado") else None

    def _es_pago(self, msg) -> bool:
        return bool(R_PAGO.search(normalizar(msg.texto))) or msg.adjunto

    def interes(self, msg, ctx):
        return 0.95 if self._espera(msg.contacto, ctx) and self._es_pago(msg) else 0.0

    def en_curso(self, msg, ctx):
        return self.interes(msg, ctx) > 0          # un comprobante le gana a cualquier conversación abierta

    def atender(self, msg, ctx):
        e = self._espera(msg.contacto, ctx)
        if not e or not self._es_pago(msg):
            return None
        if e["estado"] == "avisado":
            return Respuesta(f"¡Gracias! Ya le avisé a {ctx.perfil.quien_decide}; apenas lo confirme te escribimos 🙌")
        e.update(estado="avisado", avisado=ctx.ahora().isoformat(timespec="seconds"))
        ctx.datos.guardar("esperas", msg.contacto, e)
        return Respuesta(
            f"¡Gracias! 🙌 Le aviso a {ctx.perfil.quien_decide} para que confirme la transferencia y te escribimos por acá.",
            [Accion("confirmar_pago", {"num": e["num"], "monto": e["sena"]},
                    f"{e['cliente']} dice que transfirió la seña del encargo #{e['num']} ({plata(e['sena'])}). ¿Te llegó?")])

    def ejecutar(self, accion, ctx):
        if accion.tipo != "confirmar_pago":
            raise ErrorDeAccion(f"cobros no ejecuta '{accion.tipo}'")
        contacto = accion.destino
        e = ctx.datos.obtener("esperas", contacto) if contacto else None
        if not e:
            raise ErrorDeAccion("no hay una seña esperando para ese cliente")
        monto = float(accion.datos.get("monto") or e["sena"])
        e.update(estado="confirmado", monto=monto, confirmado=ctx.ahora().isoformat(timespec="seconds"))
        ctx.datos.guardar("esperas", contacto, e)
        ctx.publicar("pago.confirmado", {"num": e["num"], "monto": monto, "contacto": contacto})
        return None                                  # el mensaje al cliente lo manda Avisos al cambiar el estado

    def al_evento(self, evento, datos, ctx):
        if evento == "encargo.presupuesto_enviado" and datos.get("sena"):
            ctx.datos.guardar("esperas", datos["contacto"], {
                "num": datos["num"], "cliente": datos.get("cliente", ""), "sena": datos["sena"], "estado": "esperando",
                "desde": ctx.ahora().isoformat(timespec="seconds")})
        elif evento == "pendiente.rechazado" and datos.get("tipo") == "confirmar_pago" and datos.get("destino"):
            e = ctx.datos.obtener("esperas", datos["destino"])
            if e and e["estado"] == "avisado":       # la dueña dice que no le llegó: vuelve a esperar
                e["estado"] = "esperando"
                ctx.datos.guardar("esperas", datos["destino"], e)

    def comando(self, nombre, datos, ctx):
        if nombre == "esperando":
            return ctx.datos.listar("esperas", estado="esperando")
        if nombre == "avisados":
            return ctx.datos.listar("esperas", estado="avisado")
        return super().comando(nombre, datos, ctx)
