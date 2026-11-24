"""El secretario que entiende lo que le decís y hace lo que le pedís.

Dos caminos para llegar a la misma acción:
- Reglas: órdenes claras («aprobá la 2», «rechazá la 3», «respondele a la 1: …», «pasá el encargo 4 a listo»).
  Funcionan sin IA.
- IA: si el plan tiene modelo, entiende frases libres y contesta con un JSON `{"decir": …, "hacer": […]}`.
  Las acciones de solo lectura (resumen, recomendación, detalle) se muestran enseguida; las que cambian algo
  (aprobar, rechazar, responder, escribir, cambiar estado) **siempre** esperan tu «sí» antes de ejecutarse.

La IA nunca toca nada directo: propone, el agente valida contra las tareas reales del día y ejecuta recién
cuando confirmás. Si el modelo falla o devuelve algo raro, se cae a reglas.
"""

from __future__ import annotations

import json
import re

from raphael_harness import Charla, ErrorDeAccion
from raphael_harness.texto import limpio, normalizar, plata

from . import secretaria as sec

ESTADOS = {"presupuesto": "presupuesto", "confirmado": "confirmado", "confirmar": "confirmado", "en confeccion": "en_confeccion",
           "confeccion": "en_confeccion", "prueba": "prueba", "listo": "listo", "lista": "listo", "entregado": "entregado",
           "entregada": "entregado", "cancelado": "cancelado", "cancelada": "cancelado"}
ESCRITURA = {"aprobar", "rechazar", "responder", "escribir", "estado"}
LECTURA = {"resumen_dia", "recomendar", "detalle"}

R_SI = re.compile(r"^(si+|sip|dale|ok|okey|oka|confirmo|confirma\w*|hacelo|hacela|mandalo|mandala|adelante|de una|obvio|exacto|correcto|joya|perfecto)\b")
R_NO = re.compile(r"^(no\b|nop|cancela\w*|dejalo|dejala|mejor no|olvidate|para\b|frena)")
VERBO = r"(?:aprob\w+|apruebe?\w*)"
R_APROBAR = re.compile(rf"^(?:y |ok |dale |bueno )?{VERBO}\b")
R_RECHAZAR = re.compile(r"^(?:y |ok |dale |bueno )?(rechaz\w+|descart\w+)\b")
R_RESPONDER = re.compile(r"^(?:y |ok |dale |bueno )?(responde\w*|contesta\w*|escribi\w*|decile|decirle|avisale|mandale)\b(.*)$")
R_ESTADO = re.compile(r"\bencargo\s*#?\s*(\d+)\b.*?\b(en confeccion|confeccion|confirmado|prueba|listo|lista|entregado|entregada|cancelado|cancelada|presupuesto)\b")
R_ESTADO2 = re.compile(r"\b(marca\w*|pasa\w*|cambia\w*|ponele|pone)\b.*?\bencargo\s*#?\s*(\d+)\b")


# ------------------------------------------------------------------ estado de la charla
def _confirmacion(ctx) -> dict | None:
    return ctx.datos.obtener("sesion", "confirmar")


def _guardar_conf(ctx, conf: dict | None) -> None:
    if conf is None:
        ctx.datos.borrar("sesion", "confirmar")
    else:
        ctx.datos.guardar("sesion", "confirmar", conf)


def _historial(ctx) -> list[dict]:
    return (ctx.datos.obtener("sesion", "historial") or {}).get("turnos", [])


def _recordar(ctx, texto: str, respuesta: str) -> None:
    turnos = (_historial(ctx) + [{"role": "user", "content": limpio(texto, 300)},
                                 {"role": "assistant", "content": limpio(respuesta, 400)}])[-8:]
    ctx.datos.guardar("sesion", "historial", {"turnos": turnos})


# ------------------------------------------------------------------ de la frase a una acción concreta
def _tarea(ctx, ref) -> dict | None:
    u = sec._ultima(ctx)
    ts = u["tareas"] or sec.tareas(ctx)
    if ref in (None, "", "esa", "esta"):
        ref = u["actual"]
    try:
        ref = int(ref)
    except (TypeError, ValueError):
        return None
    return next((t for t in ts if t["id"] == ref), None)


