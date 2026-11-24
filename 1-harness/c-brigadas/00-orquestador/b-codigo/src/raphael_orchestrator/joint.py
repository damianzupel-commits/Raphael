"""Trabajo CONJUNTO: varias brigadas bajo el mando del orquestador, por un DAG validado por código.

Portado de JarvisRemote `orquestador/turno.py` (`run_conjunto`, `combinar_reportes`). Cada brigada trabaja por separado
y sin enterarse de las otras: su jefe (por `ctx.ask`, vigilado por el watchdog) recibe SU sub-tarea y, si depende de
otras, sus reportes como DATO (`context`, separado del pedido). El mando concluye y la voz comunica UNA respuesta.

  - Una brigada que falla, que el watchdog corta o que se pasa del presupuesto entra como degradada, con aviso; las
    demás siguen, y las que dependen de ella arrancan igual (con ese reporte degradado).
  - Si alguna de las brigadas es privada, el mando y la voz trabajan solo con modelos locales (`private=True`).
  - Todo lo que el modelo propone (reparto, dependencias, conclusión) lo controla código.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from raphael_core.engine import reports as R
from raphael_core.engine.reports import InternalReport, clip

from . import command
from .config import OrchestratorConfig
from .plan import apply_budget
from .ports import any_private, role_llm
from .routing import Route, candidates
from .watchdog import Log, limits_for, supervise

_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def combine_reports(reports: list[tuple[str, InternalReport]], conclusion: str = "", conclusion_confidence: str = "",
                    warnings: list[str] | None = None) -> InternalReport:
    """Une los reportes de varias brigadas en UNO, por CÓDIGO (ningún modelo en el medio): la voz y su verificador lo
    tratan igual que al de una sola. No inventa ni resume: concatena los resúmenes rotulados por brigada y une las listas
    tal cual; la confianza es la más baja; los pendientes conservan su número real; lo que no entra queda avisado."""
    n = max(1, len(reports))
    top = max(200, (R.MAX_SUMMARY - len(conclusion) - 40 - 20 * n) // n)
    notes: list[str] = list(warnings or [])
    confs = [r.confidence for _n, r in reports] + ([conclusion_confidence] if conclusion and conclusion_confidence else [])
    lines = ([f"[Conclusión del orquestador] {conclusion}"] if conclusion else []) \
        + [f"[{name}] {clip(r.summary, top)}" for name, r in reports]

    def join(key: str, limit: int, ident=None) -> list:
        out, seen = [], set()
        for _name, r in reports:
            for item in r.to_dict()[key]:
                k = ident(item) if ident else None
                if k is not None and k in seen:
                    continue
                seen.add(k)
                out.append(item)
        if len(out) > limit:
            notes.append(f"trabajo conjunto: {key} recortado de {len(out)} a {limit}")
        return out[:limit]

    sources = join("sources", R.MAX_SOURCES, lambda s: (s["type"], s["ref"]))
    refs = {s["ref"] for s in sources}
    findings = join("findings", R.MAX_FINDINGS)
    for f in findings:   # una fuente que quedó afuera por el tope no puede seguir citada
        f["sources"] = [r for r in f["sources"] if r in refs]
    own_warnings = [w for _n, r in reports for w in r.warnings]
    return InternalReport.validate({
        "version": R.REPORT_VERSION,
        "brigade": "+".join(r.brigade for _n, r in reports)[:80],
        "summary": clip("\n".join(lines), R.MAX_SUMMARY),
        "findings": findings, "sources": sources,
        "artifacts": join("artifacts", R.MAX_ARTIFACTS, lambda a: (a["type"], a["ref"])),
        "confidence": max(confs, key=lambda c: _CONF_ORDER.get(c, 2)) if confs else "low",
        "not_found": join("not_found", R.MAX_LIST, lambda x: x),
        "pending_proposals": join("pending_proposals", R.MAX_LIST,
                                  lambda p: ("pid", p["pending_id"]) if p.get("pending_id") else ("id", p["id"])),
        "helpers": join("helpers", R.MAX_HELPERS, lambda h: h["id"]),
        "failures": join("failures", R.MAX_HELPERS),
        "warnings": list(dict.fromkeys(notes + own_warnings))[:R.MAX_LIST],
        "degraded": any(r.degraded for _n, r in reports),
    })


async def run_joint(ctx: Any, route: Route, emit: Any, cfg: OrchestratorConfig, *, session: str | None = None,
                    remember: bool = True) -> Any:
    """El turno conjunto: reparto -> DAG por niveles -> conclusión -> voz. Devuelve un `turn.Turn`."""
    from .turn import literal, speak

    t0 = time.monotonic()
    catalog = {b["id"]: b for b in ctx.catalog()}
    cands = candidates(list(catalog.values()))
    brigades = [b for b in route.brigades if b in cands]
    if len(brigades) < 2:
        if not brigades:
            return await literal(ctx, "No hay brigadas disponibles para este pedido.", "error", emit, route=route)
        from .turn import run_brigade

        return await run_brigade(ctx, brigades[0], route.request, emit, cfg, session=session, route=route,
                                 remember=remember)
    names = {b: catalog[b].get("name") or b for b in brigades}
    private = any_private(ctx, brigades)
    j = cfg.joint
    mando = role_llm(ctx, "mando", private=private, temperature=0.1, max_tokens=1200)
    user = getattr(getattr(ctx, "identity", None), "user", "") or ""
    purposes = {b: clip(cands[b].description or names[b], 300) for b in brigades}
    plan = await command.split(route.request, purposes, llm=mando if j.split_llm else None, cands=cands, user=user,
                               dag=j.dag)
    plan = apply_budget(plan, max_brigades=j.max_brigades, max_levels=j.max_levels)
    await emit({**plan.event(), "model": ctx.ai_label("mando", private=private), "private": private})
    t_plan = time.monotonic() - t0
    log = Log(ctx.data, cfg.watchdog.keep)
    loop = asyncio.get_running_loop()
    ready: dict[str, asyncio.Future] = {b: loop.create_future() for b in plan.tasks}

    async def node(b: str) -> InternalReport:
        before = [a for a in plan.after.get(b, ()) if a in ready]
        previous = [(names[a], await ready[a]) for a in before]
        if before:
            await emit({"type": "stage", "brigade": b, "after": before})

        async def tagged(ev: dict) -> None:
            await emit({**ev, "brigade": b})

        context = command.context_for(previous) if previous else ""
        try:
            report, cut = await supervise(lambda feed: ctx.ask(b, plan.tasks[b], on_event=feed, context=context), tagged,
                                          brigade=b, brigade_name=names[b],
                                          limits=limits_for(catalog[b].get("watch"), cfg.watchdog), ctx=ctx, log=log,
                                          enabled=cfg.watchdog.enabled)
            if report is None:
                report = R.degraded_report(b, [], cut or "el watchdog cortó a esta brigada")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - el fallo de una brigada se reporta; las otras siguen
            report = R.degraded_report(b, [], f"la brigada no pudo trabajar: {type(exc).__name__}: {str(exc)[:160]}")
        if not ready[b].done():
            ready[b].set_result(report)
        return report

    tasks = {b: asyncio.ensure_future(node(b)) for b in plan.tasks}
    done, pending = await asyncio.wait(set(tasks.values()), timeout=j.max_seconds)
    for t in pending:
        t.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    results: list[tuple[str, InternalReport]] = []
    for b, t in tasks.items():
        if t in done and not t.cancelled() and t.exception() is None:
            rep = t.result()
        else:
            rep = R.degraded_report(b, [], f"se pasó el presupuesto del turno ({int(j.max_seconds)}s) y se cortó")
            await emit({"type": "report", "brigade": b, "report": rep.to_dict()})
        results.append((names[b], rep))
    t1 = time.monotonic()
    await emit({"type": "concluding", "model": ctx.ai_label("mando", private=private)})
    conclusion, conf, why = await command.conclude(results, route.request, llm=mando if j.conclusion_llm else None,
                                                   user=user)
    await emit({"type": "conclusion", "text": conclusion, "confidence": conf, "reason": why})
    notes = list(plan.warnings) + ([] if conclusion else [clip(f"sin conclusión del orquestador: {why}", R.MAX_ITEM)])
    report = combine_reports(results, conclusion, conf, notes)
    await emit({"type": "report", "brigade": report.brigade, "joint": True, "report": report.to_dict()})
    timings = {"plan": round(t_plan, 2), "brigades": round(t1 - t0 - t_plan, 2),
               "command": round(t_plan + time.monotonic() - t1, 2)}
    return await speak(ctx, report, route.request, emit, cfg, session=session, brigade=report.brigade, private=private,
                       route=route, timings=timings, remember=remember, extra={"brigades": list(plan.tasks)})
