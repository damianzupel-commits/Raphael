"""Motor y vigilancia: lista de instrumentos vigilados, avisos de señales y ejecución de órdenes YA aprobadas.

Regla que no se toca: este cocinero NUNCA llama al broker fuera de `execute` de `ejecutar_orden` / `cerrar_posicion`,
y las dos son nivel `aprobacion` en el manifiesto (con `spend` e `irreversible`: la confianza progresiva no las baja
sola a automático). En `execute` se revalida todo contra la config, aunque Damián haya editado la orden al aprobar.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from raphael_core import Action, ActionError, Cook, Health, Level

from .. import service
from ..broker import BrokerError, Order, make_broker
from ..config import Instrument, trading_config
from .signals import pick


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class EngineWatch(Cook):
    name = "engine-watch"
    version = "2.0.0"
    description = "Vigila los instrumentos, avisa cuando aparece una señal y ejecuta una orden solo si Damián la aprueba."
    commands = {
        "estado": "Estado: adaptadores en uso, pausa, órdenes de hoy",
        "vigilados": "Instrumentos vigilados",
        "ordenes": "Órdenes ejecutadas (las últimas 20)",
        "posiciones": "Posiciones abiertas en el broker",
        "agregar": "Vigilar un instrumento {'instrument': 'USD/JPY', 'timeframe': '1h'}",
        "quitar": "Dejar de vigilar un instrumento {'instrument': 'USD/JPY'}",
        "escanear": "Escanear ahora los instrumentos vigilados y guardar las señales nuevas",
        "proponer": "Pedir la aprobación para ejecutar una señal {'signal_id': '...'}",
        "cerrar": "Pedir la aprobación para cerrar una posición {'position_id': '...'}",
        "pausar": "Pausa total: no se ejecuta nada hasta reanudar",
        "reanudar": "Sale de la pausa",
    }

    def __init__(self) -> None:
        self._broker = None
        self._broker_key: tuple | None = None
        self._broker_note = ""

    # --- armado
    def _cfg(self, ctx):
        return trading_config(ctx.config)

    def _get_broker(self, cfg):
        key = (cfg.broker.adapter, cfg.broker.environment)
        if self._broker is None or self._broker_key != key:
            self._broker, self._broker_note = make_broker(cfg.broker.adapter, cfg.broker.environment)
            self._broker_key = key
        return self._broker

    def _instruments(self, ctx, cfg) -> list[Instrument]:
        mine = ctx.data.list("watchlist")
        return [Instrument(**{k: v for k, v in d.items() if k in Instrument.model_fields}) for d in mine] or cfg.watch.instruments

    def _paused(self, ctx) -> bool:
        return bool((ctx.shared.get("state", "pause") or {}).get("paused"))

    def _orders_today(self, ctx) -> int:
        today = ctx.today().isoformat()
        return sum(1 for o in ctx.shared.list("orders") if str(o.get("at", "")).startswith(today))

    # --- vigilancia
    def tick(self, now, ctx) -> None:
        cfg = self._cfg(ctx)
        if not cfg.watch.enabled or self._paused(ctx):
            return
        last = ctx.data.get("scan", "last")
        if last and now - datetime.fromisoformat(last["at"]) < timedelta(minutes=cfg.watch.interval_minutes):
            return
        self._scan(ctx, cfg)

    def _scan(self, ctx, cfg) -> list[dict]:
        ctx.data.put("scan", "last", {"at": _iso(ctx.now())})
        found = []
        for inst in self._instruments(ctx, cfg):
            res = service.analyze(cfg, inst)
            sig = res["signal"]
            if not sig or not sig["valid"] or ctx.shared.get("signals", sig["id"]):
                continue
            sig.update(status="abierta", created=_iso(ctx.now()), simulated=res["source"]["simulated"])
            ctx.shared.put("signals", sig["id"], sig)
            ctx.publish("trading.senal_nueva", {"signal_id": sig["id"], "instrument": inst.name, "direction": sig["direction"],
                                                "rr": sig["rr"], "simulated": sig["simulated"]})
            ctx.request(Action("avisar_senal", {"signal_id": sig["id"]}, self._notice_text(sig)))
            if cfg.watch.propose_automatically:
                ctx.request(self._order_action(sig, cfg))
            found.append(sig)
        return found

    @staticmethod
    def _notice_text(sig: dict) -> str:
        sim = " (datos simulados)" if sig.get("simulated") else ""
        return (f"Señal {sig['direction'].upper()} en {sig['instrument']}{sim}: entrada {sig['entry']}, stop {sig['sl']}, "
                f"objetivo {sig['tp']}, R:R {sig['rr']}. No se ejecuta nada sin tu aprobación.")

    def _order_action(self, sig: dict, cfg) -> Action:
        units = sig["size"].get("units", 0)
        return Action("ejecutar_orden", {"signal_id": sig["id"], "units": units},
                      f"Ejecutar {sig['direction'].upper()} {units} u. de {sig['instrument']} "
                      f"(entrada {sig['entry']}, stop {sig['sl']}, objetivo {sig['tp']}, "
                      f"broker {cfg.broker.adapter}/{cfg.broker.environment})")

    # --- comandos
    def command(self, name, data, ctx):
        cfg = self._cfg(ctx)
        if name == "estado":
            broker = self._get_broker(cfg)
            return {"pausado": self._paused(ctx), "ordenes_hoy": self._orders_today(ctx),
                    "max_ordenes_dia": cfg.risk.max_orders_per_day,
                    "datos": cfg.data.adapter, "broker": broker.name, "broker_simulado": broker.simulated,
                    "avisos": [n for n in (self._broker_note,) if n], "vigilancia_activa": cfg.watch.enabled}
        if name == "vigilados":
            return [i.model_dump() for i in self._instruments(ctx, cfg)]
        if name == "ordenes":
            return sorted(ctx.shared.list("orders"), key=lambda o: o.get("at", ""), reverse=True)[:20]
        if name == "posiciones":
            try:
                return self._get_broker(cfg).positions()
            except BrokerError as exc:
                raise ActionError(str(exc)) from None
        if name == "agregar":
            inst = Instrument(name=str(data.get("instrument", "")).upper(), timeframe=data.get("timeframe", "1h"))
            if not inst.name or "/" not in inst.name:
                raise ActionError("el instrumento va como 'USD/JPY'")
            ctx.data.put("watchlist", inst.name, inst.model_dump())
            return inst.model_dump()
        if name == "quitar":
            return {"quitado": ctx.data.delete("watchlist", str(data.get("instrument", "")).upper())}
        if name == "escanear":
            return {"nuevas": [s["id"] for s in self._scan(ctx, cfg)]}
        if name == "proponer":
            sig = ctx.shared.get("signals", data.get("signal_id", ""))
            if not sig or sig.get("status") != "abierta":
                raise ActionError("esa señal no existe o ya no está abierta")
            return ctx.request(self._order_action(sig, cfg))
        if name == "cerrar":
            pid = str(data.get("position_id", ""))
            if not pid:
                raise ActionError("falta position_id")
            return ctx.request(Action("cerrar_posicion", {"position_id": pid}, f"Cerrar la posición {pid}"))
        if name == "pausar":
            ctx.shared.put("state", "pause", {"paused": True, "at": _iso(ctx.now())})
            return {"pausado": True}
        if name == "reanudar":
            ctx.shared.put("state", "pause", {"paused": False, "at": _iso(ctx.now())})
            return {"pausado": False}
        return super().command(name, data, ctx)

    # --- ejecución (solo con acción ya aprobada por el Policy Engine)
    @staticmethod
    def _guard_never_automatic(action: Action, ctx) -> None:
        """Regla de Damián (21 nov): sin su aprobación no se ejecuta nada, ni en demo. El harness deja fijar el nivel
        por instalación (sin pisos), así que acá se corta si alguien dejó una acción con efecto en `automatico`."""
        if ctx.action_level(action.type) is Level.AUTO:
            raise ActionError("Trading no ejecuta en automático: dejá esa acción en 'aprobacion' (regla de Damián)")

    def execute(self, action: Action, ctx) -> str | None:
        cfg = self._cfg(ctx)
        if action.type in ("ejecutar_orden", "cerrar_posicion"):
            self._guard_never_automatic(action, ctx)
        if action.type == "avisar_senal":
            return action.summary
        if action.type == "ejecutar_orden":
            return self._execute_order(action, ctx, cfg)
        if action.type == "cerrar_posicion":
            if self._paused(ctx):
                raise ActionError("Trading está en pausa")
            try:
                res = self._get_broker(cfg).close(str(action.data.get("position_id", "")))
            except BrokerError as exc:
                raise ActionError(str(exc)) from None
            ctx.record("trading.cierre", position=res.get("id"))
            return f"Posición {res.get('id')} cerrada."
        raise ActionError(f"engine-watch no ejecuta '{action.type}'")

    def _execute_order(self, action: Action, ctx, cfg) -> str:
        if self._paused(ctx):
            raise ActionError("Trading está en pausa: no se ejecuta nada hasta reanudar")
        sig = ctx.shared.get("signals", str(action.data.get("signal_id", "")))
        if not sig or sig.get("status") != "abierta" or not sig.get("valid"):
            raise ActionError("la señal no existe, ya se usó o no es válida")
        age = ctx.now() - datetime.fromisoformat(sig["created"])
        if age > timedelta(minutes=cfg.risk.signal_ttl_minutes):
            ctx.shared.put("signals", sig["id"], {**sig, "status": "vencida"})
            raise ActionError(f"la señal venció (más de {cfg.risk.signal_ttl_minutes} min): pedí una nueva")
        if self._orders_today(ctx) >= cfg.risk.max_orders_per_day:
            raise ActionError(f"tope de {cfg.risk.max_orders_per_day} órdenes por día alcanzado")
        # tamaño: lo que pida la orden (Damián puede editarlo al aprobar), con techo duro por riesgo
        stop_dist = abs(sig["entry"] - sig["sl"])
        inst = pick(cfg, sig["instrument"])
        vpp = service.value_per_point(inst, sig["entry"])
        max_units = cfg.risk.account * cfg.risk.max_risk_pct / 100 / (stop_dist * vpp) if stop_dist > 0 else 0
        units = min(float(action.data.get("units") or sig["size"].get("units", 0)), max_units)
        if units <= 0:
            raise ActionError("tamaño inválido")
        try:
            fill = self._get_broker(cfg).place(Order(sig["instrument"], sig["direction"], units, sig["sl"], sig["tp"], sig["id"]),
                                               price=sig["entry"])
        except BrokerError as exc:
            ctx.publish("trading.orden_rechazada", {"signal_id": sig["id"], "motivo": str(exc)})
            raise ActionError(str(exc)) from None
        ctx.shared.put("orders", fill.id, {"id": fill.id, "signal_id": sig["id"], "instrument": fill.instrument,
                                           "direction": fill.direction, "units": fill.units, "price": fill.price,
                                           "broker": fill.broker, "simulated": fill.simulated, "at": _iso(ctx.now())})
        ctx.shared.put("signals", sig["id"], {**sig, "status": "ejecutada"})
        ctx.publish("trading.orden_ejecutada", {"order_id": fill.id, "instrument": fill.instrument, "simulated": fill.simulated})
        ctx.record("trading.orden", order=fill.id, broker=fill.broker, simulated=fill.simulated)
        tag = "SIMULADA" if fill.simulated else f"REAL ({getattr(self._broker, 'environment', '?')})"
        return (f"Orden {tag} {fill.id}: {fill.direction.upper()} {fill.units:g} u. de {fill.instrument}, "
                f"stop {sig['sl']}, objetivo {sig['tp']}.")

    def health(self, ctx) -> Health:
        return Health(True, "ok")
