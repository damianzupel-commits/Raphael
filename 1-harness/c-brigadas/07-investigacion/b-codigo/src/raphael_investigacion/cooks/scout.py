"""Scout: búsqueda web con cada afirmación respaldada por su fuente."""

from __future__ import annotations

import re

from raphael_core import ActionError

from .. import scout
from ..search.chain import build_providers
from .base import InvCook


class Scout(InvCook):
    name = "scout"
    version = "2.0.0"
    description = "Busca en la web y reporta cada afirmación con su fuente, su fecha y si se verificó."
    interest_pattern = re.compile(r"en la web|en internet|\binternet\b|\bonline\b|\binvestig[aá]|\bresearch\b|noticias|estado del arte")
    commands = {"investigar": "investiga una pregunta {'pregunta','verificar'}", "notas": "notas guardadas {'q'}",
                "proveedores": "qué proveedores de búsqueda hay configurados (sin claves)"}

    def run_command(self, name, data, ctx):
        env = self.inv(ctx).env
        if name == "investigar":
            return scout.research(env, data.get("pregunta", ""), verify=data.get("verificar", True))
        if name == "notas":
            return scout.notes(env, data.get("q", ""))
        if name == "proveedores":
            return [{"proveedor": p.name, "configurado": p.is_configured(), "falta": "" if p.is_configured() else p.missing_config_hint()}
                    for p in build_providers(env)]
        return super().run_command(name, data, ctx)

    def run_action(self, action, ctx):
        env = self.inv(ctx).env
        if action.type == "buscar_web":
            r = scout.research(env, action.data.get("pregunta", ""), verify=action.data.get("verificar", True))
            if r["status"] != "ok":
                return r.get("aviso") or r.get("error", "no se pudo buscar")
            lines = [f"- {c['text']} [{', '.join(str(n) for n in c['sources'])}] ({c['estado']})" for c in r["claims"]]
            srcs = [f"[{s['n']}] {s['url']} · consultado {s['retrieved_at']} · publicado {s['fecha']}" for s in r["sources"]]
            return "\n".join([*lines, "", *srcs, *r["avisos"]])
        raise ActionError(f"scout no ejecuta '{action.type}'")
