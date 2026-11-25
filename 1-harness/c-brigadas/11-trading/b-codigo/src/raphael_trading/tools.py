"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Todas SOLO LEEN o analizan. Ejecutar una orden y cerrar una posición NO son tools ni se pueden pedir desde acá: son las
acciones `ejecutar_orden` y `cerrar_posicion` (aprobación, `spend`, `irreversible`, también en demo), que sigue pidiendo el
cocinero `engine-watch` con el comando `proponer` o `cerrar` a pedido de Damián. La lista de instrumentos vigilados que se
agrega a mano vive en el espacio propio de ese cocinero y las tools no la ven: acá solo se ven los de la config.
"""

from __future__ import annotations

from datetime import date

from raphael_core import ActionError

from . import backtest as B
from . import service
from .broker import BrokerError, make_broker
from .config import trading_config
from .cooks.backtest import MAX_CANDLES, WARNING_ALL, WARNING_SIM
from .cooks.signals import pick
from .data import load_candles


def make_tools(ctx) -> dict:
    def _cfg():
        return trading_config(ctx.config)

    def _seguro(fn):
        try:
            return fn()
        except (ActionError, BrokerError) as exc:
            return {"ok": False, "motivo": str(exc)}

    def trading_analizar(instrument: str = "") -> dict:
        """Analiza un instrumento de la config (por defecto el primero) con las últimas velas y devuelve la señal, si la hay.
        No ejecuta nada."""
        def hacer():
            cfg = _cfg()
            return service.analyze(cfg, pick(cfg, instrument or None))
        return _seguro(hacer)

    def trading_backtest(instrument: str = "", candles: int = 500) -> dict:
        """Prueba la estrategia sobre histórico: win rate, expectativa en R, drawdown y desglose por setup."""
        def hacer():
            cfg = _cfg()
            inst = pick(cfg, instrument or None)
            cfg.data.candles = max(100, min(int(candles), MAX_CANDLES))
            velas, source = load_candles(cfg, inst)
            st = B.simulate(velas, service.risk_config(cfg, inst, velas[-1].c))
            st.pop("_trades", None)
            avisos = [WARNING_ALL] + ([WARNING_SIM] if source.simulated else []) + ([source.note] if source.note else [])
            return {"instrument": inst.name, "source": {"kind": source.kind, "simulated": source.simulated},
                    "candles": len(velas), "stats": st, "warnings": avisos}
        return _seguro(hacer)

    def trading_senales() -> list[dict]:
        """Las señales guardadas por la vigilancia, las más nuevas primero (hasta 20)."""
        return sorted(ctx.shared.list("signals"), key=lambda s: s.get("created", ""), reverse=True)[:20]

    def trading_ordenes() -> list[dict]:
        """Las órdenes que ya se ejecutaron (con la aprobación de Damián), las más nuevas primero (hasta 20)."""
        return sorted(ctx.shared.list("orders"), key=lambda o: o.get("at", ""), reverse=True)[:20]

    def trading_posiciones() -> list | dict:
        """Las posiciones abiertas en el broker (solo lee). Si el broker real no está disponible, usa el simulado y lo dice."""
        def hacer():
            cfg = _cfg()
            broker, nota = make_broker(cfg.broker.adapter, cfg.broker.environment)
            return {"broker": broker.name, "simulado": broker.simulated, "aviso": nota, "posiciones": broker.positions()}
        return _seguro(hacer)

    def trading_estado() -> dict:
        """Qué adaptadores de datos y de broker están configurados, si hay pausa y cuántas órdenes se ejecutaron hoy."""
        cfg = _cfg()
        hoy = date.today().isoformat()
        return {"pausado": bool((ctx.shared.get("state", "pause") or {}).get("paused")),
                "ordenes_hoy": sum(1 for o in ctx.shared.list("orders") if str(o.get("at", "")).startswith(hoy)),
                "max_ordenes_dia": cfg.risk.max_orders_per_day, "datos": cfg.data.adapter, "broker": cfg.broker.adapter,
                "entorno_broker": cfg.broker.environment, "vigilancia_activa": cfg.watch.enabled,
                "instrumentos_de_la_config": [i.name for i in cfg.watch.instruments]}

    return {f.__name__: f for f in (trading_analizar, trading_backtest, trading_senales, trading_ordenes, trading_posiciones,
                                    trading_estado)}