def _armar_accion(ctx, a: dict) -> tuple[dict | None, str]:
    """Convierte lo que se pidió en una acción concreta (con ids reales) o explica por qué no se puede."""
    tipo = a.get("accion")
    if tipo == "estado":
        num = a.get("encargo")
        estado = ESTADOS.get(normalizar(str(a.get("estado", ""))).replace("_", " "))
        try:
            num = int(num)
        except (TypeError, ValueError):
            return None, "No me dijiste de qué encargo."
        if not estado:
            return None, "No reconozco ese estado. Los válidos: presupuesto, confirmado, en confección, prueba, listo, entregado, cancelado."
        if not ctx.instalada("encargos"):
            return None, "No tenés instalada la brigada de Encargos."
        return {"accion": "estado", "encargo": num, "estado": estado,
                "resumen": f"pasar el encargo #{num} a «{estado.replace('_', ' ')}»"}, ""

    t = _tarea(ctx, a.get("tarea"))
    if tipo == "escribir" and a.get("contacto"):
        return ({"accion": "escribir", "contacto": str(a["contacto"]), "texto": limpio(str(a.get("texto", "")), 800),
                 "resumen": f"escribirle a {a['contacto']}: «{limpio(str(a.get('texto', '')), 140)}»"}, "") if a.get("texto") else (None, "¿Qué le escribo?")
    if t is None:
        return None, "No sé a qué tarea te referís. Decime el número de la lista (por ejemplo «la 2»)."

    if tipo in ("aprobar", "rechazar", "responder"):
        if not t.get("pendiente"):
            return None, f"La {t['id']}) no es algo que se apruebe o rechace: es {t['motivo']}. Puedo escribirle al cliente o cambiar el estado del encargo."
        p = next((x for x in ctx.pendientes() if x["id"] == t["pendiente"]), None)
        if p is None:
            return None, f"La {t['id']}) ya no está pendiente."
        humano = p["nivel"] == "humano"
        if tipo == "aprobar":
            if humano:
                return None, f"La {t['id']}) la tenés que resolver vos: decime qué le respondo al cliente (por ejemplo «respondele a la {t['id']}: …») o decime que la deje como resuelta."
            cambios = {}
            if a.get("precio"):
                try:
                    cambios["precio"] = int(float(a["precio"]))
                except (TypeError, ValueError):
                    return None, "No entendí el precio."
            extra = f" con el precio en {plata(cambios['precio'])}" if cambios else ""
            return {"accion": "aprobar", "pendiente": p["id"], "cambios": cambios, "tarea": t["id"],
                    "resumen": f"aprobar la {t['id']}) {t['titulo']}{extra}"}, ""
        if tipo == "rechazar":
            return {"accion": "rechazar", "pendiente": p["id"], "motivo": limpio(str(a.get("motivo", "")), 200), "tarea": t["id"],
                    "resumen": f"rechazar la {t['id']}) {t['titulo']}"}, ""
        texto = limpio(str(a.get("texto", "")), 800)
        if not texto:
            return None, "¿Qué le respondo al cliente?"
        if not humano:
            return None, f"La {t['id']}) no es una pregunta para responder: es una aprobación. ¿La aprobamos o la rechazamos?"
        return {"accion": "responder", "pendiente": p["id"], "texto": texto, "tarea": t["id"],
                "resumen": f"responderle al cliente de la {t['id']}) «{limpio(texto, 140)}» y dejarla resuelta"}, ""

    if tipo == "escribir":
        if not t.get("contacto"):
            return None, f"La {t['id']}) no tiene un cliente al que escribirle."
        texto = limpio(str(a.get("texto", "")), 800)
        if not texto:
            return None, "¿Qué le escribo?"
        return {"accion": "escribir", "contacto": t["contacto"], "texto": texto,
                "resumen": f"escribirle al cliente de la {t['id']}): «{limpio(texto, 140)}»"}, ""
    return None, "No sé hacer eso todavía."


def _proponer(ctx, acciones: list[dict], intro: str = "") -> Charla:
    ctx.datos.guardar("sesion", "confirmar", {"acciones": acciones})
    if len(acciones) == 1:
        cuerpo = f"Voy a {acciones[0]['resumen']}."
    else:
        cuerpo = "Voy a hacer esto:\n" + "\n".join(f"  • {a['resumen']}" for a in acciones)
    return Charla((intro + "\n\n" if intro else "") + cuerpo + " ¿Confirmo?", ["Sí, confirmá", "No, cancelá"])


