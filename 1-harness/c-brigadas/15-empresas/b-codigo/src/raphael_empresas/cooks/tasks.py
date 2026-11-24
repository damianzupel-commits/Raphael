"""Tareas: lo del negocio que necesita la Secretaria del orquestador (comando de lectura `owner_tasks`).

La Secretaria es un rol genérico del orquestador (pieza 02): ordena, explica y ejecuta con confirmación, pero no sabe
qué es un encargo, una seña o un turno. Este cocinero se lo dice, con lo que antes armaba `secretaria.py` de Empresas
0.4 (`BONUS_TIPO`, `_de_encargos`, `_de_agenda`, `_de_cobros` y los textos de `_opciones`):
  - enriquece los pendientes de la brigada (prioridad extra, motivo y opciones A/B/C);
  - suma tareas propias: entregas vencidas o cercanas, encargos listos, turnos de hoy y mañana, señas atrasadas,
    catálogo de la tienda sin actualizar y productos con poco stock.
Un solo cocinero atiende `owner_tasks` para toda la brigada (la Secretaria usa el primero que responde): lee los datos
comunes de la brigada (`ctx.shared`). No atiende mensajes de clientes ni ejecuta nada.
"""

from __future__ import annotations

from datetime import date, datetime

from raphael_core import ActionError, Cook
from raphael_core.text_es import money, short_date

from .. import config as C

#: (bonus, motivo) por tipo de pendiente; era BONUS_TIPO de Empresas 0.4
BONUS = {"derivar_humano": (15, "es un cliente que pidió hablar con una persona"),
         "confirmar_pago": (15, "es plata que está esperando tu confirmación"),
         "enviar_presupuesto": (10, "hay un cliente esperando el precio"),
         "responder_duda": (5, "hay un cliente esperando respuesta"),
         "confirmar_turno": (5, "hay un turno por confirmar"),
         "cancelar_pedido": (5, "hay un pedido para cancelar")}
STALE_DEPOSIT_HOURS = 48


def _date(v) -> date | None:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _hours(since: str | None, now: datetime) -> float:
    try:
        return max(0.0, (now - datetime.fromisoformat(since)).total_seconds() / 3600)
    except (TypeError, ValueError):
        return 0.0


def _o(title: str, detail: str, recommended: bool = False) -> dict:
    return {"title": title, "detail": detail, "recommended": recommended}


