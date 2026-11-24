"""Un TURNO: pedido -> (ruteo) -> jefe de la brigada por el harness, vigilado -> reporte -> voz -> UN mensaje.

Portado de JarvisRemote `orquestador/turno.py` (turno de una brigada) y de la parte de `server.py` que resolvía charla,
autoconocimiento y errores. Es el único lugar donde se cierra un turno con un `final` para la persona (invariante: solo
el orquestador le habla).

  - El jefe se pide con `ctx.ask(...)` (harness): el orquestador nunca toca a una brigada directo.
  - Si el watchdog corta, su aviso es texto de CÓDIGO y sale LITERAL (no pasa por la voz).
  - Si la brigada es privada, la voz trabaja con `private=True` (solo local; sin modelo local, plantilla).
  - Siempre hay un `final`: sin voz, o sin un mensaje fiel, sale la plantilla desde el reporte.
  - La charla queda en la memoria de la sesión (solo la lee la voz).
El trabajo conjunto (varias brigadas, DAG) está en `joint.py`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from raphael_core.contract import ActionError
from raphael_core.engine.reports import InternalReport

from . import routing, voice
from .config import OrchestratorConfig
from .memory import Conversation, MemorySettings
from .ports import routing_llm, voice_llm, voice_settings
from .routing import Route
from .self_report import system_report
from .watchdog import Log, limits_for, supervise

Emit = Callable[[dict], Awaitable[None]]


@dataclass
class Turn:
    text: str                           # lo que se le dijo a la persona (el `final`)
    via: str                            # llm | llm+sources | llm+directives | template | watchdog | literal
    report: InternalReport | None = None
    route: Route | None = None
    fidelity: dict | None = None
    timings: dict = field(default_factory=dict)


async def _noop(ev: dict) -> None:
    return None


def conversation_of(ctx: Any, cfg: OrchestratorConfig) -> Conversation:
    m = cfg.memory
    return Conversation(ctx.data, MemorySettings(m.enabled, m.max_turns, m.max_summary, m.max_request, m.max_message))


def _entry(ctx: Any, brigade: str) -> dict:
    return next((b for b in ctx.catalog() if b.get("id") == brigade), {})


def session_of(ctx: Any, session: str | None) -> str:
    """La sesión de la charla: la que se pasa o la del `OwnerContext` (la app, el WhatsApp de la dueña, la voz)."""
    return session or getattr(ctx, "session", None) or "default"


def _user(ctx: Any) -> str:
    return getattr(getattr(ctx, "identity", None), "user", "") or ""


async def literal(ctx: Any, text: str, origin: str, emit: Emit, *, route: Route | None = None) -> Turn:
    """Un texto de código que sale tal cual (comando, error, corte del watchdog, confirmación)."""
    await emit(voice.literal(text, origin))
    return Turn(text, "literal" if origin != "watchdog" else "watchdog", route=route)


async def speak(ctx: Any, report: InternalReport, request: str, emit: Emit, cfg: OrchestratorConfig, *,
                session: str | None, brigade: str, private: bool, route: Route | None = None, timings: dict | None = None,
                remember: bool = True, extra: dict | None = None) -> Turn:
    """Reporte -> mensaje por la voz -> `final`. Lo usan el turno simple, el autoconocimiento y (en O3) el conjunto."""
    t0 = time.monotonic()
    session = session_of(ctx, session)
    conv = conversation_of(ctx, cfg)
    label = ctx.ai_label("voz", private=private)
    await emit({"type": "communicating", "model": label, "private": private})
    msg = await voice.communicate(report, request, llm=voice_llm(ctx, cfg, private=private),
                                  settings=voice_settings(ctx, cfg), history=conv.for_prompt(session, _user(ctx)),
                                  model=label)
    tm = dict(timings or {})
    tm["voice"] = round(time.monotonic() - t0, 2)
    await emit({"type": "final", "reply": msg.text, "origin": "orchestrator", "brigade": brigade, "timings": tm,
                **msg.event(), **(extra or {})})
    if remember:
        conv.record(session, request, brigade, msg.text, when=ctx.now().isoformat(timespec="seconds"))
    return Turn(msg.text, msg.via, report, route, msg.verification.to_dict(), tm)


async def run_brigade(ctx: Any, brigade: str, request: str, emit: Emit, cfg: OrchestratorConfig, *, session: str | None = None,
                      context: str = "", route: Route | None = None, remember: bool = True) -> Turn:
    """El turno de UNA brigada: su jefe (vigilado) y la voz."""
    t0 = time.monotonic()
    entry = _entry(ctx, brigade)
    limits = limits_for(entry.get("watch"), cfg.watchdog)

    def run(feed):
        return ctx.ask(brigade, request, on_event=feed, context=context)

    try:
        report, cut = await supervise(run, emit, brigade=brigade, brigade_name=entry.get("name") or brigade,
                                      limits=limits, ctx=ctx, log=Log(ctx.data, cfg.watchdog.keep),
                                      enabled=cfg.watchdog.enabled)
    except asyncio.CancelledError:
        raise
    except ActionError as exc:   # no está montada o no tiene jefe: lo dice código
        return await literal(ctx, f"No pude mandarle el pedido a {entry.get('name') or brigade}: {exc}.", "error", emit,
                             route=route)
    chief_s = round(time.monotonic() - t0, 2)
    if report is None:
        return await literal(ctx, cut, "watchdog", emit, route=route)
    return await speak(ctx, report, request, emit, cfg, session=session, brigade=brigade, private=ctx.is_private(brigade),
                       route=route, timings={"chief": chief_s}, remember=remember)


async def run_chat(ctx: Any, request: str, emit: Emit, cfg: OrchestratorConfig, *, session: str | None = None,
                   route: Route | None = None, remember: bool = True) -> Turn:
    """Charla social: una llamada a la voz, sin brigada ni reporte."""
    t0 = time.monotonic()
    session = session_of(ctx, session)
    conv = conversation_of(ctx, cfg)
    label = ctx.ai_label("voz")
    msg = await voice.chat(request, llm=voice_llm(ctx, cfg), settings=voice_settings(ctx, cfg),
                           history=conv.for_prompt(session, _user(ctx)), model=label)
    tm = {"voice": round(time.monotonic() - t0, 2)}
    await emit({"type": "final", "reply": msg.text, "origin": "orchestrator", "brigade": "orquestador", "timings": tm,
                **msg.event()})
    if remember:
        conv.record(session, request, "orquestador", msg.text, when=ctx.now().isoformat(timespec="seconds"))
    return Turn(msg.text, msg.via, None, route, None, tm)


async def run_self(ctx: Any, request: str, emit: Emit, cfg: OrchestratorConfig, *, session: str | None = None,
                   route: Route | None = None, drafts: list[str] | None = None, remember: bool = True) -> Turn:
    """"¿Qué brigadas tenés?": el reporte lo arma código desde el catálogo y la voz lo comunica."""
    rep = system_report(ctx.catalog(), drafts=drafts, edition=getattr(ctx, "edition", ""),
                        drafts_enabled=cfg.drafts_enabled(getattr(ctx, "edition", "personal")))
    await emit({"type": "report", "brigade": "orquestador", "report": rep.to_dict()})
    return await speak(ctx, rep, request, emit, cfg, session=session, brigade="orquestador", private=False, route=route,
                       remember=remember)


async def decide(ctx: Any, text: str, cfg: OrchestratorConfig, *, brigade: str | None = None,
                 joint_enabled: bool | None = None) -> Route:
    """El ruteo de un pedido de la persona con el catálogo del harness y la config."""
    r = cfg.routing
    return await routing.route(text, ctx.catalog(), brigade=brigade, llm=routing_llm(ctx, cfg),
                               default_brigade=r.default_brigade, min_words=r.min_words_for_classifier,
                               assistant=getattr(getattr(ctx, "identity", None), "assistant", "") or "",
                               chat_direct=cfg.chat_direct, self_knowledge=cfg.self_knowledge,
                               joint_enabled=cfg.joint_enabled() if joint_enabled is None else joint_enabled)


async def run_route(ctx: Any, route: Route, emit: Emit | None, cfg: OrchestratorConfig, *, session: str | None = None,
                    remember: bool = True) -> Turn:
    """Ejecuta una decisión del ruteo. Lo que no tiene brigada lo resuelve código o la voz."""
    emit = emit or _noop
    await emit(route.event())
    ctx.record("ruteo", tipo=route.kind, via=route.via, brigada=route.brigade, brigadas=list(route.brigades))
    if route.kind == "chat":
        return await run_chat(ctx, route.request, emit, cfg, session=session, route=route, remember=remember)
    if route.kind == "self":
        return await run_self(ctx, route.request, emit, cfg, session=session, route=route, remember=remember)
    if route.kind == "missing":
        return await literal(ctx, f"No puedo mandarle esto a esa brigada: {route.reason}.", "error", emit, route=route)
    if route.kind == "none":
        return await literal(ctx, "No tengo una brigada que pueda atender esto ahora. Decime a cuál mandarlo con /id, "
                             "o montá una desde «Agregar brigadas».", "error", emit, route=route)
    if route.kind == "joint":
        from .joint import run_joint

        return await run_joint(ctx, route, emit, cfg, session=session, remember=remember)
    return await run_brigade(ctx, route.brigade or "", route.request, emit, cfg, session=session, route=route,
                             remember=remember)
