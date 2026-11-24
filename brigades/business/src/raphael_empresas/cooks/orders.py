"""Encargos: toma pedidos a medida paso a paso, sugiere el precio y lleva el estado de cada encargo.

Conversación (portada de `raphael_encargos` 0.1.0, que venía de Mi Tienda IA): prenda, ocasión, fecha (las fechas en
números se confirman en palabras), detalles, referencias, medidas o turno para medirse y nombre. Acepta varios datos
en un mismo mensaje. Una pregunta en el medio se la pasa a Atención (`ctx.consult`, misma brigada) y retoma donde
estaba; un reclamo en el medio también va a Atención, que lo deriva. Nunca promete precio ni fecha: deja el
presupuesto PENDIENTE de aprobación (`enviar_presupuesto`, etiquetas `external` e `irreversible`).

Publica: encargo.creado, encargo.presupuesto_enviado, encargo.estado_cambiado, turno.pedido.
Escucha: pago.confirmado (pasa a confirmado), conversacion.derivada (suelta el chat).
"""

from __future__ import annotations

import re
from datetime import timedelta

from raphael_core import Action, ActionError, Cook, Reply
from raphael_core.text_es import (
    RE_MONTH_IN_WORDS,
    clean,
    date_in_words,
    first_name,
    is_question,
    money,
    normalize,
    parse_date,
    short_date,
)

from .. import config as C
from ..pricing import suggest
from ..signals import ATTENTION, complaint

EXPIRES = timedelta(days=3)
STATUSES = ["presupuesto", "confirmado", "en_confeccion", "prueba", "listo", "entregado", "cancelado"]
ACTIVE = ("presupuesto", "confirmado", "en_confeccion", "prueba", "listo")
MAX_PRICE = 100_000_000

_ITEMS = (r"vestidos?|trajes?|sacos?|blazers?|polleras?|faldas?|pantalon\w*|camisas?|blusas?|tops?|corse\w*|corsets?|"
          r"enteritos?|monos?|tapados?|abrigos?|camperas?|conjuntos?|kimonos?|chalecos?|chaquetas?|capas?|batas?|tunicas?|bodys?|bikinis?|mallas?")
R_ITEM = re.compile(r"\b(" + _ITEMS + r")\b"
                    r"(?:\s+(?:de|para)\s+(novia|fiesta|gala|noche|egres\w+|bano|madrina|civil|15|quince))?"
                    r"(?:\s+(largo|larga|corto|corta|midi|sastre|entallad\w+|suelt\w+))?")
R_WANTS = re.compile(r"\ba medida\b|\bhac(e|en|es|er|erme|ermelo|ermela)\b|\bconfeccion\w*|\bencarg\w+|\bpresupuesto\b|"
                     r"\bcotiza\w*|\bquiero (un|una|que me)\b|\bnecesito (un|una)\b|\bme gustaria (un|una|hacer)\b")
OCCASIONS = [("casamiento", r"casamiento|boda|casorio|me caso|se casa"), ("15", r"\b15\b|quince|quinceanera"),
             ("egresados", r"egres\w+|graduac\w+|recibida|recibo"), ("civil", r"\bcivil\b"),
             ("fiesta", r"fiesta|gala|evento|cena"),
             ("bautismo", r"bautismo|bautizo"), ("comunion", r"comunion|confirmacion"), ("cumpleaños", r"cumple\w*"),
             ("trabajo", r"trabajo|oficina|uso diario|para todos los dias|diario")]
R_MEASURE = re.compile(r"\b(busto|pecho|cintura|cadera|largo|hombros?|espalda|brazos?|mangas?|tiro|contorno|altura|cuello|muslo|"
                       r"pierna|sisa|talle)\b\D{0,6}\d{2,3}")
R_NO_MEASURES = re.compile(r"\bno (las |me las )?(se|tengo|conozco|se cuales)\b|\bmedir(me|te)?\b|\bme mid(a|as|an|e|en)\b|"
                           r"\bmedida en persona\b|\ben persona\b|\bturno\b|\bprefiero (ir|pasar)\b|\bpaso a medir|"
                           r"\bno se medir|\bno se como")
