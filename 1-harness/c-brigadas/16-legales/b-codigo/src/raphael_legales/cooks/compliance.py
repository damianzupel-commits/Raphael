"""Cumplimiento: checklist para un pyme argentino y verificación de las normas contra su fuente oficial.

El checklist (comando `checklist`, solo lectura) mezcla lo que se deduce del archivo con lo que la persona respondió en la
config. `verificar_norma` (automático, solo lee una página pública) guarda cuándo se consultó cada fuente y avisa si la
página cambió desde la vez anterior. Sin red o con `fuentes.modo = off` queda "sin verificar" y lo dice; nunca inventa.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from raphael_core import Action, ActionError, Cook

from ..compliance import build, source_status
from ..config import legales_config
from ..disclaimer import DISCLAIMER
from ..norms import NORMS, norm_url
from ..sources import build_sources

AUTO_EVERY = timedelta(days=1)


class Compliance(Cook):
    name = "cumplimiento"
    version = "2.0.0"
    description = "Checklist de cumplimiento (datos personales, consumidor, facturación, Meta/WhatsApp) con fuentes consultadas."
    commands = {"checklist": "Checklist con estado de cada ítem y de su fuente",
                "normas": "Normas de partida y cuándo se consultó cada fuente",
                "verificar_normas": "Consulta ahora las fuentes oficiales {'ids': [opcional]}"}

    def command(self, name, data, ctx):
        cfg = legales_config(ctx.config)
        if name == "checklist":
            return {**build(ctx.shared, cfg, ctx.now()), "aviso": DISCLAIMER}
        if name == "normas":
            return [{"id": n.id, "title": n.title, "url": norm_url(n, cfg.fuentes.urls),
                     **source_status(ctx.shared, n.id, ctx.now(), cfg.fuentes.dias_vigencia)} for n in NORMS.values()]
        if name == "verificar_normas":
            ids = data.get("ids") or list(NORMS)
            bad = [i for i in ids if i not in NORMS]
            if bad:
                raise ActionError(f"norma desconocida: {', '.join(bad)}")
            for i in ids:
                ctx.request(Action("verificar_norma", {"id": i}, f"Verificar fuente de {NORMS[i].title}"))
            return self.command("normas", {}, ctx)
        return super().command(name, data, ctx)

    def tick(self, now, ctx):
        cfg = legales_config(ctx.config)
        if cfg.fuentes.modo != "real":
            return
        last = ctx.data.get("auto", "last")
        if last and now - datetime.fromisoformat(last["at"]) < AUTO_EVERY:
            return
        ctx.data.put("auto", "last", {"at": now.isoformat(timespec="seconds")})
        for n in NORMS.values():
            if source_status(ctx.shared, n.id, now, cfg.fuentes.dias_vigencia)["state"] != "consultada":
                ctx.request(Action("verificar_norma", {"id": n.id}, f"Verificar fuente de {n.title}"))

    def execute(self, action, ctx):
        if action.type != "verificar_norma":
            raise ActionError(f"cumplimiento no ejecuta '{action.type}'")
        norm = NORMS.get(action.data.get("id"))
        if norm is None:
            raise ActionError("norma desconocida")
        cfg = legales_config(ctx.config)
        res = build_sources(cfg.fuentes.modo, cfg.fuentes.timeout).check(norm, norm_url(norm, cfg.fuentes.urls), ctx.now())
        before = ctx.shared.get("norm_checks", norm.id)
        ctx.shared.put("norm_checks", norm.id, res.to_dict())
        if not res.ok:
            ctx.publish("norma.sin_verificar", {"id": norm.id, "error": res.error})
            return f"{norm.id}: sin verificar ({res.error})"
        if before and before.get("ok") and before.get("sha256") != res.sha256:
            ctx.publish("norma.cambio_detectado", {"id": norm.id, "url": res.url})
            return f"{norm.id}: la fuente CAMBIÓ desde la última consulta: revisala"
        ctx.publish("norma.verificada", {"id": norm.id})
        return f"{norm.id}: fuente consultada ({res.mode})"
