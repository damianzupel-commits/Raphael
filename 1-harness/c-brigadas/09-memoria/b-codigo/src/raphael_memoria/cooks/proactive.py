"""Proactivo y actividad: lo que Cerebro hace SOLO, y el feed de «lo que hizo mientras no estabas».

Apagado por default (`proactive.enabled`). Prendido, en cada vuelta: reindexa lo que haga falta (cómputo local) y mira si
hay notas para consolidar; si las hay, PIDE la consolidación (que queda pendiente de aprobación: escribe notas). También
avisa cuando el modelo local o los embeddings se apagan o vuelven (un aviso por cambio, no uno por tick).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from raphael_core import Action, Cook, Health, Origin

from .. import actions
from ..brain import Brain


class Proactive(Cook):
    name = "proactivo"
    version = "2.0.0"
    description = "Trabaja solo cuando está prendido: reindexa, propone consolidar y avisa si se cae el modelo local."
    commands = {"actividad": "Lo que hizo solo, lo más nuevo primero {'limit'}",
                "pasada": "Correr ahora una pasada proactiva (aunque esté apagado el automático)"}

    def tick(self, now, ctx) -> None:
        brain = Brain.from_ctx(ctx)
        self._watch_degradation(brain, ctx)
        if not brain.cfg.proactive.enabled:
            return
        state = ctx.shared.get("estado", "proactivo") or {}
        last = state.get("ultima_pasada")
        if last and now - _parse(last) < timedelta(minutes=brain.cfg.proactive.every_minutes):
            return
        ctx.shared.put("estado", "proactivo", {**state, "ultima_pasada": now.isoformat(timespec="seconds")})
        self._pass(brain, ctx)

    def _pass(self, brain: Brain, ctx) -> dict:
        out: dict = {}
        if brain.embedder.name != "off" and brain.embedder.embed("prueba") is not None:
            out["reindex"] = ctx.request(Action("reindexar", {}, "Reindexar la memoria (pasada proactiva)", origin=Origin.SYSTEM))
        plan = brain.consolidate(dry_run=True)
        state = ctx.shared.get("estado", "proactivo") or {}
        asked = set(state.get("pedidos", []))
        new = [p for p in plan.get("a_consolidar", []) if p["consolidation_id"] not in asked]
        out["consolidacion"] = {"estado": plan["estado"], "a_consolidar": len(plan.get("a_consolidar", [])), "nuevos": len(new)}
        if new:
            if brain.has_model():
                # un grupo ya pedido no se vuelve a pedir (si lo rechazaron, no insiste hasta que cambien las notas)
                ctx.shared.put("estado", "proactivo", {**state, "pedidos": sorted(asked | {p["consolidation_id"] for p in new})[-200:]})
                ctx.request(Action("consolidar", {}, f"Consolidar {len(new)} grupo(s) de notas relacionadas", origin=Origin.SYSTEM))
            else:
                actions.log_activity(ctx, "info", "Hay notas para consolidar pero no hay modelo local prendido.", out["consolidacion"])
        elif not plan.get("a_consolidar"):
            actions.log_activity(ctx, "consolidacion", f"Consolidación sin grupos nuevos ({plan['estado']}).")
        return out

    def _watch_degradation(self, brain: Brain, ctx) -> None:
        """Un aviso por CAMBIO de estado del modelo local o de los embeddings (no uno por tick)."""
        status = {"modelo_local": brain.has_model(), "embeddings": brain.embedder.name != "off"
                  and brain.embedder.embed("prueba") is not None}
        prev = ctx.shared.get("estado", "salud")
        ctx.shared.put("estado", "salud", status)
        if prev is not None and prev != status:
            degraded = not all(status.values())
            ctx.publish("memoria.degradada" if degraded else "memoria.recuperada", status)
            actions.log_activity(ctx, "aviso", "Cerebro degradado: " + _what(status) if degraded else "Cerebro recuperado.", status)

    def command(self, name: str, data: dict, ctx):
        if name == "actividad":
            items = (ctx.shared.get("estado", "actividad") or {}).get("items", [])
            return items[: max(1, min(int(data.get("limit", 40)), 200))]
        if name == "pasada":
            return self._pass(Brain.from_ctx(ctx), ctx)
        return super().command(name, data, ctx)

    def execute(self, action, ctx):
        return actions.execute(ctx, action)

    def health(self, ctx) -> Health:
        return Health(True)


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _what(status: dict) -> str:
    out = []
    if not status["modelo_local"]:
        out.append("no hay modelo local (la síntesis queda por reglas)")
    if not status["embeddings"]:
        out.append("no responden los embeddings (la búsqueda queda por palabra clave)")
    return "; ".join(out)