def options_for(kind: str, ctx, *, data: dict | None = None, reason: str = "") -> list[dict]:
    """Las salidas posibles de cada tipo de tarea (textos de Empresas 0.4)."""
    d = data or {}
    if kind == "derivar_humano":
        return [_o("Escribirle vos, con calma", "pedile disculpas, preguntale qué pasó y ofrecé una solución. Es lo que más "
                                                "cuida la relación.", True),
                _o("Pedir más datos antes de decidir", "decile que lo estás revisando y pedí foto o número de pedido, así no "
                                                       "prometés nada a ciegas."),
                _o("Dejarlo como resuelto", "si ya lo hablaron por otro lado, marcalo resuelto sin escribirle.")]
    if kind == "responder_duda":
        return [_o("Contestarle vos", "el bot no tiene esa respuesta cargada: escribila y se la mando.", True),
                _o("Cargarla como pregunta frecuente", "si te la hacen seguido, sumala a las preguntas de la config y la "
                                                       "próxima vez responde solo."),
                _o("Dejarla de lado", "si es spam o un error, marcala resuelta sin responder.")]
    if kind == "enviar_presupuesto":
        sug = d.get("price")
        urg = " Es urgente: antes confirmá que llegás con la fecha." if "urgente" in reason else ""
        return [_o(f"Aprobar el precio sugerido ({money(sug)})" if sug else "Ponerle precio vos",
                   ("sale de tu tabla de precios y se le manda al cliente con la seña." if sug
                    else "no está en tu tabla: poné el monto al aprobar.") + urg, True),
                _o("Cambiar el precio", "si el pedido es más complejo, corregí el monto antes de aprobar."),
                _o("Rechazar y hablar con el cliente", "si no te cierra el pedido o la fecha, rechazalo y escribile.")]
    if kind == "confirmar_pago":
        return [_o("Me llegó", "revisá tu cuenta; al confirmar, el encargo pasa a confirmado y el cliente recibe el aviso.",
                   True),
                _o("Todavía no me llegó", "rechazalo: la seña vuelve a quedar esperando la transferencia.")]
    if kind == "confirmar_turno":
        slots = ", ".join(C.of(ctx).schedule.slots) or "tus franjas"
        return [_o("Confirmar día y horario", "completá la fecha y la hora al aprobar y se le avisa al cliente.", True),
                _o("Proponer otro horario", f"rechazalo y escribile con otra opción dentro de {slots}.")]
    if kind == "cancelar_pedido":
        return [_o("Cancelar el encargo", "el cliente recibe el aviso de que quedó cancelado.", True),
                _o("No cancelar", "rechazalo y el encargo sigue como estaba.")]
    if kind == "sena_atrasada":
        return [_o("Recordarle la seña", "escribile con el alias para transferir; muchas veces es solo un olvido.", True),
                _o("Esperar unos días más", "si el pedido tiene fecha lejana, no hace falta apurarlo."),
                _o("Cancelar el encargo", "si ya no responde, cancelalo desde Encargos para liberar tu agenda.")]
    if kind == "turno":
        return [_o("Prepararte", "el cliente ya recibió el recordatorio automático.", True),
                _o("Reprogramar", "si no podés, avisale lo antes posible y ofrecele otra franja.")]
    if kind == "encargo_listo":
        return [_o("Coordinar la entrega", "escribile al cliente para ver cuándo retira o cómo se envía.", True),
                _o("Marcarlo como entregado", "cuando lo reciba, cambiá el estado a entregado y no queda pendiente.")]
    if kind.startswith("encargo_"):
        late = "pasó" in reason
        return [_o("Avisarle al cliente" if late else "Priorizarlo hoy",
                   "decile con honestidad cuándo estaría listo." if late else "es el que tiene la entrega más cerca.", True),
                _o("Cambiar el estado", "si ya avanzó, actualizá el estado y el cliente recibe el aviso.")]
    if kind == "catalogo_caido":
        return [_o("Revisar el enlace del catálogo", "puede haber cambiado la dirección o estar caída la tienda.", True),
                _o("Seguir así", "mientras tanto se responde con la última copia buena del catálogo.")]
    if kind == "stock_bajo":
        return [_o("Reponer", "si se vende seguido, conviene reponer antes de que se agote.", True),
                _o("Dejarlo así", "cuando se agote, el bot deja de ofrecerlo.")]
    return []


def _join(reasons: list[str]) -> str:
    reasons = [r for r in reasons if r]
    if len(reasons) <= 1:
        return reasons[0] if reasons else ""
    return ", ".join(reasons[:-1]) + " y " + reasons[-1]


