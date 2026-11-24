"""Brigada Encargos: toma pedidos a medida paso a paso, sugiere el precio y lleva el estado de cada encargo.

Conversación (portada de Mi Tienda IA `app/recepcion.py`): prenda, ocasión, fecha (las fechas en
números se confirman en palabras), detalles, referencias, medidas o turno para medirse y nombre.
Acepta varios datos en un mismo mensaje. Una pregunta en el medio se la pasa a Atención (vía el
harness) y retoma donde estaba. Nunca promete precio ni fecha: deja el presupuesto PENDIENTE
de aprobación de la dueña (`enviar_presupuesto`).

Eventos que publica: encargo.creado, encargo.presupuesto_enviado, encargo.estado_cambiado, turno.pedido.
Eventos que escucha: pago.confirmado (pasa a confirmado), conversacion.derivada (suelta el chat).
"""

from __future__ import annotations

import re
from datetime import timedelta

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta
from raphael_harness.texto import (R_MES_EN_LETRAS, es_pregunta, fecha_corta, fecha_en_palabras, limpio, normalizar,
                                   parse_fecha, plata, primer_nombre)

from . import __version__
from .precios import sugerir

VENCE = timedelta(days=3)
ESTADOS = ["presupuesto", "confirmado", "en_confeccion", "prueba", "listo", "entregado", "cancelado"]
ACTIVOS = ("presupuesto", "confirmado", "en_confeccion", "prueba", "listo")

_PRENDAS = (r"vestidos?|trajes?|sacos?|blazers?|polleras?|faldas?|pantalon\w*|camisas?|blusas?|tops?|corse\w*|corsets?|enteritos?|"
            r"monos?|tapados?|abrigos?|camperas?|conjuntos?|kimonos?|chalecos?|chaquetas?|capas?|batas?|tunicas?|bodys?|bikinis?|mallas?")
R_PRENDA = re.compile(r"\b(" + _PRENDAS + r")\b(?:\s+(?:de|para)\s+(novia|fiesta|gala|noche|egres\w+|bano|madrina|civil|15|quince))?"
                      r"(?:\s+(largo|larga|corto|corta|midi|sastre|entallad\w+|suelt\w+))?")
R_QUIERE = re.compile(r"\ba medida\b|\bhac(e|en|es|er|erme|ermelo|ermela)\b|\bconfeccion\w*|\bencarg\w+|\bpresupuesto\b|\bcotiza\w*|"
                      r"\bquiero (un|una|que me)\b|\bnecesito (un|una)\b|\bme gustaria (un|una|hacer)\b")
OCASIONES = [("casamiento", r"casamiento|boda|casorio|me caso|se casa"), ("15", r"\b15\b|quince|quinceanera"),
             ("egresados", r"egres\w+|graduac\w+|recibida|recibo"), ("civil", r"\bcivil\b"), ("fiesta", r"fiesta|gala|evento|cena"),
             ("bautismo", r"bautismo|bautizo"), ("comunion", r"comunion|confirmacion"), ("cumpleaños", r"cumple\w*"),
             ("trabajo", r"trabajo|oficina|uso diario|para todos los dias|diario")]
R_MEDIDA = re.compile(r"\b(busto|pecho|cintura|cadera|largo|hombros?|espalda|brazos?|mangas?|tiro|contorno|altura|cuello|muslo|pierna|sisa|talle)\b\D{0,6}\d{2,3}")
R_SIN_MEDIDAS = re.compile(r"\bno (las |me las )?(se|tengo|conozco|se cuales)\b|\bmedir(me|te)?\b|\bme mid(a|as|an|e|en)\b|\bmedida en persona\b|"
                           r"\ben persona\b|\bturno\b|\bprefiero (ir|pasar)\b|\bpaso a medir|\bno se medir|\bno se como")
R_NO = re.compile(r"^\s*(no|nop|ninguna|no tengo|nada|listo|eso es todo|no gracias|no, gracias)\b")
R_SI = re.compile(r"^\s*(si|sip|sii+|dale|exacto|correcto|ese|eso|asi es|perfecto|ok|okey|claro|confirmo)\b")
R_CHAU = re.compile(r"\b(cancel\w+|ya no (quiero|lo necesito|hace falta)|no quiero( nada)?|dejalo|deja nomas|olvidate|me arrepenti)\b")
R_SIN_APURO = re.compile(r"\bsin apuro\b|\bno tengo fecha\b|\bcuando (este|puedas)\b|\bno hay apuro\b|\bno me corre\b")

