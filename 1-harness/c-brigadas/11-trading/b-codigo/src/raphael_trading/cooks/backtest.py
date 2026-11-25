"""Backtest: prueba la estrategia sobre histórico y saca estadística. Solo lee; no ejecuta ni toca el broker."""

from __future__ import annotations

from raphael_core import Cook

from .. import backtest as B
from .. import service
from ..config import trading_config
from ..data import load_candles
from .signals import pick

MAX_CANDLES = 1500
WARNING_SIM = "Datos SIMULADOS: sirve para ver que la mecánica corre, no dice nada sobre si la estrategia tiene ventaja."
WARNING_ALL = "Un backtest positivo no garantiza resultados en vivo."


class Backtest(Cook):
    name = "backtest"
    version = "2.0.0"
    description = "Prueba la estrategia sobre datos históricos: win rate, expectativa en R, drawdown y desglose por setup."
    commands = {"backtest": "Backtest de un instrumento {'instrument': 'USD/JPY', 'candles': 500}"}

    def command(self, name, data, ctx):
        if name != "backtest":
            return super().command(name, data, ctx)
        cfg = trading_config(ctx.config)
        inst = pick(cfg, data.get("instrument"))
        cfg.data.candles = max(100, min(int(data.get("candles", 500)), MAX_CANDLES))
        candles, source = load_candles(cfg, inst)
        st = B.simulate(candles, service.risk_config(cfg, inst, candles[-1].c))
        st.pop("_trades", None)
        warnings = [WARNING_ALL] + ([WARNING_SIM] if source.simulated else []) + ([source.note] if source.note else [])
        return {"instrument": inst.name, "source": {"kind": source.kind, "simulated": source.simulated},
                "candles": len(candles), "stats": st, "warnings": warnings}