class TaskBoard(Cook):
    name = "tareas"
    version = "2.0.0"
    description = "Arma las tareas del día de la brigada para la Secretaria (no atiende clientes)."
    commands = {"owner_tasks": "Tareas del día para la Secretaria: pendientes enriquecidos y tareas propias"}

    def command(self, name, data, ctx):
        if name != "owner_tasks":
            return super().command(name, data, ctx)
        pending = data.get("pending") if isinstance(data.get("pending"), list) else []
        return self.enrich(pending, ctx) + self.orders(ctx) + self.appointments(ctx) + self.deposits(ctx) + self.store(ctx)

    # --- pendientes de la brigada
    def enrich(self, pending: list[dict], ctx) -> list[dict]:
        out = []
        for p in pending:
            a = p.get("action") or {}
            kind = a.get("type") or ""
            if kind not in BONUS:
                continue
            bonus, reason = BONUS[kind]
            reasons = [reason]
            num = (a.get("data") or {}).get("number")
            if kind == "enviar_presupuesto" and num is not None:
                o = ctx.shared.get("orders", num) or {}
                if o.get("urgent"):
                    bonus += 10
                    reasons.append("el pedido es urgente")
            r = _join(reasons)
            out.append({"pending": p["id"], "bonus": bonus, "reason": r,
                        "options": options_for(kind, ctx, data=a.get("data"), reason=r)})
        return out

    # --- tareas propias
    def orders(self, ctx) -> list[dict]:
        out, today = [], ctx.today()
        for o in ctx.shared.list("orders"):
            if o["status"] in ("presupuesto", "entregado", "cancelado"):
                continue                                   # el presupuesto ya aparece como pendiente de aprobar
            due = _date(o.get("due"))
            days = (due - today).days if due else None
            reasons, score = [], 0
            if days is not None and days < 0:
                score, reasons = 90, [f"se pasó la fecha de entrega hace {-days} día{'s' if days < -1 else ''}"]
            elif days is not None and days <= 3:
                score = 55 + (3 - days) * 8
                reasons = ["se entrega hoy" if days == 0 else "se entrega mañana" if days == 1 else f"se entrega en {days} días"]
            elif days is not None and days <= 7:
                score, reasons = 35, [f"se entrega en {days} días"]
            if o["status"] == "listo":
                score = max(score, 45) + 5
                reasons.append("está listo para entregar")
            if not score:
                continue
            if o.get("urgent"):
                score += 10
                reasons.append("era un pedido urgente")
            kind = "encargo_" + o["status"]
            r = _join(reasons)
            out.append({"kind": kind, "ref": str(o["number"]), "score": min(100, round(score)), "reason": r,
                        "title": f"Encargo #{o['number']} de {o['client']}: {o['description']}",
                        "detail": f"Estado: {o['status'].replace('_', ' ')} · entrega {short_date(o.get('due'), today)}",
                        "contact": o.get("contact"), "options": options_for(kind, ctx, reason=r)})
        return out

    def appointments(self, ctx) -> list[dict]:
        out, today = [], ctx.today()
        for a in ctx.shared.list("appointments"):
            d = _date(a.get("date"))
            if d is None or not 0 <= (d - today).days <= 1:
                continue
            is_today = d == today
            out.append({"kind": "turno", "ref": f"{a['date']} {a['time']}", "score": 62 if is_today else 30,
                        "reason": "es hoy" if is_today else "es mañana",
                        "title": f"Turno {'hoy' if is_today else 'mañana'} a las {a['time']}: {a.get('reason', 'turno')} "
                                 f"con {a.get('name') or a.get('contact', '')}",
                        "contact": a.get("contact"), "options": options_for("turno", ctx)})
        return out

    def deposits(self, ctx) -> list[dict]:
        out, now = [], ctx.now()
        for d in ctx.shared.list("deposits", status="esperando"):
            h = _hours(d.get("since"), now)
            if h < STALE_DEPOSIT_HOURS:
                continue
            days = int(h // 24)
            out.append({"kind": "sena_atrasada", "ref": str(d["number"]), "score": round(30 + min(20, h / 24 * 3)),
                        "reason": f"la seña lleva {days} días sin llegar",
                        "title": f"Seña de {d.get('client') or 'un cliente'} (encargo #{d['number']}): {money(d['deposit'])}",
                        "options": options_for("sena_atrasada", ctx)})
        return out

    def store(self, ctx) -> list[dict]:
        cfg = C.of(ctx).store
        if cfg.source.kind == "none":
            return []
        state = ctx.shared.get("catalog_state", "state") or {}
        out = []
        if state.get("error"):
            since = state.get("last_ok") or "nunca"
            out.append({"kind": "catalogo_caido", "ref": "catalogo", "score": 40,
                        "reason": f"no se pudo actualizar ({state['error'][:120]}); última copia buena: {since}",
                        "title": "El catálogo de la tienda no se está actualizando",
                        "options": options_for("catalogo_caido", ctx)})
        low = [p for p in ctx.shared.list("products") if p.get("stock") is not None and 0 < p["stock"] <= cfg.low_stock]
        if low:
            names = ", ".join(f"{p['title']} ({p['stock']})" for p in low[:5])
            out.append({"kind": "stock_bajo", "ref": "stock", "score": 20, "reason": f"quedan pocas unidades: {names}",
                        "title": f"Poco stock en {len(low)} producto{'s' if len(low) > 1 else ''}",
                        "options": options_for("stock_bajo", ctx)})
        return out

    def execute(self, action, ctx):
        raise ActionError("tareas no ejecuta acciones")
