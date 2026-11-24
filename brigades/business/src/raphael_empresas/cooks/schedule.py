"""Agenda: turnos de prueba, medidas y retiro.

- El cliente pide un turno -> el bot pregunta qué día le queda bien (ofrece las franjas de la config).
- Con el día (y la hora si la dice) -> `confirmar_turno` PENDIENTE: la dueña confirma o propone otro.
- Al confirmar: no permite dos turnos el mismo día y hora; el cliente recibe la confirmación.
- `tick`: recordatorio automático `reminder_days_before` días antes (`enviar_recordatorio`, automático, `external`).
- Escucha `turno.pedido` (lo publica Encargos cuando alguien prefiere que la midan).
Portado de `raphael_agenda` 0.1.0 (Empresas 0.4).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from raphael_core import Action, ActionError, Cook, Reply
from raphael_core.text_es import clean, date_in_words, first_name, normalize, parse_date, parse_time

from .. import config as C
from ..signals import ATTENTION, complaint

R_APPOINTMENT = re.compile(r"\b(turno|probarme|probar(lo|la)?|prueba|medirme|me midan|tomar (las )?medidas|"
                           r"pasar a (buscar|retirar|probar)|retirar(lo|la)?|cuando (puedo|paso)|puedo (ir|pasar))\b")
REASONS = [("prueba", r"prob"), ("medidas", r"medi|medidas"), ("retiro", r"retir|buscar")]


def reason_of(t: str) -> str:
    return next((m for m, rx in REASONS if re.search(rx, t)), "turno")


class Schedule(Cook):
    name = "agenda"
    version = "2.0.0"
    description = "Pide turnos al cliente, los deja para que la dueña los confirme y manda recordatorios."
    commands = {"turnos": "Turnos confirmados desde hoy", "calendario": "Turnos confirmados agrupados por fecha"}

    def in_progress(self, msg, ctx):
        return ctx.data.get("chats", msg.contact) is not None

    def interest(self, msg, ctx):
        return 0.7 if R_APPOINTMENT.search(normalize(msg.text)) else 0.0

    def _offer(self, ctx) -> str:
        slots = C.of(ctx).schedule.slots
        return "¿Qué día y horario te queda mejor? 🗓️" + (f" Tenemos: {', '.join(slots)}." if slots else "")

    async def handle(self, msg, ctx):
        t = normalize(msg.text)
        chat = ctx.data.get("chats", msg.contact)
        if chat is None:
            if not R_APPOINTMENT.search(t):
                return None
            chat = {"reason": reason_of(t), "name": msg.name}
        elif complaint(msg.text) and ctx.has_cook(ATTENTION):     # un reclamo en el medio: lo toma Atención
            ctx.data.delete("chats", msg.contact)
            r = await ctx.consult(ATTENTION, msg)
            if r is not None:
                return r
        when = parse_date(t, ctx.today())
        if not when:
            ctx.data.put("chats", msg.contact, chat)
            return Reply(self._offer(ctx))
        ctx.data.delete("chats", msg.contact)
        return Reply(f"¡Genial! Le paso tu pedido a {C.decider(ctx)} y te confirmamos el turno por acá 😊",
                     [self._request(msg.contact, chat.get("name") or msg.name, chat["reason"], when, parse_time(t),
                                    clean(msg.text, 160), ctx)])

    def _request(self, contact, name, reason, when, hour, text, ctx) -> Action:
        words = date_in_words(when, ctx.today()) + (f" a las {hour}" if hour else " (hora a definir)")
        return Action("confirmar_turno", {"date": when, "time": hour, "reason": reason, "name": name, "request": text},
                      f"Turno de {reason} para {name or contact}: {words}. Confirmá (podés cambiar fecha u hora).",
                      contact)

    def execute(self, action, ctx):
        if action.type == "confirmar_turno":
            d = action.data
            if not d.get("date") or not d.get("time"):
                raise ActionError("falta la fecha o la hora: aprobalo con {'date': 'AAAA-MM-DD', 'time': 'HH:MM'}")
            try:
                date.fromisoformat(d["date"])
            except (TypeError, ValueError) as exc:
                raise ActionError("la fecha tiene que ser AAAA-MM-DD") from exc
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(d["time"])):
                raise ActionError("la hora tiene que ser HH:MM")
            key = f"{d['date']} {d['time']}"
            if ctx.shared.get("appointments", key):
                raise ActionError(f"ya hay un turno el {key}: elegí otro horario")
            ctx.shared.put("appointments", key, {"date": d["date"], "time": d["time"], "reason": d.get("reason", "turno"),
                                                 "name": d.get("name", ""), "contact": action.target, "reminded": False})
            ctx.publish("turno.confirmado", {"date": d["date"], "time": d["time"], "contact": action.target,
                                             "reason": d.get("reason", "turno")})
            name = first_name(d.get("name", ""))
            return (f"¡Listo{', ' + name if name else ''}! Te esperamos el {date_in_words(d['date'], ctx.today())} "
                    f"a las {d['time']} para la {d.get('reason', 'cita')} 😊")
        if action.type == "enviar_recordatorio":
            d = action.data
            return (f"¡Hola! Te recordamos tu turno de {d.get('reason', 'cita')} el {date_in_words(d['date'], ctx.today())} "
                    f"a las {d['time']} 🗓️ Si no podés venir, avisanos por acá.")
        raise ActionError(f"agenda no ejecuta '{action.type}'")

    def on_event(self, event, data, ctx):
        if event != "turno.pedido" or not data.get("contact"):
            return
        pref = data.get("preference", "")
        t = normalize(pref)
        when = parse_date(t, ctx.today())
        reason = data.get("reason", "medidas")
        if when:
            ctx.request(self._request(data["contact"], data.get("name", ""), reason, when, parse_time(t), pref, ctx))
        else:
            ctx.request(Action("confirmar_turno", {"date": None, "time": None, "reason": reason,
                                                   "name": data.get("name", ""), "request": pref},
                               f"Turno de {reason} para {data.get('name')}: dijo «{pref}». Poné fecha y hora al confirmar.",
                               data["contact"]))

    def tick(self, now, ctx):
        days = C.of(ctx).schedule.reminder_days_before
        target = (now.date() + timedelta(days=days)).isoformat()
        for a in ctx.shared.list("appointments", reminded=False):
            if now.date().isoformat() <= a["date"] <= target:
                a["reminded"] = True
                ctx.shared.put("appointments", f"{a['date']} {a['time']}", a)
                ctx.request(Action("enviar_recordatorio", {"date": a["date"], "time": a["time"], "reason": a["reason"]},
                                   f"Recordatorio a {a['name']}", a["contact"]))

    def upcoming(self, ctx) -> list[dict]:
        since = ctx.today().isoformat()
        return sorted((a for a in ctx.shared.list("appointments") if a["date"] >= since),
                      key=lambda a: (a["date"], a["time"]))

    def command(self, name, data, ctx):
        if name == "turnos":
            return self.upcoming(ctx)
        if name == "calendario":
            cal: dict[str, list] = {}
            for a in self.upcoming(ctx):
                cal.setdefault(a["date"], []).append(a)
            return cal
        return super().command(name, data, ctx)
