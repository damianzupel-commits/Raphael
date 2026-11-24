"""El orquestador que monta el harness (`installation.orchestrator.entry: "raphael_orchestrator.orchestrator:RaphaelOrchestrator"`
o el entry point `raphael`). Mismo código en los dos modos (DISENO §3.7); cambia la config:

  - `secretary` (instalación de la clienta, sin maestro): los mensajes de clientes se ordenan con `routing.order_cooks`;
    cuando habla la dueña, la atiende la Secretaria (`secretary.handle`).
  - `master` (Raphael personal): cuando habla la persona, primero una confirmación que esté esperando; después, si es
    trabajo de Secretaria (tareas, pendientes, aprobar, responder), la Secretaria; si no, ruteo -> turno (una brigada,
    trabajo conjunto, charla o autoconocimiento). Antes que todo, los comandos de borradores (`/brigadas`, …).
En los dos modos: avisos proactivos por los ganchos del harness (`on_event`, `tick`), que solo leen y avisan.
"""

from __future__ import annotations

from typing import Any

from raphael_core.contract import Orchestrator, OwnerReply

from . import __version__, confirm, drafts_cmd, proactive, secretary
from .config import OrchestratorConfig, config_from
from .ports import routing_llm
from .routing import order_cooks
from .turn import decide, run_route


class RaphaelOrchestrator(Orchestrator):
    name = "raphael"
    version = __version__
    description = "Orquestador de Raphael: ruteo, mando, voz y Secretaria."
    consumes = proactive.EVENTS

    def __init__(self, config: dict | None = None) -> None:
        self.cfg: OrchestratorConfig = config_from(config or {})
        self.config = dict(config or {})

    def configure(self, config: dict) -> None:
        self.config = dict(config)
        self.cfg = config_from(config)   # una config inválida falla acá, al montar (no en un turno)

    # --- ganchos del harness: solo leen y avisan ---------------------------------------------------------------------------
    def on_event(self, event: str, data: dict, ctx: Any) -> None:
        proactive.on_event(ctx, self.cfg, event, data)

    def tick(self, now: Any, ctx: Any) -> None:
        proactive.tick(ctx, self.cfg, now)

    # --- mensajes de clientes -----------------------------------------------------------------------------------------
    async def route(self, msg: Any, ctx: Any, cooks: list[Any]) -> list[Any]:
        descriptions = {}
        for b in ctx.catalog():
            for c in (b.get("cooks") or {}):
                descriptions[f"{b['id']}/{c}"] = b.get("description") or b.get("name") or b["id"]
        return await order_cooks(msg, ctx, cooks, llm=routing_llm(ctx, self.cfg), fallback=self.cfg.routing.fallback_cook,
                                 descriptions=descriptions)

    # --- la persona ---------------------------------------------------------------------------------------------------
    async def talk_to_owner(self, text: str, ctx: Any) -> OwnerReply:
        cmd = drafts_cmd.parse(text)
        if cmd is not None:   # lo interpreta código, solo si el mensaje EMPIEZA con el comando
            session = getattr(ctx, "session", None) or "default"
            if confirm.waiting(ctx, session):
                confirm.clear(ctx, session)
            reply = await drafts_cmd.run(ctx, cmd[0], cmd[1], enabled=self.cfg.drafts_enabled(getattr(ctx, "edition", "")))
            await ctx.emit({"type": "final", "reply": reply, "origin": "command", "literal": True})
            return OwnerReply(reply, meta={"via": "command", "command": cmd[0]})
        if self.cfg.mode == "secretary":
            return await secretary.handle(ctx, text, self.cfg)
        return await self._master(text, ctx)

    async def _master(self, text: str, ctx: Any) -> OwnerReply:
        session = getattr(ctx, "session", None) or "default"
        waiting = confirm.waiting(ctx, session)
        if waiting and not (confirm.is_yes(text) or confirm.is_no(text)):
            confirm.clear(ctx, session)          # otra frase: la propuesta se descarta y la charla sigue normal
            ctx.record("propuesta_descartada", motivo="otra frase")
            waiting = None
        if waiting or secretary.looks_like_owner_work(text):
            r = await secretary.handle(ctx, text, self.cfg, session)
            return OwnerReply(r.text, r.suggestions, r.tasks, r.card, {**r.meta, "via": "secretary"})
        route = await decide(ctx, text, self.cfg)
        turn = await run_route(ctx, route, getattr(ctx, "emit", None), self.cfg, session=session)
        return OwnerReply(turn.text, meta={"via": turn.via, "route": route.event(), "fidelity": turn.fidelity,
                                           "timings": turn.timings})
