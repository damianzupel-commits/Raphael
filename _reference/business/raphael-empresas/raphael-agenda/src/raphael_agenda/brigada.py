"""Brigada Agenda: turnos de prueba, medidas y retiro.

- El cliente pide un turno -> el bot pregunta qué día le queda bien (ofrece las franjas del perfil).
- Con el día (y la hora si la dice) -> `confirmar_turno` PENDIENTE: la dueña confirma o propone otro.
- Al confirmar: no permite dos turnos en el mismo día y hora; el cliente recibe la confirmación.
- `tick`: recordatorio automático `recordatorio_dias_antes` días antes (perfil).
- Escucha `turno.pedido` (Encargos, cuando alguien prefiere que la midan).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta
from raphael_harness.texto import fecha_en_palabras, limpio, normalizar, parse_fecha, parse_hora, primer_nombre

from . import __version__

R_TURNO = re.compile(r"\b(turno|probarme|probar(lo|la)?|prueba|medirme|me midan|tomar (las )?medidas|pasar a (buscar|retirar|probar)|"
                     r"retirar(lo|la)?|cuando (puedo|paso)|puedo (ir|pasar))\b")
MOTIVOS = [("prueba", r"prob"), ("medidas", r"medi|medidas"), ("retiro", r"retir|buscar")]


def motivo_de(t: str) -> str:
    return next((m for m, rx in MOTIVOS if re.search(rx, t)), "turno")


class Agenda(Brigada):
    nombre = "agenda"
    version = __version__
    descripcion = "Pide turnos al cliente, los deja para que la dueña los confirme y manda recordatorios."
    acciones = {"confirmar_turno": Nivel.APROBACION, "enviar_recordatorio": Nivel.AUTO}
    eventos = ("turno.pedido",)
    comandos = {"turnos": "Turnos confirmados desde hoy", "calendario": "Turnos agrupados por fecha"}

    def en_curso(self, msg, ctx):
        return ctx.datos.obtener("chats", msg.contacto) is not None

    def interes(self, msg, ctx):
        return 0.7 if R_TURNO.search(normalizar(msg.texto)) else 0.0

    def _ofrecer(self, ctx) -> str:
        franjas = ctx.perfil.agenda.franjas
        return ("¿Qué día y horario te queda mejor? 🗓️" + (f" Tenemos: {', '.join(franjas)}." if franjas else ""))

    def atender(self, msg, ctx):
        t = normalizar(msg.texto)
        chat = ctx.datos.obtener("chats", msg.contacto)
        if chat is None:
            if not R_TURNO.search(t):
                return None
            chat = {"motivo": motivo_de(t), "nombre": msg.nombre}
        fecha = parse_fecha(t, ctx.hoy())
        if not fecha:
            ctx.datos.guardar("chats", msg.contacto, chat)
            return Respuesta(self._ofrecer(ctx))
        ctx.datos.borrar("chats", msg.contacto)
        return Respuesta(f"¡Genial! Le paso tu pedido a {ctx.perfil.quien_decide} y te confirmamos el turno por acá 😊",
                         [self._pedido(msg.contacto, chat.get("nombre") or msg.nombre, chat["motivo"], fecha,
                                       parse_hora(t), limpio(msg.texto, 160), ctx)])

    def _pedido(self, contacto, nombre, motivo, fecha, hora, texto, ctx) -> Accion:
        cuando = fecha_en_palabras(fecha, ctx.hoy()) + (f" a las {hora}" if hora else " (hora a definir)")
        return Accion("confirmar_turno", {"fecha": fecha, "hora": hora, "motivo": motivo, "nombre": nombre, "pedido": texto},
                      f"Turno de {motivo} para {nombre or contacto}: {cuando}. Confirmá (podés cambiar fecha u hora).")

    def ejecutar(self, accion, ctx):
        if accion.tipo == "confirmar_turno":
            d = accion.datos
            if not d.get("fecha") or not d.get("hora"):
                raise ErrorDeAccion("falta la fecha o la hora: aprobalo con {'fecha': 'AAAA-MM-DD', 'hora': 'HH:MM'}")
            try:
                date.fromisoformat(d["fecha"])
            except ValueError as exc:
                raise ErrorDeAccion("la fecha tiene que ser AAAA-MM-DD") from exc
            clave = f"{d['fecha']} {d['hora']}"
            if ctx.datos.obtener("turnos", clave):
                raise ErrorDeAccion(f"ya hay un turno el {clave}: elegí otro horario")
            ctx.datos.guardar("turnos", clave, {"fecha": d["fecha"], "hora": d["hora"], "motivo": d.get("motivo", "turno"),
                                                "nombre": d.get("nombre", ""), "contacto": accion.destino, "recordado": False})
            ctx.publicar("turno.confirmado", {"fecha": d["fecha"], "hora": d["hora"], "contacto": accion.destino,
                                              "motivo": d.get("motivo", "turno")})
            nombre = primer_nombre(d.get("nombre", ""))
            return (f"¡Listo{', ' + nombre if nombre else ''}! Te esperamos el {fecha_en_palabras(d['fecha'], ctx.hoy())} "
                    f"a las {d['hora']} para la {d.get('motivo', 'cita')} 😊")
        if accion.tipo == "enviar_recordatorio":
            d = accion.datos
            return (f"¡Hola! Te recordamos tu turno de {d.get('motivo', 'cita')} el {fecha_en_palabras(d['fecha'], ctx.hoy())} "
                    f"a las {d['hora']} 🗓️ Si no podés venir, avisanos por acá.")
        raise ErrorDeAccion(f"agenda no ejecuta '{accion.tipo}'")

    def al_evento(self, evento, datos, ctx):
        if evento == "turno.pedido":
            t = normalizar(datos.get("preferencia", ""))
            fecha = parse_fecha(t, ctx.hoy())
            if fecha:
                ctx.solicitar(self._with_destino(self._pedido(datos["contacto"], datos.get("nombre", ""), datos.get("motivo", "medidas"),
                                                              fecha, parse_hora(t), datos.get("preferencia", ""), ctx), datos["contacto"]))
            else:
                ctx.solicitar(Accion("confirmar_turno", {"fecha": None, "hora": None, "motivo": datos.get("motivo", "medidas"),
                                                         "nombre": datos.get("nombre", ""), "pedido": datos.get("preferencia", "")},
                                     f"Turno de {datos.get('motivo', 'medidas')} para {datos.get('nombre')}: dijo «{datos.get('preferencia')}». "
                                     "Poné fecha y hora al confirmar.", datos["contacto"]))

    @staticmethod
    def _with_destino(a: Accion, destino: str) -> Accion:
        a.destino = destino
        return a

    def tick(self, ahora, ctx):
        dias = ctx.perfil.agenda.recordatorio_dias_antes
        objetivo = (ahora.date() + timedelta(days=dias)).isoformat()
        for t in ctx.datos.listar("turnos", recordado=False):
            if t["fecha"] <= objetivo and t["fecha"] >= ahora.date().isoformat():
                t["recordado"] = True
                ctx.datos.guardar("turnos", f"{t['fecha']} {t['hora']}", t)
                ctx.solicitar(Accion("enviar_recordatorio", {"fecha": t["fecha"], "hora": t["hora"], "motivo": t["motivo"]},
                                     f"Recordatorio a {t['nombre']}", t["contacto"]))

    def comando(self, nombre, datos, ctx):
        desde = ctx.hoy().isoformat()
        turnos = sorted((t for t in ctx.datos.listar("turnos") if t["fecha"] >= desde), key=lambda t: (t["fecha"], t["hora"]))
        if nombre == "turnos":
            return turnos
        if nombre == "calendario":
            cal: dict[str, list] = {}
            for t in turnos:
                cal.setdefault(t["fecha"], []).append(t)
            return cal
        return super().comando(nombre, datos, ctx)
