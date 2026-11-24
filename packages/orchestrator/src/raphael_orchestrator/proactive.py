"""Avisos proactivos ("open loops"): el orquestador mira por su cuenta y AVISA; nunca ejecuta nada.

Reemplaza la idea de JarvisRemote `app/proactive.py` (que ampliaba casos y el vault llamando al agente: eso es de las
brigadas 07 y 09). Acá corre en los ganchos del harness (`on_event` y `tick`), que solo reciben un
`OrchestratorContext`: puede leer y dejar un aviso (`ctx.notify`), no aprobar ni ordenar.

  - pendiente nuevo que resuelve una persona (o todos, según config) -> aviso;
  - el jefe de una brigada quedó caído, o su chequeo de salud la dejó sin atender -> aviso;
  - el harness propone dejar algo en automático (confianza progresiva) -> aviso;
  - un pendiente que lleva más de `remind_after_hours` sin resolverse -> un recordatorio (una sola vez por pendiente).
Cada aviso se da una sola vez (se recuerda en el espacio del orquestador).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import OrchestratorConfig

COLLECTION = "proactive"
EVENTS = ("pendiente.creado", "brigada.jefe_caido", "brigada.salud", "confianza.propuesta")


def _once(ctx: Any, key: str) -> bool:
    """True la primera vez que se pide `key` (y lo deja anotado)."""
    if ctx.data.get(COLLECTION, key):
        return False
    ctx.data.put(COLLECTION, key, {"at": ctx.now().isoformat(timespec="seconds")})
    return True


def _name(ctx: Any, brigade: str) -> str:
    return next((b.get("name") or brigade for b in ctx.catalog() if b.get("id") == brigade), brigade)


def on_event(ctx: Any, cfg: OrchestratorConfig, event: str, data: dict) -> dict | None:
    """El aviso que corresponde a un evento (o None). Lo deja con `ctx.notify`."""
    p = cfg.proactive
    if not p.enabled:
        return None
    if event == "pendiente.creado":
        level = data.get("level")
        if p.new_pending == "none" or (p.new_pending == "human" and level != "humano"):
            return None
        pid = data.get("id")
        if not _once(ctx, f"pending-{pid}"):
            return None
        doc = next((x for x in ctx.pending() if x["id"] == pid), {})
        what = doc.get("summary") or data.get("type") or "un pendiente"
        verb = "Te espera algo para resolver vos" if level == "humano" else "Hay algo esperando tu aprobación"
        return ctx.notify(f"{verb}: #{pid} ({what}).", kind="pending", pending=pid, brigade=data.get("brigade"))
    if event == "brigada.jefe_caido":
        b = data.get("brigade", "")
        if not _once(ctx, f"chief-{b}-{ctx.now().date()}"):
            return None
        return ctx.notify(f"El jefe de {_name(ctx, b)} quedó caído ({data.get('why', 'sin detalle')}). Revivilo desde el "
                          "panel o volvé a montar la brigada.", kind="chief_down", brigade=b)
    if event == "brigada.salud" and data.get("down"):
        b = data.get("brigade", "")
        if not _once(ctx, f"health-{b}-{ctx.now().isoformat(timespec='hours')}"):
            return None
        return ctx.notify(f"{_name(ctx, b)} dejó de atender: su chequeo de salud dio mal. Vuelve sola cuando dé bien.",
                          kind="health", brigade=b)
    if event == "confianza.propuesta":
        pid = data.get("id")
        if not _once(ctx, f"trust-{pid}"):
            return None
        return ctx.notify(f"Aprobaste muchas veces seguidas «{data.get('action')}» sin cambios: te propongo dejarla en "
                          f"automático. Está como pendiente #{pid}; decidís vos.", kind="trust", pending=pid)
    return None


def tick(ctx: Any, cfg: OrchestratorConfig, now: datetime) -> list[dict]:
    """Recordatorios de pendientes viejos. Solo lee y avisa."""
    p = cfg.proactive
    if not p.enabled or p.remind_after_hours <= 0:
        return []
    out = []
    for doc in ctx.pending():
        try:
            age = (now - datetime.fromisoformat(doc.get("created"))).total_seconds() / 3600
        except (TypeError, ValueError):
            continue
        if age >= p.remind_after_hours and _once(ctx, f"remind-{doc['id']}"):
            out.append(ctx.notify(f"Sigue esperando desde hace {int(age)} h: #{doc['id']} ({doc.get('summary') or 'pendiente'}).",
                                  kind="reminder", pending=doc["id"]))
    return out
