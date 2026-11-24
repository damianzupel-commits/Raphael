"""Confirmación de acciones de escritura: se arman con ids REALES, se proponen y se ejecutan solo tras un "sí".

Portado de Empresas `raphael_orquestador/agente.py` (`_armar_accion`, `_proponer`, `_resolver_confirmacion`) y
generalizado: las acciones y los comandos salen del catálogo del harness, no de una lista del negocio.

  1. Una escritura (aprobar, rechazar o resolver un pendiente, escribirle a un contacto, un comando declarado de una
     brigada) se ARMA por código contra la realidad: el pendiente tiene que estar abierto (número real), el nivel tiene
     que permitirlo (lo `humano` no se aprueba: se resuelve), el contacto tiene que existir, el comando tiene que estar
     declarado en el manifiesto. Lo que el modelo inventó se rechaza y se dice por qué.
  2. Se guarda como propuesta en el espacio del orquestador (por sesión) y se muestra: "Voy a … ¿Confirmo?".
  3. Solo un "sí" explícito (lista cerrada, el mensaje entero) la ejecuta; un "no" la cancela; cualquier otra frase la
     descarta y la charla sigue normal (decisión 4: no vence por tiempo, la cancela el próximo mensaje).
  4. Antes de ejecutar se vuelve a validar (el pendiente pudo cerrarse mientras tanto) y se ejecuta SOLO por el
     `OwnerContext` del harness (que audita y pasa por el Policy Engine). Queda auditado quién confirmó qué.
"""

from __future__ import annotations

import re
from typing import Any

from raphael_core.contract import ActionError
from raphael_core.engine.reports import normalize

COLLECTION = "confirm"
MAX_TEXT = 800

_YES = frozenset("si sii siii sip dale ok okey oka okay confirmo confirma confirmalo confirmala hacelo hacela mandalo "
                 "mandala adelante de una obvio exacto correcto joya perfecto va".split())
_NO = re.compile(r"^(no\b|nop\b|cancela\w*|dejalo|dejala|mejor no|olvidate|para\b|frena)")


def is_yes(text: str) -> bool:
    """¿Es un "sí" explícito? El mensaje ENTERO tiene que ser de la lista cerrada (hasta 4 palabras)."""
    words = re.findall(r"[a-z]+", normalize(text))
    return 0 < len(words) <= 4 and all(w in _YES for w in words)


def is_no(text: str) -> bool:
    return bool(_NO.match(normalize(text).strip(" .!¡¿?")))


