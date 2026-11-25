"""Asociativo, analogías y curiosidad: busca por asociación (activación propagada por los wikilinks), por analogía
estructural, por composición de conceptos, y detecta los huecos del vault. Todo cómputo de grafo, sin modelo.

Lo único que escribe es el aprendizaje del uso (`dar_feedback`): qué notas se usaron de verdad y cómo salió.
"""

from __future__ import annotations

from raphael_core import ActionError, Cook

from .. import actions
from ..brain import Brain


class Associative(Cook):
    name = "asociativo"
    version = "2.0.0"
    description = "Recuperación por asociación, analogía y composición; curiosidad sobre el vault."
    commands = {"asociar": "Recuperación asociativa {'query', 'limit', 'anticipar', 'diversificar'}",
                "analogias": "Análogos estructurales de una nota {'nota'}",
                "componer": "Notas en la intersección de conceptos {'conceptos': [..]}",
                "curiosidad": "Huecos del vault: notas citadas que no existen y notas huérfanas",
                "feedback": "Marcar notas usadas y cómo salió {'ids', 'signals', 'situacion', 'paso'}"}

    def command(self, name: str, data: dict, ctx):
        brain = Brain.from_ctx(ctx)
        if name == "asociar":
            q = str(data.get("query") or "").strip()
            if not q:
                raise ActionError("falta 'query'")
            # `reforzar` no se acepta acá: aprender del uso es una acción (feedback), no una lectura
            return brain.spread(q, limit=int(data.get("limit", 10)), anticipar=bool(data.get("anticipar")),
                                diversificar=bool(data.get("diversificar")), extractos=bool(data.get("extractos")))
        if name == "analogias":
            return brain.analogies(str(data.get("nota") or ""), limit=int(data.get("limit", 8)))
        if name == "componer":
            return brain.compose(list(data.get("conceptos") or []), limit=int(data.get("limit", 10)))
        if name == "curiosidad":
            return brain.curiosity(limit=int(data.get("limit", 10)))
        if name == "feedback":
            return actions.request(ctx, "dar_feedback", {k: data.get(k) for k in ("ids", "signals", "situacion", "paso")},
                                   "Aprender del uso de notas")
        return super().command(name, data, ctx)

    def execute(self, action, ctx):
        return actions.execute(ctx, action)
