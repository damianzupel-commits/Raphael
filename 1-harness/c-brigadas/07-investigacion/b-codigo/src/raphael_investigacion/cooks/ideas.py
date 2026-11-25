"""Ideas y prototipos: ideas, evaluación, specs y prototipos que solo corren aprobados y en el espacio aislado."""

from __future__ import annotations

import re

from raphael_core import ActionError

from .. import ideas
from .base import InvCook


class Ideas(InvCook):
    name = "ideas"
    version = "2.0.0"
    description = "Registra y evalúa ideas, escribe specs y guarda prototipos acotados."
    interest_pattern = re.compile(r"\bideas?\b|prototip|\bspec\b|especificaci[oó]n|brainstorm")
    commands = {
        "ranking": "ideas por puntaje", "idea": "una idea {'id'}", "spec": "la spec de una idea {'id'}",
        "nueva": "registra una idea {'title','problem','pitch','tags'}", "generar": "ideas a partir de un tema {'seed','n'}",
        "evaluar": "puntúa {'id','impacto','encaje','esfuerzo','riesgo'} (sin puntajes: los sugiere el modelo local)",
        "escribir_spec": "escribe la spec {'id'}", "guardar_prototipo": "guarda código Python SIN correrlo {'id','code','name'}",
        "prototipos": "prototipos guardados {'idea'}"}

    def run_command(self, name, data, ctx):
        env = self.inv(ctx).env
        if name == "ranking":
            return ideas.ranking(env)
        if name == "idea":
            return ideas.get(env, data.get("id", ""))
        if name == "spec":
            return env.space.get("specs", data.get("id", "")) or {"error": "esa idea todavía no tiene spec"}
        if name == "nueva":
            return ideas.add_idea(env, data.get("title", ""), data.get("problem", ""), data.get("pitch", ""), data.get("tags"))
        if name == "generar":
            return ideas.generate(env, data.get("seed", ""), int(data.get("n", 5)))
        if name == "evaluar":
            sc = {k: data.get(k) for k in ideas.SCORES}
            return ideas.evaluate(env, data.get("id", ""), sc if all(sc.values()) else None)
        if name == "escribir_spec":
            return ideas.write_spec(env, data.get("id", ""))
        if name == "guardar_prototipo":
            r = ideas.save_prototype(env, data.get("id", ""), data.get("code", ""), data.get("name", "prototipo"))
            return {k: v for k, v in r.items() if k != "code"}
        if name == "prototipos":
            return [{k: p[k] for k in ("id", "name", "review", "runs")} for p in env.space.list("prototypes")
                    if not data.get("idea") or p["idea"] == data["idea"]]
        return super().run_command(name, data, ctx)

    def run_action(self, action, ctx):
        if action.type == "correr_prototipo":
            r = ideas.run_prototype(self.inv(ctx).env, action.data.get("id", ""))
            if not r["ran"]:
                return "No corrió: " + "; ".join(r["problems"])
            return (f"Corrió en {r['seconds']} s, salida {r['exit_code']}" + (" (se pasó del tiempo)" if r["timed_out"] else "")
                    + f"\n{r['stdout'][:1500]}" + (f"\nerrores:\n{r['stderr'][:800]}" if r["stderr"] else ""))
        raise ActionError(f"ideas no ejecuta '{action.type}'")