def _clean(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


# --- armar una acción contra la realidad ----------------------------------------------------------------------------------
def _open_pending(ctx: Any, pid: Any) -> dict | None:
    try:
        n = int(pid)
    except (TypeError, ValueError):
        return None
    return next((p for p in ctx.pending() if p["id"] == n), None)


def _task(tasks: list[dict], ref: Any, current: int | None) -> dict | None:
    if ref in (None, "", "esa", "esta"):
        ref = current
    try:
        n = int(ref)
    except (TypeError, ValueError):
        return None
    return next((t for t in tasks if t["id"] == n), None)


def build(ctx: Any, a: dict, tasks: list[dict], current: int | None = None) -> tuple[dict | None, str]:
    """Lo que se pidió -> una acción concreta con ids reales, o (None, por qué no se puede). `a` viene de las reglas o
    del modelo (dato no confiable): {"action": aprobar|rechazar|responder|escribir|comando, "task" | "pending", ...}."""
    kind = a.get("action") or a.get("accion")
    if kind == "comando":
        return _build_command(ctx, a)
    t = _task(tasks, a.get("task", a.get("tarea")), current)
    pid = a.get("pending")
    if pid is None and t is not None:
        pid = t.get("pending")
    if kind == "escribir":
        contact = a.get("contact") or a.get("contacto") or (t or {}).get("contact")
        text = _clean(a.get("text") or a.get("texto"), MAX_TEXT)
        if not contact:
            return None, ("No sé a quién escribirle. Decime el número de la tarea (por ejemplo «la 2»)." if t is None
                          else f"La {t['id']}) no tiene un contacto al que escribirle.")
        if not ctx.conversation(str(contact)):
            return None, f"No tengo ninguna conversación con {contact}: no le escribo a alguien que no conozco."
        if not text:
            return None, "¿Qué le escribo?"
        who = f"al contacto de la {t['id']})" if t else f"a {contact}"
        return {"kind": "write", "contact": str(contact), "text": text,
                "summary": f"escribirle {who}: «{_clean(text, 140)}»"}, ""
    if kind not in ("aprobar", "rechazar", "responder"):
        return None, "No sé hacer eso."
    if t is None and a.get("pending") is None:
        return None, "No sé a qué tarea te referís. Decime el número de la lista (por ejemplo «la 2»)."
    label = f"la {t['id']})" if t else f"el pendiente #{pid}"
    if pid is None:
        return None, (f"La {t['id']}) no es algo que se apruebe o rechace: {t.get('reason') or 'es una tarea'}. "
                      "Puedo escribirle al contacto.")
    p = _open_pending(ctx, pid)
    if p is None:
        return None, f"{label[0].upper() + label[1:]} ya no está pendiente."
    human = p["level"] == "humano"
    title = (t or {}).get("title") or p.get("summary") or f"#{p['id']}"
    if kind == "aprobar":
        if human:
            return None, (f"{label[0].upper() + label[1:]} la tenés que resolver vos: decime qué le respondo (por ejemplo "
                          f"«respondele a {label.rstrip(')')}: …») o que la deje como resuelta.")
        changes = a.get("changes") or a.get("cambios") or {}
        if not isinstance(changes, dict):
            return None, "No entendí los cambios."
        extra = f" con cambios ({', '.join(f'{k}: {v}' for k, v in changes.items())})" if changes else ""
        return {"kind": "approve", "pending": p["id"], "changes": changes,
                "summary": f"aprobar {label} {title}{extra}"}, ""
    if kind == "rechazar":
        return {"kind": "reject", "pending": p["id"], "reason": _clean(a.get("reason") or a.get("motivo"), 200),
                "summary": f"rechazar {label} {title}"}, ""
    text = _clean(a.get("text") or a.get("texto"), MAX_TEXT)
    if not text:
        return None, "¿Qué le respondo?"
    if not human:
        return None, (f"{label[0].upper() + label[1:]} no es una pregunta para responder: es una aprobación. "
                      "¿La aprobamos o la rechazamos?")
    return {"kind": "resolve", "pending": p["id"], "text": text,
            "summary": f"responderle a {label} «{_clean(text, 140)}» y dejarla resuelta"}, ""


def _build_command(ctx: Any, a: dict) -> tuple[dict | None, str]:
    brigade, name = a.get("brigade") or a.get("brigada"), a.get("command") or a.get("comando")
    data = a.get("data") or a.get("datos") or {}
    b = next((x for x in ctx.catalog() if x.get("id") == brigade and x.get("mounted")), None)
    if b is None:
        return None, f"No tengo montada la brigada {brigade}."
    if b.get("down"):
        return None, f"{b.get('name') or brigade} está caída ({b.get('down_reason')})."
    spec = (b.get("commands") or {}).get(name)
    if spec is None:
        return None, f"{b.get('name') or brigade} no tiene la orden «{name}»."
    if not isinstance(data, dict):
        return None, "No entendí los datos de la orden."
    cooks = spec.get("cooks") or list((b.get("cooks") or {}).keys())
    cook = a.get("cook") if a.get("cook") in cooks else (cooks[0] if cooks else None)
    if cook is None:
        return None, f"{b.get('name') or brigade} no tiene quién atienda «{name}»."
    desc = spec.get("description") or name
    shown = ", ".join(f"{k}: {v}" for k, v in data.items())
    return {"kind": "command", "brigade": brigade, "cook": cook, "command": name, "data": data,
            "summary": f"{desc} en {b.get('name') or brigade}" + (f" ({shown})" if shown else "")}, ""


# --- proponer, confirmar, ejecutar ---------------------------------------------------------------------------------------
def propose(ctx: Any, session: str, actions: list[dict], intro: str = "") -> tuple[str, list[str]]:
    """Guarda la propuesta y devuelve (texto, sugerencias). Nada se ejecuta acá."""
    ctx.data.put(COLLECTION, session, {"actions": actions})
    if len(actions) == 1:
        body = f"Voy a {actions[0]['summary']}."
    else:
        body = "Voy a hacer esto:\n" + "\n".join(f"  • {a['summary']}" for a in actions)
    return (intro + "\n\n" if intro else "") + body + " ¿Confirmo?", ["Sí, confirmá", "No, cancelá"]


def waiting(ctx: Any, session: str) -> dict | None:
    return ctx.data.get(COLLECTION, session)


def clear(ctx: Any, session: str) -> None:
    ctx.data.delete(COLLECTION, session)


async def execute(ctx: Any, a: dict) -> str:
    """Ejecuta UNA acción ya confirmada por el `OwnerContext`. Nunca rompe la charla."""
    kind = a["kind"]
    try:
        if kind in ("approve", "reject", "resolve") and _open_pending(ctx, a["pending"]) is None:
            return f"No lo hice: el pendiente #{a['pending']} ya no está abierto."
        ctx.record("orden_confirmada", quien=getattr(ctx, "who", ""), orden=kind, pendiente=a.get("pending"),
                   brigada=a.get("brigade"), comando=a.get("command"))
        if kind == "approve":
            r = await ctx.approve(a["pending"], a.get("changes") or None)
            if r.get("state") == "error":
                return f"No pude aprobar: {r.get('error')}"
            if r.get("state") == "pending":
                return f"Quedó pendiente otra vez (#{r.get('id')}): el nivel de esa acción pide otra aprobación."
            return "Aprobada." + (" Ya le salió el mensaje al contacto." if r.get("text") else "")
        if kind == "reject":
            await ctx.reject(a["pending"], a.get("reason", ""))
            return "Rechazada."
        if kind == "resolve":
            await ctx.resolve(a["pending"], a["text"])
            return "Le mandé tu respuesta al contacto y la dejé resuelta."
        if kind == "write":
            ctx.write(a["contact"], a["text"])
            return "Mensaje enviado."
        if kind == "command":
            await ctx.order(a["brigade"], a["cook"], a["command"], a.get("data") or {})
            return f"Hecho: {a['summary']}."
    except ActionError as exc:
        return f"No pude: {exc}"
    except Exception as exc:  # noqa: BLE001 - nunca romper la charla
        return f"Algo falló y no se hizo: {_clean(exc, 120)}"
    return "No sé hacer eso."


async def settle(ctx: Any, session: str, text: str) -> tuple[str, list[str]] | None:
    """Si hay una propuesta esperando: "sí" -> ejecuta todo; "no" -> cancela; otra frase -> la descarta y devuelve None
    (que la charla siga normal)."""
    w = waiting(ctx, session)
    if not w:
        return None
    clear(ctx, session)
    if is_no(text):
        return "Listo, no hago nada.", ["¿Qué tareas quedan?"]
    if is_yes(text):
        results = [await execute(ctx, a) for a in w.get("actions", [])]
        return "\n".join(results), []
    ctx.record("propuesta_descartada", motivo="otra frase")
    return None
