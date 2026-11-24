"""El orquestador como secretario: le cuenta a la dueña qué hay para hoy, qué conviene hacer primero y,
cuando algo se le escapó al bot, le da el contexto y las salidas posibles.

Todo se hace con reglas (se puede auditar y no inventa nada). La IA, si el plan la incluye, solo ayuda
a resumir una conversación y a entender frases libres; nunca decide qué es urgente.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from raphael_harness import Charla
from raphael_harness.texto import fecha_corta, limpio, normalizar, plata

MAX_LISTA = 8

R_PRIMERO = re.compile(r"\b(cual|cuales)\b.*\b(primero|empiezo|hago|recomiendas|aconsejas|conviene)\b|por (cual|donde) (empiezo|arranco|arrancamos|empezamos)|"
                       r"\b(recomendas|recomiendas|aconsejas|prioridad|mas urgente|lo mas importante)\b|que (hago|hacemos) primero")
R_SIGUIENTE = re.compile(r"\b(y despues|despues de esa|siguiente|la que sigue|y luego|que mas)\b|y la otra\b")
R_HOY = re.compile(r"\b(buen(os|as)? ?(dias?|tardes|noches)|hola|buenas|que tareas|que (hay|tenemos|tengo|queda|falta)|resumen|como estamos|"
                   r"pendientes|tareas|agenda de hoy|que onda|empecemos|arranquemos)\b")
R_GRACIAS = re.compile(r"\b(gracias|genial|perfecto|dale|listo|ok|buenisimo|excelente)\b")
R_NUMERO = re.compile(r"(?:\b(?:la|el|numero|nro|n|tarea|punto|#)\s*)?\b(\d{1,2})\b")
ORDINALES = {"primera": 1, "primero": 1, "segunda": 2, "segundo": 2, "tercera": 3, "tercero": 3, "cuarta": 4, "cuarto": 4,
             "quinta": 5, "quinto": 5, "sexta": 6, "sexto": 6, "septima": 7, "octava": 8}
R_DETALLE = re.compile(r"\b(contame|decime|detalle|detalles|explicame|mostrame|abri|abrime|ver|veamos|que pasa con|de que se trata|esa|a ver)\b")


# ------------------------------------------------------------------ las tareas del día
def _fecha(v) -> date | None:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _horas(desde: str | None, ahora: datetime) -> float:
    try:
        return max(0.0, (ahora - datetime.fromisoformat(desde)).total_seconds() / 3600)
    except (TypeError, ValueError):
        return 0.0


def _hace(horas: float) -> str:
    if horas < 1:
        return "hace un rato"
    if horas < 48:
        return f"hace {int(horas)} h"
    return f"hace {int(horas // 24)} días"


BONUS_TIPO = {"derivar_humano": (15, "es un cliente que pidió hablar con una persona"),
              "confirmar_pago": (15, "es plata que está esperando tu confirmación"),
              "enviar_presupuesto": (10, "hay un cliente esperando el precio"),
              "responder_duda": (5, "hay un cliente esperando respuesta"),
              "confirmar_turno": (5, "hay un turno por confirmar")}


def _de_pendientes(ctx, ahora: datetime) -> list[dict]:
    out = []
    for p in ctx.pendientes():
        a = p["accion"]
        tipo = a["tipo"]
        puntaje = 60 if p["nivel"] == "humano" else 40
        motivos = []
        extra, porque = BONUS_TIPO.get(tipo, (0, ""))
        puntaje += extra
        if porque:
            motivos.append(porque)
        h = _horas(p.get("creado"), ahora)
        if h >= 1:
            puntaje += min(20, h * 1.5)
            motivos.append(f"lo dejaste esperando {_hace(h)}")
        num = (a.get("datos") or {}).get("num")
        if tipo == "enviar_presupuesto" and num:
            e = ctx.consultar_datos("encargos", "ver", {"num": num}) or {}
            if e.get("urgente"):
                puntaje += 10
                motivos.append("el pedido es urgente")
        out.append({"tipo": tipo, "origen": "pendiente", "titulo": a.get("resumen") or tipo, "detalle": "",
                    "puntaje": round(puntaje), "motivo": _unir(motivos) or "espera tu decisión",
                    "pendiente": p["id"], "contacto": a.get("destino"), "encargo": num})
    return out


def _de_encargos(ctx, hoy: date) -> list[dict]:
    out = []
    for e in ctx.consultar_datos("encargos", "listar") or []:
        if e["estado"] == "presupuesto":
            continue                                           # ese ya aparece como pendiente de aprobar
        entrega = _fecha(e.get("entrega"))
        dias = (entrega - hoy).days if entrega else None
        motivos, puntaje = [], 0
        if dias is not None and dias < 0:
            puntaje, motivos = 90, [f"se pasó la fecha de entrega hace {-dias} día{'s' if dias < -1 else ''}"]
        elif dias is not None and dias <= 3:
            puntaje = 55 + (3 - dias) * 8
            motivos = ["se entrega hoy" if dias == 0 else "se entrega mañana" if dias == 1 else f"se entrega en {dias} días"]
        elif dias is not None and dias <= 7:
            puntaje, motivos = 35, [f"se entrega en {dias} días"]
        if e["estado"] == "listo":
            puntaje = max(puntaje, 45) + 5
            motivos.append("está listo para entregar")
        if not puntaje:
            continue
        if e.get("urgente"):
            puntaje += 10
            motivos.append("era un pedido urgente")
        out.append({"tipo": "encargo_" + e["estado"], "origen": "encargo", "puntaje": round(puntaje), "motivo": _unir(motivos),
                    "titulo": f"Encargo #{e['num']} de {e['cliente']}: {e['descripcion']}",
                    "detalle": f"Estado: {e['estado'].replace('_', ' ')} · entrega {fecha_corta(e.get('entrega'), hoy)}",
                    "pendiente": None, "contacto": e.get("contacto"), "encargo": e["num"]})
    return out


def _de_agenda(ctx, hoy: date) -> list[dict]:
    out = []
    for t in ctx.consultar_datos("agenda", "turnos") or []:
        f = _fecha(t.get("fecha"))
        if f is None or (f - hoy).days > 1:
            continue
        es_hoy = f == hoy
        out.append({"tipo": "turno", "origen": "agenda", "puntaje": 62 if es_hoy else 30,
                    "motivo": "es hoy" if es_hoy else "es mañana",
                    "titulo": f"Turno {'hoy' if es_hoy else 'mañana'} a las {t['hora']}: {t.get('motivo', 'turno')} con {t.get('nombre') or t.get('contacto', '')}",
                    "detalle": "", "pendiente": None, "contacto": t.get("contacto"), "encargo": None})
    return out


def _de_cobros(ctx, ahora: datetime) -> list[dict]:
    out = []
    for e in ctx.consultar_datos("cobros", "esperando") or []:
        h = _horas(e.get("desde"), ahora)
        if h < 48:
            continue
        out.append({"tipo": "sena_atrasada", "origen": "cobros", "puntaje": round(30 + min(20, h / 24 * 3)),
                    "motivo": f"la seña lleva {_hace(h)[5:]} sin llegar",
                    "titulo": f"Seña de {e.get('cliente') or 'un cliente'} (encargo #{e['num']}): {plata(e['sena'])}",
                    "detalle": "", "pendiente": None, "contacto": None, "encargo": e["num"]})
    return out


def _unir(motivos: list[str]) -> str:
    if not motivos:
        return ""
    if len(motivos) == 1:
        return motivos[0]
    return ", ".join(motivos[:-1]) + " y " + motivos[-1]


def tareas(ctx) -> list[dict]:
    ahora = ctx.ahora()
    todas = _de_pendientes(ctx, ahora) + _de_encargos(ctx, ahora.date()) + _de_agenda(ctx, ahora.date()) + _de_cobros(ctx, ahora)
    todas.sort(key=lambda t: -t["puntaje"])
    for i, t in enumerate(todas, 1):
        t["id"] = i
    return todas


# ------------------------------------------------------------------ la charla
def _saludo(ctx) -> str:
    h = ctx.ahora().hour
    nombre = ctx.perfil.empresa.duena
    s = "Buen día" if h < 12 else "Buenas tardes" if h < 20 else "Buenas noches"
    return f"{s}, {nombre}" if nombre else s


def _lista(ts: list[dict]) -> str:
    return "\n".join(f"{t['id']}) {t['titulo']}" + (f"\n    {t['detalle']}" if t["detalle"] else "") for t in ts[:MAX_LISTA])


def _guardar(ctx, ts: list[dict], actual: int | None) -> None:
    ctx.datos.guardar("sesion", "ultima", {"tareas": ts, "actual": actual})


def _ultima(ctx) -> dict:
    return ctx.datos.obtener("sesion", "ultima") or {"tareas": [], "actual": None}


def _resumen_dia(ctx, con_saludo: bool = True) -> Charla:
    ts = tareas(ctx)
    _guardar(ctx, ts, None)
    ini = (_saludo(ctx) + ". ") if con_saludo else ""
    if not ts:
        return Charla(ini + "No tengo nada pendiente: ni mensajes para decidir, ni entregas cerca. Día tranquilo 🙌", ["¿Cómo vienen los encargos?"])
    n = len(ts)
    texto = f"{ini}Tenemos {n} cosa{'s' if n > 1 else ''} para hoy:\n{_lista(ts)}"
    if n > MAX_LISTA:
        texto += f"\n… y {n - MAX_LISTA} más que son menos urgentes."
    return Charla(texto, ["¿Cuál me recomendás hacer primero?", "Contame la 1"], ts[:MAX_LISTA])


def _recomendar(ctx) -> Charla:
    ts = _ultima(ctx)["tareas"] or tareas(ctx)
    if not ts:
        return Charla("No hay nada urgente. Si querés, mirá los encargos en curso.", [])
    t = ts[0]
    _guardar(ctx, ts, t["id"])
    texto = f"Te recomiendo la {t['id']}) {t['titulo']}.\nPorque {t['motivo']}."
    if len(ts) > 1:
        texto += f"\nDespués seguiría con la {ts[1]['id']}) {ts[1]['titulo']}."
    return Charla(texto, [f"Contame la {t['id']}", "¿Y después?"], [])


def _siguiente(ctx) -> Charla:
    u = _ultima(ctx)
    ts, actual = u["tareas"], u["actual"]
    if not ts:
        return _resumen_dia(ctx, False)
    prox = next((t for t in ts if actual is None or t["id"] > actual), None)
    if prox is None:
        return Charla("Esa era la última de la lista. Si querés, repasamos el día de nuevo.", ["¿Qué tareas tenemos hoy?"])
    _guardar(ctx, ts, prox["id"])
    return Charla(f"Seguiría con la {prox['id']}) {prox['titulo']}.\nPorque {prox['motivo']}.", [f"Contame la {prox['id']}", "¿Y después?"], [])


def _numero(t: str) -> int | None:
    for palabra, n in ORDINALES.items():
        if re.search(rf"\b{palabra}\b", t):
            return n
    solo = t.strip(" .!?")
    m = R_NUMERO.fullmatch(solo) or (R_NUMERO.search(t) if R_DETALLE.search(t) else None)
    return int(m.group(1)) if m else None


def _ficha(ctx, tarea: dict) -> Charla:
    ts = _ultima(ctx)["tareas"]
    _guardar(ctx, ts, tarea["id"])
    pend = next((p for p in ctx.pendientes() if p["id"] == tarea.get("pendiente")), None) if tarea.get("pendiente") else None
    conv = ctx.conversacion(tarea["contacto"])[-6:] if tarea.get("contacto") else []
    resumen = _resumir(ctx, tarea, conv)
    opciones = _opciones(ctx, tarea, pend)
    partes = [f"{tarea['id']}) {tarea['titulo']}", f"Por qué ahora: {tarea['motivo']}."]
    if resumen:
        partes.append(f"Contexto: {resumen}")
    if opciones:
        partes.append("Qué podés hacer:\n" + "\n".join(f"  {chr(65 + i)}. {o['titulo']} — {o['detalle']}" + (" (lo que yo haría)" if o["recomendada"] else "")
                                                       for i, o in enumerate(opciones)))
    ficha = {"tarea": tarea["id"], "titulo": tarea["titulo"], "motivo": tarea["motivo"], "resumen": resumen,
             "conversacion": [{"de": m["de"], "texto": m["texto"], "cuando": m.get("cuando")} for m in conv],
             "opciones": opciones, "pendiente": pend}
    return Charla("\n\n".join(partes), ["¿Y después?", "¿Qué tareas quedan?"], [], ficha)


def _resumir(ctx, tarea: dict, conv: list[dict]) -> str:
    if not conv:
        return ""
    ultimo = next((m for m in reversed(conv) if m["de"] == "cliente"), None)
    ia = ctx.ia("resumen", [{"role": "system", "content": "Resumí en dos oraciones, en español rioplatense, qué quiere el cliente y qué falta resolver. No inventes datos."},
                            {"role": "user", "content": "\n".join(f"{'Cliente' if m['de'] == 'cliente' else 'Raphael'}: {m['texto']}" for m in conv)}],
                 max_tokens=160)
    if ia:
        return ia.strip()
    if ultimo is None:
        return "Raphael le escribió pero el cliente todavía no contestó."
    return f"escribió {sum(1 for m in conv if m['de'] == 'cliente')} mensaje(s); lo último que dijo: «{limpio(ultimo['texto'], 160)}»."


def _opciones(ctx, t: dict, pend: dict | None) -> list[dict]:
    tipo = t["tipo"]
    d = (pend["accion"].get("datos") if pend else None) or {}

    def o(titulo, detalle, rec=False):
        return {"titulo": titulo, "detalle": detalle, "recomendada": rec}

    if tipo == "derivar_humano":
        return [o("Escribirle vos, con calma", "pedile disculpas, preguntale qué pasó y ofrecé una solución. Es lo que más cuida la relación.", True),
                o("Pedir más datos antes de decidir", "decile que lo estás revisando y pedí foto o número de pedido, así no prometés nada a ciegas."),
                o("Dejarlo como resuelto", "si ya lo hablaron por otro lado, marcalo resuelto sin escribirle.")]
    if tipo == "responder_duda":
        return [o("Contestarle vos", "Raphael no tiene esa respuesta cargada: escribila en la tarjeta y se la mando.", True),
                o("Cargarla como pregunta frecuente", "si te la hacen seguido, sumala a las preguntas del perfil y la próxima Raphael responde solo."),
                o("Dejarla de lado", "si es spam o un error, marcala resuelta sin responder.")]
    if tipo == "enviar_presupuesto":
        sug = d.get("precio")
        urg = " Es urgente: antes confirmá que llegás con la fecha." if "urgente" in t["motivo"] else ""
        return [o(f"Aprobar el precio sugerido ({plata(sug)})" if sug else "Ponerle precio vos",
                  ("sale de tu tabla de precios y se le manda al cliente con la seña." if sug else "no está en tu tabla: escribí el monto en la tarjeta.") + urg, True),
                o("Cambiar el precio", "si el pedido es más complejo, corregí el monto en la tarjeta antes de aprobar."),
                o("Rechazar y hablar con el cliente", "si no te cierra el pedido o la fecha, rechazalo y escribile.")]
    if tipo == "confirmar_pago":
        return [o("Me llegó", "revisá tu cuenta; al confirmar, el encargo pasa a confirmado y el cliente recibe el aviso.", True),
                o("Todavía no me llegó", "rechazalo: Raphael vuelve a esperar la transferencia.")]
    if tipo == "confirmar_turno":
        franjas = ", ".join(ctx.perfil.agenda.franjas) if ctx.perfil.agenda.franjas else "tus franjas"
        return [o("Confirmar día y horario", "completá la fecha y la hora en la tarjeta y se le avisa al cliente.", True),
                o("Proponer otro horario", f"rechazalo y escribile con otra opción dentro de {franjas}.")]
    if tipo == "aviso_tope":
        return [o("Seguir con reglas", "las brigadas funcionan igual; solo se apaga la IA hasta el mes que viene.", True),
                o("Subir de plan", "si querés que la IA siga, hablá con soporte para cambiar de plan.")]
    if tipo == "sena_atrasada":
        return [o("Recordarle la seña", "escribile con el alias para transferir; muchas veces es solo un olvido.", True),
                o("Esperar unos días más", "si el pedido tiene fecha lejana, no hace falta apurarlo."),
                o("Cancelar el encargo", "si ya no responde, cancelalo desde Encargos para liberar tu agenda.")]
    if tipo == "turno":
        return [o("Prepararte", "el cliente ya recibió el recordatorio automático.", True),
                o("Reprogramar", "si no podés, avisale lo antes posible y ofrecele otra franja.")]
    if tipo == "encargo_listo":
        return [o("Coordinar la entrega", "escribile al cliente para ver cuándo retira o cómo se envía.", True),
                o("Marcarlo como entregado", "cuando lo reciba, cambiá el estado en Encargos y no queda pendiente.")]
    if tipo.startswith("encargo_"):
        vencido = "pasó" in t["motivo"]
        return [o("Avisarle al cliente" if vencido else "Priorizarlo hoy", "decile con honestidad cuándo estaría listo." if vencido else "es el que tiene la entrega más cerca.", True),
                o("Cambiar el estado", "si ya avanzó, actualizá el estado en Encargos y el cliente recibe el aviso.")]
    return []


def atender(texto: str, ctx) -> Charla:
    t = normalizar(texto).strip()
    ref = None if R_PRIMERO.search(t) else _numero(t)          # «¿cuál primero?» no es «la tarea 1»
    if ref is not None:
        ts = _ultima(ctx)["tareas"] or tareas(ctx)
        if not _ultima(ctx)["tareas"]:
            _guardar(ctx, ts, None)
        tarea = next((x for x in ts if x["id"] == ref), None)
        if tarea is None:
            return Charla(f"No tengo una tarea {ref}. Hoy hay {len(ts)}." if ts else "Hoy no hay tareas.", ["¿Qué tareas tenemos hoy?"])
        return _ficha(ctx, tarea)
    if R_PRIMERO.search(t):
        return _recomendar(ctx)
    if R_SIGUIENTE.search(t):
        return _siguiente(ctx)
    if R_HOY.search(t):
        return _resumen_dia(ctx, con_saludo=bool(re.search(r"\b(buen|hola)", t)))
    if R_GRACIAS.search(t) and len(t) < 30:
        return Charla("¡Dale! Avisame cuando quieras repasar lo que queda.", ["¿Qué tareas quedan?"])
    libre = _libre(ctx, texto)
    if libre:
        return Charla(libre, ["¿Qué tareas tenemos hoy?", "¿Cuál hago primero?"])
    return Charla("No te entendí del todo 🙈. Puedo contarte qué hay para hoy, recomendarte por dónde empezar o darte el detalle de una tarea (por ejemplo «contame la 2»).",
                  ["¿Qué tareas tenemos hoy?", "¿Cuál hago primero?"])


def _libre(ctx, texto: str) -> str | None:
    """Frase que las reglas no entendieron: si el plan tiene IA, le damos el estado del día para que conteste con eso y nada más."""
    ts = _ultima(ctx)["tareas"] or tareas(ctx)
    estado = "\n".join(f"{t['id']}) {t['titulo']} — {t['motivo']}" for t in ts[:MAX_LISTA]) or "(sin tareas pendientes)"
    r = ctx.ia("secretaria", [{"role": "system", "content": "Sos la secretaria de una dueña de negocio. Contestá en español rioplatense, breve y cálida, usando SOLO la lista de tareas de abajo. "
                                                            "Si no lo sabés con esa lista, decilo. No inventes datos ni prometas acciones.\n\nTareas de hoy:\n" + estado},
                              {"role": "user", "content": texto}], max_tokens=220)
    return r.strip() if r else None