# ------------------------------------------------------------------ ejecutar (solo después del «sí»)
def _ejecutar_una(ctx, a: dict) -> str:
    tipo = a["accion"]
    try:
        if tipo == "aprobar":
            r = ctx.aprobar(a["pendiente"], a.get("cambios") or None)
            if r.get("estado") == "error":
                return f"❌ No pude aprobar: {r.get('error')}"
            return "✅ Aprobada." + (" Ya le salió el mensaje al cliente." if r.get("texto") else "")
        if tipo == "rechazar":
            ctx.rechazar(a["pendiente"], a.get("motivo", ""))
            return "✅ Rechazada."
        if tipo == "responder":
            ctx.resolver(a["pendiente"], a["texto"])
            return "✅ Le mandé tu respuesta al cliente y la dejé resuelta."
        if tipo == "escribir":
            ctx.escribir(a["contacto"], a["texto"])
            return "✅ Mensaje enviado al cliente."
        if tipo == "estado":
            ctx.ordenar("encargos", "estado", {"num": a["encargo"], "estado": a["estado"]})
            return f"✅ Encargo #{a['encargo']} en «{a['estado'].replace('_', ' ')}» (el cliente recibe el aviso si corresponde)."
    except ErrorDeAccion as e:
        return f"❌ No pude: {e}"
    except Exception as e:  # noqa: BLE001 - nunca romper la charla
        return f"❌ Algo falló y no se hizo: {limpio(str(e), 120)}"
    return "No sé hacer eso todavía."


def _resolver_confirmacion(ctx, texto: str, conf: dict) -> Charla | None:
    t = normalizar(texto).strip(" .!¡¿?")
    if R_NO.match(t):
        _guardar_conf(ctx, None)
        return Charla("Listo, no hago nada.", ["¿Qué tareas quedan?"])
    if R_SI.match(t):
        _guardar_conf(ctx, None)
        res = [f"{_ejecutar_una(ctx, a)}" for a in conf["acciones"]]
        ts = sec.tareas(ctx)
        sec._guardar(ctx, ts, None)
        resto = f"Quedan {len(ts)} cosa{'s' if len(ts) != 1 else ''} para hoy." if ts else "No queda nada pendiente 🙌"
        return Charla("\n".join(res) + "\n\n" + resto, ["¿Qué tareas quedan?", "¿Cuál hago primero?"] if ts else [])
    return None                                                 # otra frase: se descarta la propuesta y se sigue normal


# ------------------------------------------------------------------ órdenes por reglas (sin IA)
def _despues_de_dos_puntos(texto: str) -> str:
    m = re.search(r"[:：]\s*(.+)$", texto, re.S)
    if m:
        return m.group(1).strip().strip("«»\"'")
    m = re.search(r"[«\"“](.+)[»\"”]", texto, re.S)
    return m.group(1).strip() if m else ""


def _numero_orden(t: str) -> int | None:
    """El número de tarea de una orden («aprobá la 2», «respondele a la 3: …»): solo se mira antes de los dos puntos."""
    cabeza = t.split(":")[0]
    for palabra, n in sec.ORDINALES.items():
        if re.search(rf"\b{palabra}\b", cabeza):
            return n
    m = sec.R_NUMERO.search(cabeza)
    return int(m.group(1)) if m else None


