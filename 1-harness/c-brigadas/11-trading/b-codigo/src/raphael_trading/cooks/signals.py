"""Señales: analiza un instrumento con el método (sweep, POI, riesgo) y devuelve la señal. Nunca ejecuta."""

from __future__ import annotations

from raphael_core import ActionError, Cook

from .. import service
from ..config import Instrument, trading_config


def pick(cfg, name: str | None) -> Instrument:
    insts = cfg.watch.instruments
    if not name:
        return insts[0]
    found = next((i for i in insts if i.name.upper() == name.upper()), None)
    if found is None:
        raise ActionError(f"'{name}' no está en la lista de instrumentos de la config (watch.instruments)")
    return found


class Signals(Cook):
    name = "signals"
    version = "2.0.0"
    description = "Analiza un instrumento y propone una señal con entrada, stop, objetivo y tamaño. No ejecuta nada."
    commands = {"analizar": "Analiza un instrumento ahora {'instrument': 'USD/JPY'}",
                "senales": "Señales guardadas por la vigilancia (las últimas 20)"}

    def interest(self, msg, ctx) -> float:
        t = (msg.text or "").lower()
        return 0.6 if any(w in t for w in ("señal", "senal", "usd/jpy", "trading", "operar")) else 0.0

    def command(self, name, data, ctx):
        if name == "analizar":
            cfg = trading_config(ctx.config)
            return service.analyze(cfg, pick(cfg, data.get("instrument")))
        if name == "senales":
            return sorted(ctx.shared.list("signals"), key=lambda s: s.get("created", ""), reverse=True)[:20]
        return super().command(name, data, ctx)
