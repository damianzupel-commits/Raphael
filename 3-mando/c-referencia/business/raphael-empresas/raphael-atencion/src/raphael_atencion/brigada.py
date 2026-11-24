"""Brigada Atención: responde SOLO con la información del perfil, anota lo que no sabe y deriva reclamos.

- Pregunta con respuesta cargada (horarios, envíos, medios de pago, ubicación, preguntas frecuentes) -> responde.
- Pregunta sin respuesta cargada -> "te lo confirma {dueña}" + pendiente humano `responder_duda`.
- Reclamo o pedido de hablar con alguien -> se retira, avisa al cliente y crea `derivar_humano`.
- Saludo suelto -> saluda y ofrece ayuda.
"""

from __future__ import annotations

import re

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta
from raphael_harness.texto import es_pregunta, limpio, normalizar

from . import __version__

R_RECLAMO = re.compile(
    r"\b(reclamo|queja|me quejo|estafa|me estafaron|vino roto|llego (mal|roto|danado|fallado)|esta (roto|fallado|mal hecho)|"
    r"no (me )?(llego|respondieron|contestan)|devolucion|devuelvan|reembolso|"
    r"(quiero|necesito) hablar con (alguien|una persona|un humano|la duena|el duen\w+|vos)|me cobraron (de mas|mal))\b")
R_SALUDO = re.compile(r"^\s*(hola|holis|buenas|buen dia|buenos dias|buenas tardes|buenas noches|que tal)\W*$")

TEMAS = {
    "horarios": r"\b(horario|horarios|abren|abris|cierran|atienden|atendes|a que hora|que dias)\b",
    "envios": r"\b(envio|envios|envian|envias|mandan|mandas|despachan|llega a|llegan a|correo|retiro|retirar)\b",
    "medios_pago": r"\b(pago|pagos|pagar|transferencia|tarjeta|efectivo|mercado ?pago|cuotas|medios de pago)\b",
    "ubicacion": r"\b(donde (estan|queda|quedan)|direccion|ubicacion|local|showroom|zona)\b",
}


def _tokens(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 3}


class Atencion(Brigada):
    nombre = "atencion"
    version = __version__
    descripcion = "Responde con la información cargada, anota dudas y deriva reclamos a una persona."
    acciones = {"responder_duda": Nivel.HUMANO, "derivar_humano": Nivel.HUMANO}
    comandos = {"dudas": "Lista las preguntas que el bot no supo responder"}

    # ------------------------------------------------------------ qué sabe
    def _respuesta_cargada(self, t: str, ctx) -> str | None:
        info = ctx.perfil.informacion
        for faq in info.faq:
            claves = {normalizar(p) for p in faq.palabras} or _tokens(normalizar(faq.pregunta))
            if claves and (any(re.search(rf"\b{re.escape(c)}\b", t) for c in claves if faq.palabras)
                           or len(claves & _tokens(t)) / len(claves) >= 0.6):
                return faq.respuesta
        partes = []
        for tema, rx in TEMAS.items():
            if re.search(rx, t):
                valor = getattr(info, tema)
                if isinstance(valor, list):
                    valor = ", ".join(valor)
                if valor:
                    partes.append(valor if valor.endswith((".", "!", "?")) else valor + ".")
        return " ".join(partes) or None

    def interes(self, msg, ctx):
        t = normalizar(msg.texto)
        if R_RECLAMO.search(t):
            return 0.95
        if self._respuesta_cargada(t, ctx):
            return 0.6
        return 0.3 if es_pregunta(msg.texto) else 0.1

    # ------------------------------------------------------------ atender
    def atender(self, msg, ctx):
        t = normalizar(msg.texto)
        quien = ctx.perfil.quien_decide
        if R_RECLAMO.search(t):
            ctx.publicar("conversacion.derivada", {"contacto": msg.contacto, "motivo": "reclamo"})
            return Respuesta(
                f"Te entiendo, y lamento lo que pasó. Ya le aviso a {quien} para que te escriba personalmente enseguida.",
                [Accion("derivar_humano", {"texto": limpio(msg.texto, 400), "nombre": msg.nombre},
                        f"Reclamo de {msg.nombre or msg.contacto}: «{limpio(msg.texto, 140)}»")])
        cargada = self._respuesta_cargada(t, ctx)
        if cargada:
            return Respuesta(cargada)
        if R_SALUDO.search(t):
            return Respuesta(f"¡Hola! 😊 Gracias por escribir a {ctx.negocio}. ¿En qué te puedo ayudar?")
        if es_pregunta(msg.texto):
            n = ctx.datos.siguiente("dudas")
            ctx.datos.guardar("dudas", n, {"num": n, "contacto": msg.contacto, "pregunta": limpio(msg.texto, 300),
                                           "estado": "abierta", "cuando": ctx.ahora().isoformat(timespec="seconds")})
            return Respuesta(f"Eso te lo confirma {quien} personalmente, ya se lo anoto 😊",
                             [Accion("responder_duda", {"duda": n, "pregunta": limpio(msg.texto, 300)},
                                     f"Pregunta sin respuesta cargada: «{limpio(msg.texto, 140)}»")])
        return None

    # ------------------------------------------------------------ cuando la dueña resuelve
    def ejecutar(self, accion, ctx):
        if accion.tipo == "responder_duda":
            respuesta = accion.datos.get("respuesta")
            if not respuesta:
                raise ErrorDeAccion("falta la respuesta para la clienta")
            n = accion.datos.get("duda")
            d = ctx.datos.obtener("dudas", n) if n else None
            if d:
                ctx.datos.guardar("dudas", n, {**d, "estado": "respondida", "respuesta": respuesta})
            return respuesta
        if accion.tipo == "derivar_humano":
            return accion.datos.get("respuesta")
        raise ErrorDeAccion(f"atención no ejecuta '{accion.tipo}'")

    def comando(self, nombre, datos, ctx):
        if nombre == "dudas":
            return ctx.datos.listar("dudas", **({"estado": datos["estado"]} if datos.get("estado") else {}))
        return super().comando(nombre, datos, ctx)