def ordenes_por_reglas(ctx, texto: str) -> Charla | None:
    t = normalizar(texto).strip(" .!¡¿?")
    m = R_ESTADO.search(t) or None
    if m and re.search(r"\b(marca\w*|pasa\w*|cambia\w*|ponele|pone|esta|ya)\b", t):
        a, err = _armar_accion(ctx, {"accion": "estado", "encargo": m.group(1), "estado": m.group(2)})
        return _proponer(ctx, [a]) if a else Charla(err)
    m = R_ESTADO2.search(t)
    if m:
        est = next((v for k, v in ESTADOS.items() if re.search(rf"\b{k}\b", t)), None)
        if est:
            a, err = _armar_accion(ctx, {"accion": "estado", "encargo": m.group(2), "estado": est})
            return _proponer(ctx, [a]) if a else Charla(err)

    ref = _numero_orden(t)
    for rx, tipo in ((R_APROBAR, "aprobar"), (R_RECHAZAR, "rechazar")):
        if rx.match(t):
            a, err = _armar_accion(ctx, {"accion": tipo, "tarea": ref, "motivo": _despues_de_dos_puntos(texto)})
            return _proponer(ctx, [a]) if a else Charla(err, ["¿Qué tareas tenemos hoy?"])
    m = R_RESPONDER.match(t)
    if m:
        cuerpo = _despues_de_dos_puntos(texto)
        if not cuerpo:
            return None                                         # sin texto no es una orden clara: que decida la IA o las reglas de charla
        tarea = _tarea(ctx, ref)
        tipo = "responder" if tarea and tarea.get("pendiente") else "escribir"
        a, err = _armar_accion(ctx, {"accion": tipo, "tarea": ref, "texto": cuerpo})
        return _proponer(ctx, [a]) if a else Charla(err, ["¿Qué tareas tenemos hoy?"])
    return None


# ------------------------------------------------------------------ IA
SISTEMA = """Sos Raphael, el secretario de {dueña} en {negocio}. Hablás con la dueña en español rioplatense (voseo), breve y cálido, como un buen secretario.
Tu trabajo: contarle qué hay para hacer, recomendarle por dónde empezar y hacer lo que te pida con las herramientas de abajo.

REGLAS
- Usá SOLO los datos de "TAREAS DE HOY". No inventes clientes, precios, fechas ni tareas. Si no lo sabés, decilo.
- Respondé SIEMPRE con un único JSON y nada más: {{"decir": "<tu mensaje, máx. 3 oraciones>", "hacer": [<acciones>]}}
- "hacer" puede estar vacío. Las acciones que cambian algo se las confirma ella antes de ejecutarse; vos solo proponelas.
- Si te pide algo ambiguo (¿cuál tarea?, ¿qué texto?), preguntale en "decir" y dejá "hacer" vacío.
- Si faltan datos para una acción (el texto de una respuesta, el precio), no la inventes: preguntá.
- Para escribirle a un cliente usá el texto que ella dicte; si solo dice «avisale que sí», podés redactarlo vos corto y amable y se lo mostramos antes de enviar.

ACCIONES (campo "accion")
- "resumen_dia": muestra la lista de tareas.            {{"accion":"resumen_dia"}}
- "recomendar": recomienda por cuál empezar.            {{"accion":"recomendar"}}
- "detalle": ficha con contexto y opciones de una tarea. {{"accion":"detalle","tarea":2}}
- "aprobar": aprueba una tarea que espera aprobación (con "precio" opcional en pesos).  {{"accion":"aprobar","tarea":1,"precio":90000}}
- "rechazar": rechaza una tarea.                         {{"accion":"rechazar","tarea":1,"motivo":"..."}}
- "responder": responde al cliente de una tarea que esperaba una persona y la deja resuelta.  {{"accion":"responder","tarea":3,"texto":"..."}}
- "escribir": escribe al cliente de una tarea.           {{"accion":"escribir","tarea":3,"texto":"..."}}
- "estado": cambia el estado de un encargo (presupuesto, confirmado, en_confeccion, prueba, listo, entregado, cancelado).  {{"accion":"estado","encargo":4,"estado":"listo"}}

TAREAS DE HOY (ya ordenadas por urgencia)
{tareas}

OTROS DATOS
{extra}"""


def _bloque_tareas(ts: list[dict]) -> str:
    if not ts:
        return "(no hay tareas pendientes)"
    out = []
    for t in ts[:sec.MAX_LISTA + 4]:
        out.append(f"{t['id']}) [{t['tipo']}] {t['titulo']} — {t['motivo']}"
                   + (f" · detalle: {t['detalle']}" if t["detalle"] else "")
                   + (f" · se puede aprobar/rechazar" if t.get("pendiente") else "")
                   + (f" · cliente: {t['contacto']}" if t.get("contacto") else ""))
    return "\n".join(out)


