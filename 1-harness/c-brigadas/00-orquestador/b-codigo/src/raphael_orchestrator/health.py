"""Chequeo de salud del orquestador: qué anda, qué cae a reglas y qué falta cargar. Solo lee; nunca muestra claves.

`report(ctx, cfg, speech)` arma un dict con `ok`, `warnings` (qué falta, en castellano) y el detalle:
  - modo (`master` o `secretary`) y edición;
  - por rol (`mando`, `voz`, `ruteo`): el modelo que usaría o «sin modelo» (entonces responde por reglas/plantilla);
  - privacidad: las brigadas privadas montadas y si hay modelo LOCAL para ellas. Sin local, NO se manda a la nube;
  - voz hablada (adaptador y estado).
Un aviso no es un error: el orquestador sigue andando sin IA (reglas y plantilla). `ok` es False solo si la config no sirve.
"""

from __future__ import annotations

from typing import Any

from .config import OrchestratorConfig
from .proactive import no_ai_problems
from .speech import Speech, describe

ROLES = ("mando", "voz", "ruteo")


async def report(ctx: Any, cfg: OrchestratorConfig, speech: Speech | None = None) -> dict:
    roles = {r: {"available": ctx.has_ai(r), "model": ctx.ai_label(r)} for r in ROLES}
    private = [b["id"] for b in ctx.catalog() if b.get("private") and b.get("mounted", True)]
    local = ctx.has_ai("voz", private=True)
    out: dict[str, Any] = {
        "ok": True, "mode": cfg.mode, "edition": getattr(ctx, "edition", ""), "roles": roles,
        "privacy": {"private_brigades": private, "local_model": local,
                    "private_goes_to_cloud": False},   # por construcción: la pasarela solo acepta locales para lo privado
        "warnings": [msg for _key, msg in no_ai_problems(ctx)],
    }
    if speech is not None:
        st = await speech.status()
        out["speech"] = st
        if not (st.get("stt") or {}).get("ok") or not (st.get("tts") or {}).get("ok"):
            out["warnings"].append(describe(st))
    return out
