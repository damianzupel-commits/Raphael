"""Orquestador de Raphael: decide qué brigadas ven cada mensaje y en qué orden.

Reglas, en este orden:
1. Un reclamo o un pedido de hablar con una persona va primero a Atención (que lo deriva).
2. La brigada que tiene una conversación abierta con ese contacto sigue.
3. Después, por interés declarado (0 a 1), de mayor a menor.
4. Atención siempre queda al final como red: si nadie más lo toma, responde o anota la duda.
"""

from __future__ import annotations

import re

from raphael_harness import Orquestador
from raphael_harness.texto import normalizar

from . import __version__, agente

R_RECLAMO = re.compile(
    r"\b(reclamo|queja|me quejo|estafa|me estafaron|vino roto|llego (mal|roto|danado|fallado)|esta (roto|fallado|mal hecho)|"
    r"no (me )?(llego|respondieron|contestan)|devolucion|devuelvan|reembolso|"
    r"(quiero|necesito) hablar con (alguien|una persona|un humano|la duena|el duen\w+|vos)|me cobraron (de mas|mal))\b")

ATENCION = "atencion"


class OrquestadorRaphael(Orquestador):
    nombre = "orquestador"
    version = __version__
    descripcion = ("Reparte cada mensaje entre las brigadas y hace de secretario de la dueña: "
                   "qué hay para hoy, qué conviene hacer primero y el contexto de lo que el bot no resolvió.")

    def elegir(self, msg, ctx, brigadas):
        por_nombre = {b.nombre: b for b in brigadas}
        t = normalizar(msg.texto)
        orden: list = []

        reclamo = bool(R_RECLAMO.search(t))
        if reclamo and ATENCION in por_nombre:
            orden.append(por_nombre[ATENCION])

        abiertas = [b for b in brigadas if b not in orden and b.en_curso(msg, ctx.para(b.nombre))]
        orden += abiertas

        puntajes = [(b.interes(msg, ctx.para(b.nombre)), b) for b in brigadas if b not in orden and b.nombre != ATENCION]
        con_interes = [b for p, b in sorted(puntajes, key=lambda x: -x[0]) if p > 0]
        orden += con_interes
        if not (reclamo or abiertas or con_interes):                # ninguna regla lo ubicó: que lo mire la IA (si hay)
            elegida = self._preguntar_a_la_ia(msg, ctx, [b for b in brigadas if b.nombre != ATENCION])
            if elegida is not None:
                orden.append(elegida)

        if ATENCION in por_nombre and por_nombre[ATENCION] not in orden:
            orden.append(por_nombre[ATENCION])
        ctx.registrar("orden", contacto=msg.contacto, orden=[b.nombre for b in orden])
        return orden

    def _preguntar_a_la_ia(self, msg, ctx, candidatas):
        """Las reglas no vieron a quién corresponde: si hay IA, ella elige entre las brigadas activas (o dice que a ninguna)."""
        if not candidatas or not ctx.hay_ia("intencion"):
            return None
        menu = "\n".join(f"- {b.nombre}: {b.descripcion}" for b in candidatas)
        r = ctx.ia("intencion", [{"role": "system", "content": "Sos el recepcionista de un negocio. Te llega el mensaje de un cliente y tenés que decidir qué área lo atiende. "
                                  'Respondé SOLO un JSON: {"brigada": "<nombre exacto>"} o {"brigada": "ninguna"} si no corresponde a ninguna.\nÁreas:\n' + menu},
                                 {"role": "user", "content": msg.texto[:500]}], max_tokens=60, temperatura=0)
        m = re.search(r'"brigada"\s*:\s*"([^"]*)"', r or "")
        elegida = next((b for b in candidatas if m and b.nombre == m.group(1).strip()), None)
        ctx.registrar("router_ia", contacto=msg.contacto, brigada=elegida.nombre if elegida else None)
        return elegida

    def atender_duena(self, texto, ctx):
        return agente.atender(texto, ctx)
