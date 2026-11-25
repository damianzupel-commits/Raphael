"""Vigilancia de tendencias: revisa sola los temas que le tocan (en cada tick) y avisa por el bus."""

from __future__ import annotations

import re

from raphael_core import ActionError

from .. import trends
from .base import InvCook


class Trends(InvCook):
    name = "tendencias"
    version = "2.0.0"
    description = "Sigue los temas que la persona define y avisa cuando hay algo nuevo y relevante, con resumen y fuentes."
    interest_pattern = re.compile(r"tendencia|vigil[aá]|monitore|avis[aá]me cuando")
    commands = {
        "temas": "temas que se vigilan", "avisos": "últimos avisos {'tema','limite'}",
        "seguir": "empieza a vigilar {'tema','consultas','palabras_clave','cada_horas','umbral'}",
        "pausar": "pausa un tema {'tema'}", "reanudar": "reanuda un tema {'tema'}",
        "revisar": "revisa ahora un tema {'tema'} (o los que tocan)"}

    def tick(self, now, ctx) -> None:
        env = self.inv(ctx).env
        try:
            trends.review(env)
        except Exception as exc:  # noqa: BLE001 - una revisión caída no tumba al harness; queda en la auditoría
            ctx.record("tendencias_fallo", error=type(exc).__name__)

    def run_command(self, name, data, ctx):
        env = self.inv(ctx).env
        if name == "temas":
            return trends.watches(env)
        if name == "avisos":
            return trends.alerts(env, data.get("tema") or None, int(data.get("limite", 20)))
        if name == "seguir":
            w = trends.follow(env, data.get("tema", ""), queries=data.get("consultas"), keywords=data.get("palabras_clave"),
                              interval_hours=data.get("cada_horas"), min_score=float(data.get("umbral", 0.5)))
            return {k: v for k, v in w.items() if k != "seen"}
        if name in ("pausar", "reanudar"):
            return trends.set_active(env, data.get("tema", ""), name == "reanudar")
        if name == "revisar":
            return trends.review(env, data.get("tema") or None, force=bool(data.get("tema")))
        return super().run_command(name, data, ctx)

    def run_action(self, action, ctx):
        if action.type == "borrar_tema":
            r = trends.delete(self.inv(ctx).env, action.data.get("tema", ""))
            return f"Tema borrado, con {r['alerts_deleted']} avisos."
        raise ActionError(f"tendencias no ejecuta '{action.type}'")