R_NO = re.compile(r"^\s*(no|nop|ninguna|no tengo|nada|listo|eso es todo|no gracias|no, gracias)\b")
R_YES = re.compile(r"^\s*(si|sip|sii+|dale|exacto|correcto|ese|eso|asi es|perfecto|ok|okey|claro|confirmo)\b")
R_BYE = re.compile(r"\b(cancel\w+|ya no (quiero|lo necesito|hace falta)|no quiero( nada)?|dejalo|deja nomas|olvidate|"
                   r"me arrepenti)\b")
R_NO_RUSH = re.compile(r"\bsin apuro\b|\bno tengo fecha\b|\bcuando (este|puedas)\b|\bno hay apuro\b|\bno me corre\b")

QUESTION = {
    "prenda": "¿Qué prenda te gustaría que te haga? (vestido, traje, conjunto…)",
    "ocasion": "¿Para qué ocasión es? ✨",
    "fecha": "¿Para qué fecha lo necesitás? 📅",
    "fecha_otra": "Uy, perdón 😅 Decime el día y el mes en palabras, por ejemplo “20 de diciembre”.",
    "detalles": "Contame cómo te lo imaginás: tela, color, largo, estilo… Si no sabés, decime “lo que me recomiendes”.",
    "referencias": "¿Tenés fotos de referencia o algo que te guste? Mandalas por acá 📸 Si no, decime “no”.",
    "medidas": ("¿Sabés tus medidas? Si las tenés, pasame busto, cintura, cadera y largo (en cm). "
                "Si preferís que te las tomen en persona, decime “prefiero que me midan” 📏"),
    "turno": "¡Dale! ¿Qué días y horarios te quedan bien para pasar a medirte? Te confirmamos el turno 🗓️",
    "nombre": "Por último, ¿a nombre de quién lo anoto? 😊",
}


def _singular(w: str) -> str:
    return w[:-2] if w.endswith("ones") else w[:-1] if w.endswith("s") and not w.endswith("is") else w


def item_of(t: str) -> str:
    m = R_ITEM.search(t)
    if not m:
        return ""
    base, use, shape = m.groups()
    return " ".join([_singular(base)] + ([f"de {use}"] if use else []) + ([shape] if shape else []))


def occasion_of(t: str) -> str:
    return next((name for name, rx in OCCASIONS if re.search(rx, t)), "")


def name_of(text: str) -> str:
    s = re.sub(r"(?i)^\s*(hola[,!]?\s*)?(soy|me llamo|mi nombre es|a nombre de|anotalo a nombre de|anotalo como)\s+", "",
               text.strip())
    s = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ' -]", "", s).strip()
    return " ".join(w.capitalize() for w in s.split()[:4])


def wants_order(text: str) -> bool:
    t = normalize(text)
    if re.search(r"\ba medida\b", t):
        return True
    from_stock = re.search(r"\btalles?\b|\bstock\b|\bunidades\b|\b\d+\s+(" + _ITEMS + r")\b", t)   # "2 remeras talle M"
    return bool(R_ITEM.search(t) and R_WANTS.search(t)) and not from_stock


def number_from(data: dict):
    n = data.get("number", data.get("num"))
    try:
        return int(n)
    except (TypeError, ValueError):
        return n


