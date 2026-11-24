"""Pasos genéricos de validación de una brigada creada por borrador (los que nombra su `ValidationSpec`).

Cada paso es `async def step(ctx) -> {"ok": True | False | None, "detail": str}`; `ok=None` = SIN VALIDAR (faltó un
prerrequisito: nunca cuenta como verde ni como rojo). `ctx` = {"clean": borrador, "catalog": registro de tools,
"step": el paso, "ask": async (pedido) -> (InternalReport, [tools usadas]) | InternalReport | None}.

`run_validation` los corre todos en orden. El ruteo se valida sin modelo; una respuesta necesita un modelo (ask).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .factory import classify, compile_spec

Ask = Callable[[str], Awaitable[Any]]


async def step_scope(ctx: dict) -> dict:
    """Menor privilegio: el jefe sin tools, cada efímero solo con tools que existen y que se le pueden dar."""
    clean, catalog = ctx["clean"], ctx["catalog"]
    bad = [f"{h['mode']}: {t} ({classify(t, catalog)['level']})" for h in clean["helpers"] for t in h["tools"]
           if classify(t, catalog)["level"] in ("unknown", "denied")]
    return {"ok": not bad, "detail": "; ".join(bad) or "tools dentro de lo permitido"}


async def step_routing(ctx: dict) -> dict:
    routing = compile_spec(ctx["clean"]).routing
    fails = [f"«{c['message'][:50]}» → {routing.classify(c['message'])} (se esperaba {c['mode']})"
             for c in ctx["step"]["cases"] if routing.classify(c["message"]) != c["mode"]]
    return {"ok": not fails, "detail": "; ".join(fails) or f"{len(ctx['step']['cases'])} casos bien ruteados"}


async def prereq_response(ctx: dict) -> str | None:
    """None si se puede correr; si no, el motivo (el paso queda SIN VALIDAR)."""
    return None if ctx.get("ask") else "hace falta un modelo para pedirle una respuesta a la brigada"


async def step_response(ctx: dict) -> dict:
    missing = await prereq_response(ctx)
    if missing:
        return {"ok": None, "detail": missing}
    step = ctx["step"]
    rep = await ctx["ask"](step["message"])
    used = set(ctx.get("used_tools") or [])
    if isinstance(rep, tuple):
        rep, tools = rep
        used |= set(tools)
    if rep is None:
        return {"ok": None, "detail": "la brigada no devolvió reporte"}
    text = " ".join([rep.summary, *(f.text for f in rep.findings)])
    fails = [f"no contiene /{p}/" for p in step["must_contain"] if not re.search(p, text, re.IGNORECASE)]
    fails += [f"no usó {t}" for t in step["must_use_tools"] if t not in used]
    if rep.degraded:
        fails.append("el reporte salió degradado")
    return {"ok": not fails, "detail": "; ".join(fails) or "respuesta dentro del criterio"}


async def run_validation(clean: dict, catalog: Mapping[str, Any], ask: Ask | None = None) -> list[dict]:
    """[{"id", "label", "ok", "detail"}] en el orden del ValidationSpec."""
    spec = compile_spec(clean)
    assert spec.validation is not None
    steps = {p["id"]: p for p in clean["validation"]["steps"]}
    runners = {"raphael_core.drafts.checks:step_scope": step_scope, "raphael_core.drafts.checks:step_routing": step_routing,
               "raphael_core.drafts.checks:step_response": step_response}
    used: list[str] = []
    out = []
    for s in spec.validation.steps:
        ctx = {"clean": clean, "catalog": catalog, "step": steps.get(s.id, {}), "ask": ask, "used_tools": used}
        try:
            res = await runners[s.runner](ctx)
        except Exception as exc:  # noqa: BLE001 - un paso que explota es rojo, con el motivo
            res = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}
        out.append({"id": s.id, "label": s.label, **res})
    return out