PREGUNTA = {
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


def prenda_de(t: str) -> str:
    m = R_PRENDA.search(t)
    if not m:
        return ""
    base, uso, forma = m.groups()
    return " ".join([_singular(base)] + ([f"de {uso}"] if uso else []) + ([forma] if forma else []))


def ocasion_de(t: str) -> str:
    return next((nombre for nombre, rx in OCASIONES if re.search(rx, t)), "")


def nombre_de(texto: str) -> str:
    s = re.sub(r"(?i)^\s*(hola[,!]?\s*)?(soy|me llamo|mi nombre es|a nombre de|anotalo a nombre de|anotalo como)\s+", "", texto.strip())
    s = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ' -]", "", s).strip()
    return " ".join(w.capitalize() for w in s.split()[:4])


def quiere_encargo(texto: str) -> bool:
    t = normalizar(texto)
    if re.search(r"\ba medida\b", t):
        return True
    de_stock = re.search(r"\btalles?\b|\bstock\b|\bunidades\b|\b\d+\s+(" + _PRENDAS + r")\b", t)   # "2 remeras talle M"
    return bool(R_PRENDA.search(t) and R_QUIERE.search(t)) and not de_stock


class Encargos(Brigada):
    nombre = "encargos"
    version = __version__
    descripcion = "Toma pedidos a medida, sugiere el presupuesto y lleva el estado de cada encargo."
    acciones = {"enviar_presupuesto": Nivel.APROBACION, "cancelar_pedido": Nivel.APROBACION}
    eventos = ("pago.confirmado", "conversacion.derivada")
    comandos = {"listar": "Encargos activos (o todos con {'todos': true})", "ver": "Un encargo por número {'num': n}",
                "estado": "Cambia el estado {'num': n, 'estado': 'en_confeccion'|'prueba'|'listo'|'entregado'|'cancelado'}"}

    # ------------------------------------------------------------ estado de la conversación
    def _chat(self, contacto: str, ctx) -> dict | None:
        d = ctx.datos.obtener("chats", contacto)
        if d is None:
            return None
        cuando = ctx.datos.actualizado("chats", contacto)
        if cuando and cuando < ctx.ahora() - VENCE:
            ctx.datos.borrar("chats", contacto)
            return None
        return d

    def en_curso(self, msg, ctx):
        return self._chat(msg.contacto, ctx) is not None

    def interes(self, msg, ctx):
        return 0.8 if quiere_encargo(msg.texto) else 0.0

    def _pregunta(self, paso: str, data: dict, ctx) -> str:
        if paso == "confirmar_fecha":
            return f"Para confirmar: ¿lo necesitás para el {fecha_en_palabras(data['fecha'], ctx.hoy())}? (sí / no)"
        if paso == "fecha" and data.get("fecha_rechazada"):
            return PREGUNTA["fecha_otra"]
        return PREGUNTA[paso]

    # ------------------------------------------------------------ conversación
    def atender(self, msg, ctx):
        texto, t = msg.texto, normalizar(msg.texto)
        data = self._chat(msg.contacto, ctx)
        nueva = data is None
        if nueva:
            if not quiere_encargo(texto):
                return None
            data = {"paso": None, "refs": 0, "perfil": msg.nombre}
        elif R_CHAU.search(t):
            ctx.datos.borrar("chats", msg.contacto)
            return Respuesta("Dale, sin problema 😊 Cualquier cosa me escribís cuando quieras.")

        paso = data.get("paso")
        if msg.adjunto:
            data["refs"] = data.get("refs", 0) + 1
            if paso in (None, "referencias"):
                ctx.datos.guardar("chats", msg.contacto, {**data, "paso": "referencias"})
                return Respuesta("¡Recibida! 📸 ¿Tenés alguna más? Si ya está, decime “listo”.")
        else:
            entendido = self._absorber(data, paso, texto, t, ctx)
            if not entendido and paso is not None and es_pregunta(texto):
                r = ctx.consultar("atencion", msg)
                if ctx.datos.obtener("chats", msg.contacto) is None:
                    return r                                 # era un reclamo: atención derivó y el chat ya se soltó
                ctx.datos.guardar("chats", msg.contacto, data)
                pre = (r.texto + "\n\n") if r and r.texto else ""
                return Respuesta(pre + self._pregunta(paso, data, ctx))

        siguiente = self._siguiente(data, ctx)
        if siguiente is None:
            ctx.datos.borrar("chats", msg.contacto)
            return self._cerrar(msg, data, ctx)
        data["paso"] = siguiente
        ctx.datos.guardar("chats", msg.contacto, data)
        if nueva:
            return Respuesta("¡Hola! 😊 Qué lindo que quieras hacerte algo a medida. Te hago unas preguntitas para pasarle "
                             f"todo a {ctx.perfil.quien_decide} y que te arme el presupuesto.\n\n" + self._pregunta(siguiente, data, ctx))
        return Respuesta(self._pregunta(siguiente, data, ctx))

    def _absorber(self, data: dict, paso: str | None, texto: str, t: str, ctx) -> bool:
        """Guarda la respuesta al paso actual y, de yapa, cualquier otro dato que traiga el mensaje."""
        antes = dict(data)
        hoy = ctx.hoy()
        p = prenda_de(t)
        if p and (not data.get("prenda") or (p.startswith(data["prenda"].split()[0]) and len(p) > len(data["prenda"]))):
            data["prenda"] = p
        if p and paso in ("ocasion", "detalles") and not ocasion_de(t) and len(t.split()) <= 5:
            return data != antes
        if not data.get("ocasion") and ocasion_de(t):
            data["ocasion"] = ocasion_de(t)
        if "fecha" not in data or (data.get("fecha") is None and data.get("fecha_texto")):
            f = parse_fecha(t, hoy)
            if f:
                data["fecha"] = f
                data["fecha_ok"] = bool(R_MES_EN_LETRAS.search(t))   # "12 de octubre" no tiene vuelta; "12/10" se confirma
                data.pop("fecha_texto", None)
                if paso not in (None, "fecha"):
                    return True
            elif R_SIN_APURO.search(t) and "fecha" not in data:
                data["fecha"] = None
        if not data.get("medidas") and len(R_MEDIDA.findall(t)) >= 2:
            data["medidas"] = limpio(texto, 400)
        if paso == "prenda" and not antes.get("prenda") and len(t.split()) <= 12 and "?" not in texto:
            data["prenda"] = data.get("prenda") or limpio(texto, 80)
        elif paso == "ocasion" and not antes.get("ocasion") and "?" not in texto:
            data["ocasion"] = re.sub(r"(?i)^(es\s+)?(para|por)\s+(mi|el|la|un|una|los|las|lo de)?\s*", "", limpio(texto, 120)) or limpio(texto, 120)
        elif paso == "fecha" and "fecha" not in antes and "fecha" not in data and "?" not in texto and not (ocasion_de(t) and not antes.get("ocasion")):
            data["fecha"] = None
            data["fecha_texto"] = limpio(texto, 80)
        elif paso == "confirmar_fecha":
            otra = parse_fecha(t, hoy)
            if otra:
                data["fecha"], data["fecha_ok"] = otra, bool(R_MES_EN_LETRAS.search(t))
            elif R_SI.search(t):
                data["fecha_ok"] = True
            elif R_NO.search(t):
                data.pop("fecha", None)
                data.pop("fecha_ok", None)
                data["fecha_rechazada"] = True
        elif paso == "detalles" and "?" not in texto:
            data["detalles"] = limpio(texto, 400)
        elif paso == "referencias" and R_NO.search(t):
            data["refs_listo"] = True
        elif paso == "medidas":
            if "medidas" not in antes and not data.get("medidas"):
                if R_SIN_MEDIDAS.search(t) or R_NO.search(t):
                    data["medidas"] = ""
                    data["quiere_turno"] = True
                elif re.search(r"\d{2,3}", t):
                    data["medidas"] = limpio(texto, 400)
        elif paso == "turno" and "?" not in texto:
            data["turno"] = limpio(texto, 160)
        elif paso == "nombre" and "?" not in texto:
            n = nombre_de(texto)
            if n:
                data["nombre"] = n
        return data != antes

    @staticmethod
    def _siguiente(data: dict, ctx) -> str | None:
        pide = set(ctx.perfil.encargos.datos_obligatorios)
        if not data.get("prenda"):
            return "prenda"
        if "ocasion" in pide and not data.get("ocasion"):
            return "ocasion"
        if "fecha" in pide and "fecha" not in data:
            return "fecha"
        if data.get("fecha") and not data.get("fecha_ok"):
            return "confirmar_fecha"
        if "detalles" in pide and not data.get("detalles"):
            return "detalles"
        if "referencias" in pide and not data.get("refs_listo") and "medidas" not in data:
            return "referencias"
        if "medidas" in pide and "medidas" not in data:
            return "medidas"
        if data.get("quiere_turno") and not data.get("turno"):
            return "turno"
        if not data.get("nombre"):
            return "nombre"
        return None

    def _cerrar(self, msg, data: dict, ctx) -> Respuesta:
        hoy = ctx.hoy()
        fecha = data.get("fecha")
        plazo = ctx.perfil.encargos.urgente_si_dias_menor_a
        urgente = bool(fecha and fecha < (hoy + timedelta(days=plazo)).isoformat())
        notas = [f"Ocasión: {data.get('ocasion') or '-'}"]
        if data.get("detalles"):
            notas.append(f"Cómo lo imagina: {data['detalles']}")
        if data.get("refs"):
            notas.append(f"Mandó {data['refs']} foto(s) de referencia por {msg.canal}")
        if data.get("turno"):
            notas.append(f"Turno para medirse: {data['turno']} (a confirmar)")
        if urgente:
            notas.append(f"URGENTE: lo necesita para el {fecha_corta(fecha, hoy)}; confirmar si se llega")
        if fecha is None:
            notas.append(f"Fecha: {data['fecha_texto']}" if data.get("fecha_texto") else "Sin fecha: no tiene apuro")
        ocasion = data.get("ocasion") or ""
        desc = data["prenda"] + (f" para {ocasion}" if ocasion and len(ocasion.split()) <= 3 else "")
        num = ctx.datos.siguiente("encargos")
        s = sugerir(ctx.perfil.encargos, desc, data.get("detalles") or "")
        e = {"num": num, "cliente": data["nombre"], "descripcion": desc, "entrega": fecha, "contacto": msg.contacto,
             "origen": msg.canal, "medidas": data.get("medidas") or "", "notas": "\n".join(notas), "urgente": urgente,
             "estado": "presupuesto", "precio": None, "sena": None, "pagado": 0,
             "sugerido": s["precio"] if s else None, "sugerido_detalle": s["detalle"] if s else "",
             "dias_estimados": s["dias"] if s else None, "presupuesto_enviado": False,
             "creado": ctx.ahora().isoformat(timespec="seconds")}
        ctx.datos.guardar("encargos", num, e)
        ctx.publicar("encargo.creado", {k: e[k] for k in ("num", "cliente", "descripcion", "entrega", "contacto", "urgente")})
        acciones = [Accion("enviar_presupuesto", {"num": num, "precio": e["sugerido"]},
                           f"Encargo #{num} de {e['cliente']}: {desc}"
                           + (f" — sugerido {plata(e['sugerido'])} ({e['sugerido_detalle']})" if s else " — sin precio en tu tabla: ponelo vos")
                           + (" — URGENTE" if urgente else ""))]
        if data.get("turno"):
            ctx.publicar("turno.pedido", {"contacto": msg.contacto, "nombre": e["cliente"], "motivo": "medidas",
                                          "preferencia": data["turno"], "encargo": num})
        out = (f"¡Listo, {primer_nombre(e['cliente'])}! 🧵 Ya le pasé todo a {ctx.perfil.quien_decide}. "
               "Te mandamos el presupuesto por acá apenas lo tenga.")
        if urgente:
            out += f"\nComo lo necesitás para el {fecha_corta(fecha, hoy)}, hay que confirmar si se llega con los tiempos; te avisamos."
        if data.get("turno"):
            out += "\nSobre el turno para medirte, te confirmamos el día y horario. 📏"
        return Respuesta(out + f"\n(Tu número de encargo es el #{num})", acciones)

    # ------------------------------------------------------------ acciones aprobadas
    def ejecutar(self, accion, ctx):
        if accion.tipo == "enviar_presupuesto":
            e = ctx.datos.obtener("encargos", accion.datos.get("num"))
            if not e:
                raise ErrorDeAccion("ese encargo no existe")
            precio = accion.datos.get("precio")
            if not precio or float(precio) <= 0:
                raise ErrorDeAccion("falta el precio: aprobalo con {'precio': monto}")
            if float(precio) > 100_000_000:
                raise ErrorDeAccion("el precio es demasiado alto: revisalo")
            pct = ctx.perfil.cobros.sena_pct
            e.update(precio=float(precio), sena=round(float(precio) * pct / 100, -2), presupuesto_enviado=True)
            ctx.datos.guardar("encargos", e["num"], e)
            ctx.publicar("encargo.presupuesto_enviado", {"num": e["num"], "contacto": e["contacto"], "cliente": e["cliente"],
                                                         "precio": e["precio"], "sena": e["sena"], "descripcion": e["descripcion"]})
            return self._mensaje_presupuesto(e, ctx)
        if accion.tipo == "cancelar_pedido":
            e = self._cambiar_estado(accion.datos.get("num"), "cancelado", ctx)
            return f"Tu encargo #{e['num']} quedó cancelado. Cualquier cosa nos escribís 😊"
        raise ErrorDeAccion(f"encargos no ejecuta '{accion.tipo}'")

    @staticmethod
    def _mensaje_presupuesto(e: dict, ctx) -> str:
        c = ctx.perfil.cobros
        nombre = primer_nombre(e["cliente"])
        out = (f"¡Hola{' ' + nombre if nombre else ''}! 😊 Te paso el presupuesto de tu {e['descripcion']} "
               f"(encargo #{e['num']}): {plata(e['precio'])}.\n")
        if e.get("sena"):
            out += f"Para confirmarlo se pide una seña del {c.sena_pct:g}% ({plata(e['sena'])})"
            if c.alias:
                out += f" por transferencia al alias {c.alias}" + (f" (a nombre de {c.titular})" if c.titular else "")
            out += ".\n"
        if e.get("dias_estimados"):
            out += f"Estaría listo en unos {e['dias_estimados']} días desde que se confirma. "
        return out + "Cuando transfieras, avisame por acá 🧵"

    # ------------------------------------------------------------ estados
    def _cambiar_estado(self, num, estado: str, ctx) -> dict:
        if estado not in ESTADOS:
            raise ErrorDeAccion(f"estado desconocido: {estado}. Válidos: {ESTADOS}")
        e = ctx.datos.obtener("encargos", num)
        if not e:
            raise ErrorDeAccion(f"no existe el encargo #{num}")
        if e["estado"] == estado:
            return e
        e["estado"] = estado
        ctx.datos.guardar("encargos", e["num"], e)
        ctx.publicar("encargo.estado_cambiado", {"num": e["num"], "estado": estado, "contacto": e["contacto"],
                                                  "cliente": e["cliente"], "descripcion": e["descripcion"], "origen": e["origen"]})
        return e

    def al_evento(self, evento, datos, ctx):
        if evento == "pago.confirmado" and datos.get("num"):
            e = ctx.datos.obtener("encargos", datos["num"])
            if e:
                e["pagado"] = float(e.get("pagado") or 0) + float(datos.get("monto") or 0)
                ctx.datos.guardar("encargos", e["num"], e)
                if e["estado"] == "presupuesto":
                    self._cambiar_estado(e["num"], "confirmado", ctx)
        elif evento == "conversacion.derivada" and datos.get("contacto"):
            ctx.datos.borrar("chats", datos["contacto"])

    def comando(self, nombre, datos, ctx):
        if nombre == "listar":
            todos = ctx.datos.listar("encargos")
            return todos if datos.get("todos") else [e for e in todos if e["estado"] in ACTIVOS]
        if nombre == "ver":
            e = ctx.datos.obtener("encargos", datos.get("num"))
            if not e:
                raise ErrorDeAccion(f"no existe el encargo #{datos.get('num')}")
            return e
        if nombre == "estado":
            return self._cambiar_estado(datos.get("num"), datos.get("estado", ""), ctx)
        return super().comando(nombre, datos, ctx)