def _json(r: str) -> dict | None:
    r = re.sub(r"<think>.*?</think>", "", r, flags=re.S).strip()
    r = re.sub(r"^```(?:json)?|```$", "", r.strip(), flags=re.M).strip()
    i, j = r.find("{"), r.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        d = json.loads(r[i:j + 1])
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def con_ia(ctx, texto: str) -> Charla | None:
    if not ctx.hay_ia("secretaria"):
        return None
    ts = sec.tareas(ctx)
    sec._guardar(ctx, ts, sec._ultima(ctx)["actual"])
    sistema = SISTEMA.format(**{"dueña": ctx.perfil.empresa.duena or "la dueña", "negocio": ctx.negocio or "su negocio",
                                "tareas": _bloque_tareas(ts),
                                "extra": f"Hoy es {ctx.hoy().strftime('%d/%m/%Y')}. Brigadas activas: {', '.join(ctx.brigadas_activas()) or 'ninguna'}."})
    crudo = ctx.ia("secretaria", [{"role": "system", "content": sistema}, *_historial(ctx), {"role": "user", "content": texto}],
                   max_tokens=500, temperatura=0.2)
    if not crudo:
        return None
    d = _json(crudo)
    if d is None:                                               # el modelo contestó en prosa: sirve como respuesta, sin acciones
        limpio_ = re.sub(r"<think>.*?</think>", "", crudo, flags=re.S).strip()
        return Charla(limpio_, ["¿Qué tareas tenemos hoy?", "¿Cuál hago primero?"]) if limpio_ else None
    decir = limpio(str(d.get("decir") or ""), 600)
    pedidas = [x for x in (d.get("hacer") or []) if isinstance(x, dict)][:5]

    partes, charla_lectura, escrituras, errores = [], None, [], []
    for x in pedidas:
        tipo = x.get("accion")
        if tipo == "resumen_dia":
            charla_lectura = sec._resumen_dia(ctx, con_saludo=False)
        elif tipo == "recomendar":
            charla_lectura = sec._recomendar(ctx)
        elif tipo == "detalle":
            t = _tarea(ctx, x.get("tarea"))
            charla_lectura = sec._ficha(ctx, t) if t else None
            if t is None:
                errores.append("No encontré esa tarea.")
        elif tipo in ESCRITURA:
            a, err = _armar_accion(ctx, x)
            escrituras.append(a) if a else errores.append(err)
    if escrituras:
        return _proponer(ctx, escrituras, decir)
    if charla_lectura:
        txt = (decir + "\n\n" if decir else "") + charla_lectura.texto
        return Charla(txt, charla_lectura.sugerencias, charla_lectura.tareas, charla_lectura.ficha)
    if errores and not decir:
        decir = " ".join(errores)
    return Charla(decir or "No supe qué hacer con eso. ¿Me lo decís de otra forma?", ["¿Qué tareas tenemos hoy?", "¿Cuál hago primero?"])


# ------------------------------------------------------------------ punto de entrada
def atender(texto: str, ctx) -> Charla:
    conf = _confirmacion(ctx)
    if conf:
        r = _resolver_confirmacion(ctx, texto, conf)
        if r is not None:
            _recordar(ctx, texto, r.texto)
            return r
        _guardar_conf(ctx, None)                                # dijo otra cosa: la propuesta anterior queda cancelada

    r = ordenes_por_reglas(ctx, texto)
    if r is None and not _es_simple(texto):
        r = con_ia(ctx, texto)                                   # lo libre o compuesto lo entiende el modelo (si hay)
    if r is None:
        r = sec.atender(texto, ctx)                              # lo simple y claro (o sin IA): reglas
    _recordar(ctx, texto, r.texto)
    return r


def _es_simple(texto: str) -> bool:
    """Frases cortas y de un solo pedido («¿qué tareas hay?», «contame la 2»): las reglas contestan mejor y gratis."""
    t = normalizar(texto).strip()
    if len(t.split()) > 7 or re.search(r"\b(y|pero|ademas|tambien)\b.*\b(aproba|rechaza|respond|escrib|decile|avisale|pasa|marca)", t):
        return False
    return bool(sec.R_PRIMERO.search(t) or sec.R_SIGUIENTE.search(t) or sec.R_HOY.search(t) or sec._numero(t) is not None)