class Orders(Cook):
    name = "encargos"
    version = "2.0.0"
    description = "Toma pedidos a medida, sugiere el presupuesto y lleva el estado de cada encargo."
    commands = {"listar": "Encargos activos (o todos con {'all': true})", "ver": "Un encargo por número {'number': n}",
                "estado": "Cambia el estado de un encargo {'number': n, 'status': 'en_confeccion'|'prueba'|'listo'|"
                          "'entregado'|'cancelado'}"}

    # --- estado de la conversación
    def _chat(self, contact: str, ctx) -> dict | None:
        d = ctx.data.get("chats", contact)
        if d is None:
            return None
        when = ctx.data.updated("chats", contact)
        if when and when < ctx.now() - EXPIRES:
            ctx.data.delete("chats", contact)
            return None
        return d

    def in_progress(self, msg, ctx):
        return self._chat(msg.contact, ctx) is not None

    def interest(self, msg, ctx):
        return 0.8 if wants_order(msg.text) else 0.0

    def _question(self, step: str, data: dict, ctx) -> str:
        if step == "confirmar_fecha":
            return f"Para confirmar: ¿lo necesitás para el {date_in_words(data['date'], ctx.today())}? (sí / no)"
        if step == "fecha" and data.get("date_rejected"):
            return QUESTION["fecha_otra"]
        return QUESTION[step]

    async def _to_attention(self, msg, ctx) -> Reply | None:
        if not ctx.has_cook(ATTENTION):
            return None
        return await ctx.consult(ATTENTION, msg)

    # --- conversación
    async def handle(self, msg, ctx):
        text, t = msg.text, normalize(msg.text)
        data = self._chat(msg.contact, ctx)
        new = data is None
        if new:
            if not wants_order(text):
                return None
            data = {"step": None, "refs": 0, "profile_name": msg.name}
        elif complaint(text):                                 # un reclamo en el medio: lo toma Atención y suelta el chat
            r = await self._to_attention(msg, ctx)
            if r is not None:
                return r
        elif R_BYE.search(t):
            ctx.data.delete("chats", msg.contact)
            return Reply("Dale, sin problema 😊 Cualquier cosa me escribís cuando quieras.")

        step = data.get("step")
        if msg.attachment:
            data["refs"] = data.get("refs", 0) + 1
            if step in (None, "referencias"):
                ctx.data.put("chats", msg.contact, {**data, "step": "referencias"})
                return Reply("¡Recibida! 📸 ¿Tenés alguna más? Si ya está, decime “listo”.")
        else:
            understood = self._absorb(data, step, text, t, ctx)
            if not understood and step is not None and is_question(text):
                r = await self._to_attention(msg, ctx)
                if ctx.data.get("chats", msg.contact) is None:
                    return r                                  # era un reclamo: Atención derivó y el chat ya se soltó
                ctx.data.put("chats", msg.contact, data)
                pre = (r.text + "\n\n") if r and r.text else ""
                return Reply(pre + self._question(step, data, ctx))

        nxt = self._next(data, ctx)
        if nxt is None:
            ctx.data.delete("chats", msg.contact)
            return self._close(msg, data, ctx)
        data["step"] = nxt
        ctx.data.put("chats", msg.contact, data)
        if new:
            return Reply("¡Hola! 😊 Qué lindo que quieras hacerte algo a medida. Te hago unas preguntitas para pasarle "
                         f"todo a {C.decider(ctx)} y que te arme el presupuesto.\n\n" + self._question(nxt, data, ctx))
        return Reply(self._question(nxt, data, ctx))

    def _absorb(self, data: dict, step: str | None, text: str, t: str, ctx) -> bool:
        """Guarda la respuesta al paso actual y, de yapa, cualquier otro dato que traiga el mensaje."""
        before = dict(data)
        today = ctx.today()
        p = item_of(t)
        if p and (not data.get("item") or (p.startswith(data["item"].split()[0]) and len(p) > len(data["item"]))):
            data["item"] = p
        if p and step in ("ocasion", "detalles") and not occasion_of(t) and len(t.split()) <= 5:
            return data != before
        if not data.get("occasion") and occasion_of(t):
            data["occasion"] = occasion_of(t)
        if "date" not in data or (data.get("date") is None and data.get("date_text")):
            f = parse_date(t, today)
            if f:
                data["date"] = f
                data["date_ok"] = bool(RE_MONTH_IN_WORDS.search(t))   # "12 de octubre" no tiene vuelta; "12/10" se confirma
                data.pop("date_text", None)
                if step not in (None, "fecha"):
                    return True
            elif R_NO_RUSH.search(t) and "date" not in data:
                data["date"] = None
        if not data.get("measures") and len(R_MEASURE.findall(t)) >= 2:
            data["measures"] = clean(text, 400)
        if step == "prenda" and not before.get("item") and len(t.split()) <= 12 and "?" not in text:
            data["item"] = data.get("item") or clean(text, 80)
        elif step == "ocasion" and not before.get("occasion") and "?" not in text:
            data["occasion"] = re.sub(r"(?i)^(es\s+)?(para|por)\s+(mi|el|la|un|una|los|las|lo de)?\s*", "",
                                      clean(text, 120)) or clean(text, 120)
        elif step == "fecha" and "date" not in before and "date" not in data and "?" not in text and \
                not (occasion_of(t) and not before.get("occasion")):
            data["date"] = None
            data["date_text"] = clean(text, 80)
        elif step == "confirmar_fecha":
            other = parse_date(t, today)
            if other:
                data["date"], data["date_ok"] = other, bool(RE_MONTH_IN_WORDS.search(t))
            elif R_YES.search(t):
                data["date_ok"] = True
            elif R_NO.search(t):
                data.pop("date", None)
                data.pop("date_ok", None)
                data["date_rejected"] = True
        elif step == "detalles" and "?" not in text:
            data["details"] = clean(text, 400)
        elif step == "referencias" and R_NO.search(t):
            data["refs_done"] = True
        elif step == "medidas":
            if "measures" not in before and not data.get("measures"):
                if R_NO_MEASURES.search(t) or R_NO.search(t):
                    data["measures"] = ""
                    data["wants_appointment"] = True
                elif re.search(r"\d{2,3}", t):
                    data["measures"] = clean(text, 400)
        elif step == "turno" and "?" not in text:
            data["appointment"] = clean(text, 160)
        elif step == "nombre" and "?" not in text:
            n = name_of(text)
            if n:
                data["name"] = n
        return data != before

    @staticmethod
    def _next(data: dict, ctx) -> str | None:
        asks = set(C.of(ctx).orders.required_steps)
        if not data.get("item"):
            return "prenda"
        if "ocasion" in asks and not data.get("occasion"):
            return "ocasion"
        if "fecha" in asks and "date" not in data:
            return "fecha"
        if data.get("date") and not data.get("date_ok"):
            return "confirmar_fecha"
        if "detalles" in asks and not data.get("details"):
            return "detalles"
        if "referencias" in asks and not data.get("refs_done") and "measures" not in data:
            return "referencias"
        if "medidas" in asks and "measures" not in data:
            return "medidas"
        if data.get("wants_appointment") and not data.get("appointment"):
            return "turno"
        if not data.get("name"):
            return "nombre"
        return None

    def _close(self, msg, data: dict, ctx) -> Reply:
        today = ctx.today()
        cfg = C.of(ctx)
        due = data.get("date")
        urgent = bool(due and due < (today + timedelta(days=cfg.orders.urgent_if_days_under)).isoformat())
        notes = [f"Ocasión: {data.get('occasion') or '-'}"]
        if data.get("details"):
            notes.append(f"Cómo lo imagina: {data['details']}")
        if data.get("refs"):
            notes.append(f"Mandó {data['refs']} foto(s) de referencia por {msg.channel}")
        if data.get("appointment"):
            notes.append(f"Turno para medirse: {data['appointment']} (a confirmar)")
        if urgent:
            notes.append(f"URGENTE: lo necesita para el {short_date(due, today)}; confirmar si se llega")
        if due is None:
            notes.append(f"Fecha: {data['date_text']}" if data.get("date_text") else "Sin fecha: no tiene apuro")
        occasion = data.get("occasion") or ""
        desc = data["item"] + (f" para {occasion}" if occasion and len(occasion.split()) <= 3 else "")
        num = ctx.shared.next("orders")
        s = suggest(cfg.orders, desc, data.get("details") or "")
        o = {"number": num, "client": data["name"], "description": desc, "due": due, "contact": msg.contact,
             "channel": msg.channel, "measures": data.get("measures") or "", "notes": "\n".join(notes), "urgent": urgent,
             "status": "presupuesto", "price": None, "deposit": None, "paid": 0,
             "suggested": s["price"] if s else None, "suggested_detail": s["detail"] if s else "",
             "estimated_days": s["days"] if s else None, "quote_sent": False,
             "created": ctx.now().isoformat(timespec="seconds")}
        ctx.shared.put("orders", num, o)
        ctx.publish("encargo.creado", {k: o[k] for k in ("number", "client", "description", "due", "contact", "urgent")})
        actions = [Action("enviar_presupuesto", {"number": num, "price": o["suggested"]},
                          f"Encargo #{num} de {o['client']}: {desc}"
                          + (f" — sugerido {money(o['suggested'])} ({o['suggested_detail']})" if s
                             else " — sin precio en tu tabla: ponelo vos")
                          + (" — URGENTE" if urgent else ""))]
        if data.get("appointment"):
            ctx.publish("turno.pedido", {"contact": msg.contact, "name": o["client"], "reason": "medidas",
                                         "preference": data["appointment"], "order": num})
        out = (f"¡Listo, {first_name(o['client'])}! 🧵 Ya le pasé todo a {C.decider(ctx)}. "
               "Te mandamos el presupuesto por acá apenas lo tenga.")
        if urgent:
            out += (f"\nComo lo necesitás para el {short_date(due, today)}, hay que confirmar si se llega con los tiempos; "
                    "te avisamos.")
        if data.get("appointment"):
            out += "\nSobre el turno para medirte, te confirmamos el día y horario. 📏"
        return Reply(out + f"\n(Tu número de encargo es el #{num})", actions)

    # --- acciones aprobadas
    def execute(self, action, ctx):
        if action.type == "enviar_presupuesto":
            o = ctx.shared.get("orders", number_from(action.data))
            if not o:
                raise ActionError("ese encargo no existe")
            try:
                price = float(action.data.get("price") or 0)
            except (TypeError, ValueError) as exc:
                raise ActionError("el precio tiene que ser un número") from exc
            if price <= 0:
                raise ActionError("falta el precio: aprobalo con {'price': monto}")
            if price > MAX_PRICE:
                raise ActionError("el precio es demasiado alto: revisalo")
            pct = C.of(ctx).payments.deposit_pct
            o.update(price=price, deposit=round(price * pct / 100, -2), quote_sent=True)
            ctx.shared.put("orders", o["number"], o)
            ctx.publish("encargo.presupuesto_enviado", {"number": o["number"], "contact": o["contact"], "client": o["client"],
                                                         "price": o["price"], "deposit": o["deposit"],
                                                         "description": o["description"]})
            return self._quote_message(o, ctx)
        if action.type == "cancelar_pedido":
            o = self._set_status(number_from(action.data), "cancelado", ctx)
            return f"Tu encargo #{o['number']} quedó cancelado. Cualquier cosa nos escribís 😊"
        raise ActionError(f"encargos no ejecuta '{action.type}'")

    @staticmethod
    def _quote_message(o: dict, ctx) -> str:
        c = C.of(ctx).payments
        name = first_name(o["client"])
        out = (f"¡Hola{' ' + name if name else ''}! 😊 Te paso el presupuesto de tu {o['description']} "
               f"(encargo #{o['number']}): {money(o['price'])}.\n")
        if o.get("deposit"):
            out += f"Para confirmarlo se pide una seña del {c.deposit_pct:g}% ({money(o['deposit'])})"
            if c.alias:
                out += f" por transferencia al alias {c.alias}" + (f" (a nombre de {c.holder})" if c.holder else "")
            out += ".\n"
        if o.get("estimated_days"):
            out += f"Estaría listo en unos {o['estimated_days']} días desde que se confirma. "
        return out + "Cuando transfieras, avisame por acá 🧵"

    # --- estados
    def _set_status(self, num, status: str, ctx) -> dict:
        if status not in STATUSES:
            raise ActionError(f"estado desconocido: {status}. Válidos: {', '.join(STATUSES)}")
        o = ctx.shared.get("orders", num)
        if not o:
            raise ActionError(f"no existe el encargo #{num}")
        if o["status"] == status:
            return o
        o["status"] = status
        ctx.shared.put("orders", o["number"], o)
        ctx.publish("encargo.estado_cambiado", {"number": o["number"], "status": status, "contact": o["contact"],
                                                 "client": o["client"], "description": o["description"],
                                                 "channel": o["channel"]})
        return o

    def on_event(self, event, data, ctx):
        if event == "pago.confirmado" and data.get("number"):
            o = ctx.shared.get("orders", data["number"])
            if o:
                o["paid"] = float(o.get("paid") or 0) + float(data.get("amount") or 0)
                ctx.shared.put("orders", o["number"], o)
                if o["status"] == "presupuesto":
                    self._set_status(o["number"], "confirmado", ctx)
        elif event == "conversacion.derivada" and data.get("contact"):
            ctx.data.delete("chats", data["contact"])

    def command(self, name, data, ctx):
        if name == "listar":
            every = ctx.shared.list("orders")
            return every if (data.get("all") or data.get("todos")) else [o for o in every if o["status"] in ACTIVE]
        if name == "ver":
            o = ctx.shared.get("orders", number_from(data))
            if not o:
                raise ActionError(f"no existe el encargo #{number_from(data)}")
            return o
        if name == "estado":
            return self._set_status(number_from(data), str(data.get("status") or data.get("estado") or ""), ctx)
        return super().command(name, data, ctx)
