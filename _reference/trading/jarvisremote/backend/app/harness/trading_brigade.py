"""La Brigada de Trading, ensamblada como un DAG sobre el mismo harness que la
Brigada de Auditoría (`audit_brigade.py`). Cada estación es una clase con
`name`/`tier`/`tools` y un `run(task, bb)` que lee la pizarra, hace SU parte del
método Smart Money (Fede Esses, modelo IFVG) y escribe su resultado + su
**requisito** (¿se cumple la condición de esta etapa?). El orquestador corre las
estaciones en orden y T7 arma la señal final.

Flujo (DAG):

    T1 Datos ─► T2 Estructura ─► T3 Liquidez ─► T4 Zona/Bias ─► T5 POI/IFVG ─► T6 Riesgo/Gate ─► T7 Señal ─► T8 Lectura

ADITIVO y AISLADO: no se importa al arrancar el backend, no ejecuta órdenes ni
mueve dinero (solo analiza y propone; el click final es del humano). No es
asesoramiento financiero. T1-T7 son tier 0 (deterministas): el trading es
matemática sobre velas. T8 (Lectura Esses, 2026-09-29) es la ÚNICA con LLM (tier 2):
lee los datos ya detectados y da una lectura discrecional con las reglas de Fede
Esses -- juicio sobre la matemática, no detección. Best-effort (on_error=skip): si
el modelo se cae, la brigada devuelve igual el veredicto mecánico de T7.

Testeable: cada estación es pura; el DAG se prueba con velas sintéticas
(`engine.synth`) sin datos reales.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..trading import engine as E
from ..trading import signals as S
from .blackboard import ExecutionStore, MemoryBlackboard
from .contracts import AgentResult, Node, Task
from .orchestrator import Budget, Orchestrator, RunReport

logger = logging.getLogger("jarvis.harness.trading")

# Nombres de estación (estables: se leen de la pizarra por estos nombres).
T1 = "T1_datos"
T2 = "T2_estructura"
T3 = "T3_liquidez"
T4 = "T4_zona"
T5 = "T5_poi"
T6 = "T6_riesgo"
T7 = "T7_senal"
T8 = "T8_lectura"

# Reglas del método Fede Esses (modelo IFVG) para la lectura discrecional del LLM.
# El LLM razona SOLO sobre los datos deterministas ya detectados por T1-T7 (nunca
# inventa patrones/precios): es una capa de JUICIO sobre la matemática, no detección.
_ESSES_SYSTEM = (
    "Sos un analista que lee price action con el método Smart Money de Fede Esses, modelo IFVG "
    "(Inverse Fair Value Gap). Te paso datos YA detectados de forma DETERMINISTA (estructura, liquidez, "
    "zona, POI, riesgo) -- NO inventes patrones ni precios; razoná SOLO sobre esos datos. El modelo IFVG "
    "tiene 3 pasos: (1) barrido de liquidez (sweep), (2) desplazamiento que INVIERTE un FVG (crea el "
    "IFVG), (3) entrada en ese IFVG. Confluencias que suman calidad: daily bias a favor, precio en "
    "discount (compras) o premium (ventas), order block / inducement, estructura (BOS/CHoCH) a favor, "
    "R:R >= 2. Disciplina: si falta una confluencia CLAVE, la respuesta correcta es ESPERAR, no forzar. "
    "Tu lectura, breve: (a) ¿setup A+, B, o no-setup según el método?; (b) qué confluencias están y "
    "cuáles faltan; (c) gestión de riesgo (dónde el SL, adónde el TP, R:R); (d) recomendación clara. "
    "Cerrá SIEMPRE recordando que la decisión y la ejecución son del humano; esto NO es asesoramiento "
    "financiero."
)


def _req(nombre: str, cumple: bool, detalle: str) -> dict:
    return {"nombre": nombre, "cumple": bool(cumple), "detalle": detalle}


async def _esses_reading(facts: str, station_name: str, tier: int) -> str | None:
    """Lectura discrecional del LLM sobre los datos deterministas, con las reglas de
    Esses. Usa el fallback en cascada por tier (model_registry.candidates_for): si el
    modelo primario falla, prueba el siguiente. Best-effort: None si todos fallan."""
    from .model_registry import registry

    msgs = [
        {"role": "system", "content": _ESSES_SYSTEM},
        {"role": "user", "content": "DATOS DETECTADOS (deterministas):\n" + facts + "\n\nDame tu lectura Esses."},
    ]
    for client, model in registry.candidates_for(station_name, tier):
        try:
            resp = await client.chat.completions.create(model=model, messages=msgs)
            return (resp.choices[0].message.content or "").strip()
        except Exception:  # noqa: BLE001 -- fallback: pruebo el siguiente del tier
            logger.warning("T8 lectura Esses falló con %s; pruebo el siguiente del tier.", model)
    return None


def _candles_from_task(task: Task) -> list[E.Candle]:
    """Acepta payload['candles'] como lista de dicts o listas [t,o,h,l,c,v].
    Para demo, payload['demo']=True usa velas sintéticas."""
    p = task.payload
    if p.get("demo"):
        return E.synth(n=int(p.get("n", 400)), seed=int(p.get("seed", 7)))
    raw = p.get("candles") or []
    out: list[E.Candle] = []
    for i, c in enumerate(raw):
        if isinstance(c, dict):
            out.append(E.Candle(c.get("t", i), float(c["o"]), float(c["h"]),
                                float(c["l"]), float(c["c"]), float(c.get("v", 0))))
        else:
            t, o, h, l, cl, *rest = c
            out.append(E.Candle(t, float(o), float(h), float(l), float(cl),
                                float(rest[0]) if rest else 0.0))
    return out


# --- T1 · Datos (Reconocimiento) ----------------------------------------------
class DataStation:
    """Carga las velas OHLC del instrumento (de payload o adaptador). Requisito:
    hay suficientes velas para analizar."""

    name = T1
    tier = 0
    tools = ["trading_load_candles"]

    async def run(self, task: Task, bb) -> AgentResult:
        candles = _candles_from_task(task)
        cumple = len(candles) >= 30
        req = _req("Datos suficientes", cumple, f"{len(candles)} velas (mínimo 30)")
        if not cumple:
            return AgentResult(ok=False, error="pocas velas para analizar",
                               output={"requisito": req, "chat": [
                                   {"rol": "sistema", "texto": f"Solo {len(candles)} velas; necesito ≥30."}]})
        return AgentResult(ok=True, output={
            "candles": candles,
            "instrument": task.payload.get("instrument", "?"),
            "requisito": req,
            "chat": [{"rol": "sistema", "texto": f"Cargué {len(candles)} velas de {task.payload.get('instrument','?')}."}],
        })


# --- T2 · Estructura ----------------------------------------------------------
class StructureStation:
    """Tendencia + swings + quiebres (BOS/CHoCH). Requisito: hay estructura legible
    (tendencia definida o un evento estructural reciente)."""

    name = T2
    tier = 0
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        candles = (bb.read(T1) or {}).get("candles") or []
        swings = E.find_swings(candles)
        events = E.structure_events(candles, swings)
        trend = E.trend_from_swings(swings)
        last_ev = events[-1] if events else None
        cumple = trend != "range" or bool(events)
        detalle = f"tendencia={trend}, eventos={len(events)}"
        return AgentResult(ok=True, output={
            "trend": trend,
            "n_events": len(events),
            "last_event": {"kind": last_ev.kind, "dir": last_ev.direction, "i": last_ev.i} if last_ev else None,
            "requisito": _req("Estructura legible", cumple, detalle),
            "chat": [{"rol": "sistema", "texto": f"Estructura: tendencia {trend}, {len(events)} quiebres (BOS/CHoCH)."}],
        })


# --- T3 · Liquidez ------------------------------------------------------------
class LiquidityStation:
    """Niveles de liquidez + tomas de liquidez (sweeps) + inducement. Requisito
    (gatillo #1 del modelo): hubo un sweep reciente. Define la dirección tentativa."""

    name = T3
    tier = 0
    tools = []

    def __init__(self, lookback: int = 8) -> None:
        self._lb = lookback

    async def run(self, task: Task, bb) -> AgentResult:
        candles = (bb.read(T1) or {}).get("candles") or []
        i = len(candles) - 1
        a = E.analyze(candles)
        recent = [s for s in a["sweeps"] if i - s.i <= self._lb]
        sweep = recent[-1] if recent else None
        direction = None
        if sweep:
            direction = "long" if sweep.side == "sell" else "short"
        ind = a.get("inducement")
        cumple = sweep is not None
        detalle = (f"sweep {sweep.side} @ {sweep.level:.4f} → {direction}" if sweep
                   else "sin toma de liquidez reciente")
        return AgentResult(ok=True, output={
            "sweep": {"side": sweep.side, "level": sweep.level, "i": sweep.i} if sweep else None,
            "direction": direction,
            "inducement": ind,
            "requisito": _req("Toma de liquidez (sweep)", cumple, detalle),
            "chat": [{"rol": "sistema", "texto":
                      (f"Liquidez: se barrió {sweep.side}-side @ {sweep.level:.4f} → sesgo {direction}."
                       + (" Inducement previo barrido." if ind and ind.get('taken') else ""))
                      if sweep else "Liquidez: sin sweep reciente — no hay gatillo."}],
        })


# --- T4 · Zona / Bias ---------------------------------------------------------
class ZoneStation:
    """Premium/Discount + daily bias. Requisito: el precio está en la zona correcta
    para la dirección (discount para compras, premium para ventas)."""

    name = T4
    tier = 0
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        candles = (bb.read(T1) or {}).get("candles") or []
        direction = (bb.read(T3) or {}).get("direction")
        a = E.analyze(candles)
        zone = a["price_zone"]
        trend = a["trend"]
        ok_zone = (direction == "long" and zone == "discount") or \
                  (direction == "short" and zone == "premium") or \
                  zone == "equilibrium"
        detalle = f"zona={zone}, bias(trend)={trend}, dir={direction}"
        return AgentResult(ok=True, output={
            "zone": zone, "bias": trend,
            "requisito": _req("Zona correcta (premium/discount)", bool(ok_zone), detalle),
            "chat": [{"rol": "sistema", "texto": f"Zona: precio en {zone} (bias {trend}). "
                      f"{'Coincide' if ok_zone else 'NO coincide'} con dir {direction}."}],
        })


# --- T5 · POI / IFVG ----------------------------------------------------------
class POIStation:
    """Zonas de interés: IFVG (el modelo de Fede) primero, luego FVG y order block.
    Requisito: hay un POI en la dirección, cerca del precio."""

    name = T5
    tier = 0
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        candles = (bb.read(T1) or {}).get("candles") or []
        direction = (bb.read(T3) or {}).get("direction")
        a = E.analyze(candles)
        last = candles[-1].c
        want = "bull" if direction == "long" else "bear"
        poi_kind, zone = None, None
        for iv in reversed([x for x in a.get("ifvgs", []) if x.direction == want]):
            if iv.bottom <= last * 1.02 and iv.top >= last * 0.98:
                poi_kind, zone = "IFVG", (iv.bottom, iv.top); break
        if poi_kind is None:
            for g in reversed([g for g in a["fvgs"] if not g.filled and g.direction == want]):
                if g.bottom <= last * 1.02 and g.top >= last * 0.98:
                    poi_kind, zone = "FVG", (g.bottom, g.top); break
        if poi_kind is None:
            for o in reversed([o for o in a["order_blocks"] if o.direction == want]):
                if o.bottom <= last * 1.02 and o.top >= last * 0.98:
                    poi_kind, zone = "OB", (o.bottom, o.top); break
        cumple = poi_kind is not None
        detalle = (f"{poi_kind} [{zone[0]:.4f}, {zone[1]:.4f}]" if cumple else "sin POI cerca")
        return AgentResult(ok=True, output={
            "poi_kind": poi_kind, "poi_zone": zone,
            "n_ifvg": len(a.get("ifvgs", [])),
            "requisito": _req("POI (IFVG/FVG/OB) en zona", cumple, detalle),
            "chat": [{"rol": "sistema", "texto": f"POI: {detalle}."}],
        })


# --- T6 · Riesgo / Gate -------------------------------------------------------
class RiskStation:
    """Arma la señal con riesgo (sizing, SL/TP, R:R) y aplica los gates 'no operar'
    (noticias, R:R mínimo, confianza). Requisito: la señal pasa todos los gates.
    Reusa `signals.generate_signal` (la lógica ya probada)."""

    name = T6
    tier = 0
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        candles = (bb.read(T1) or {}).get("candles") or []
        p = task.payload
        cfg = S.RiskConfig(
            account=float(p.get("account", 10000)),
            risk_pct=float(p.get("risk_pct", 1.0)),
            min_rr=float(p.get("min_rr", 2.0)),
            value_per_point=float(p.get("value_per_point", 1.0)),
            min_conf=float(p.get("min_conf", 0.6)),
        )
        sig = S.generate_signal(candles, cfg, news_windows=p.get("news_windows"))
        if sig is None:
            return AgentResult(ok=True, output={
                "signal": None,
                "requisito": _req("Señal válida (gates)", False, "sin setup (falta sweep/POI)"),
                "chat": [{"rol": "raphael", "texto": "Riesgo/Gate: no hay setup A+ ahora. Esperar."}],
            })
        detalle = (f"{sig.direction} R:R={sig.rr} conf={sig.confidence}"
                   + ("" if sig.valid else f" — RECHAZADA: {sig.reject_reason}"))
        return AgentResult(ok=True, output={
            "signal": {
                "direction": sig.direction, "entry": sig.entry, "sl": sig.sl, "tp": sig.tp,
                "rr": sig.rr, "confidence": sig.confidence, "zone": sig.zone,
                "tags": sig.tags, "size": sig.size, "valid": sig.valid,
                "reject_reason": sig.reject_reason,
            },
            "requisito": _req("Señal válida (gates)", sig.valid, detalle),
            "chat": [{"rol": "raphael", "texto": f"Riesgo/Gate: {detalle}. Tamaño {sig.size.get('units')} u (riesgo ${sig.size.get('risk_cash')})."}],
        })


# --- T7 · Señal / Pase --------------------------------------------------------
class SignalStation:
    """Ensambla el veredicto final: ¿OPERAR o ESPERAR? Junta los requisitos de todas
    las estaciones y la señal. NO ejecuta: propone para que el humano decida."""

    name = T7
    tier = 0
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        reqs = []
        for n in (T1, T2, T3, T4, T5, T6):
            r = (bb.read(n) or {}).get("requisito")
            if r:
                reqs.append(r)
        sig = (bb.read(T6) or {}).get("signal")
        all_ok = all(r["cumple"] for r in reqs)
        verdict = "OPERAR" if (all_ok and sig and sig.get("valid")) else "ESPERAR"
        cumplidos = sum(1 for r in reqs if r["cumple"])
        chat = [{"rol": "raphael", "texto":
                 f"VEREDICTO: {verdict}. Requisitos {cumplidos}/{len(reqs)} cumplidos."
                 + (f" Señal {sig['direction'].upper()} entry={sig['entry']} SL={sig['sl']} "
                    f"TP={sig['tp']} R:R={sig['rr']} (conf {sig['confidence']}). "
                    "Decisión y ejecución: tuyas." if (verdict == 'OPERAR' and sig) else "")}]
        return AgentResult(ok=True, output={
            "verdict": verdict,
            "requisitos": reqs,
            "signal": sig,
            "chat": chat,
        })


# --- T8 · Lectura Esses (JUICIO del LLM, tier 2) ------------------------------
class LecturaStation:
    """Capa de razonamiento (LLM): lee los datos DETERMINISTAS de T2-T7 y da una
    lectura discrecional con el método de Fede Esses (IFVG) — juicio sobre la
    matemática, no detección. tier 2 (usa modelo, ruteado por el sistema de tiers).
    Best-effort y `on_error=skip`: si el LLM falla, la brigada devuelve igual el
    veredicto mecánico de T7 (nunca bloquea la señal)."""

    name = T8
    tier = 3
    tools = []

    async def run(self, task: Task, bb) -> AgentResult:
        t2 = bb.read(T2) or {}; t3 = bb.read(T3) or {}; t4 = bb.read(T4) or {}
        t5 = bb.read(T5) or {}; t6 = bb.read(T6) or {}; t7 = bb.read(T7) or {}
        sig = t6.get("signal")
        # resumen compacto de lo detectado (solo datos, sin ruido)
        facts = (
            f"Instrumento: {(bb.read(T1) or {}).get('instrument','?')}\n"
            f"Estructura: tendencia={t2.get('trend')}, quiebres={t2.get('n_events')}, ultimo={t2.get('last_event')}\n"
            f"Liquidez: sweep={t3.get('sweep')}, direccion={t3.get('direction')}, inducement={t3.get('inducement')}\n"
            f"Zona/Bias: zona={t4.get('zone')}, bias={t4.get('bias')}\n"
            f"POI: {t5.get('poi_kind')} zona={t5.get('poi_zone')} (IFVGs detectados={t5.get('n_ifvg')})\n"
            f"Riesgo/Señal: {sig}\n"
            f"Veredicto mecanico: {t7.get('verdict')} | requisitos: "
            + ", ".join(f"{r['nombre']}={'OK' if r['cumple'] else 'NO'}" for r in (t7.get('requisitos') or []))
        )
        lectura = await _esses_reading(facts, self.name, self.tier)
        if lectura is None:
            return AgentResult(ok=True, output={
                "lectura": None,
                "chat": [{"rol": "raphael", "texto": "Lectura Esses no disponible (modelo caído); queda el veredicto mecánico."}],
            })
        return AgentResult(ok=True, output={
            "lectura": lectura,
            "chat": [{"rol": "usuario", "texto": "Leé el setup con el método de Fede Esses."},
                     {"rol": "raphael", "texto": lectura}],
        })


def build_trading_dag(stations: dict[str, Any] | None = None) -> list[Node]:
    s = stations or {}
    t1 = s.get(T1) or DataStation()
    t2 = s.get(T2) or StructureStation()
    t3 = s.get(T3) or LiquidityStation()
    t4 = s.get(T4) or ZoneStation()
    t5 = s.get(T5) or POIStation()
    t6 = s.get(T6) or RiskStation()
    t7 = s.get(T7) or SignalStation()
    t8 = s.get(T8) or LecturaStation()
    return [
        Node(t1, on_error="abort"),
        Node(t2, depends_on=[T1], on_error="abort"),
        Node(t3, depends_on=[T2], on_error="abort"),
        Node(t4, depends_on=[T3], on_error="skip"),   # zona es confluencia
        Node(t5, depends_on=[T3], on_error="abort"),
        Node(t6, depends_on=[T5, T4], on_error="abort"),
        Node(t7, depends_on=[T6, T5, T4, T3, T2, T1], on_error="abort"),
        Node(t8, depends_on=[T7], on_error="skip"),   # juicio LLM: nunca bloquea la señal
    ]


async def run_trading_brigade(
    payload: dict[str, Any],
    stations: dict[str, Any] | None = None,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Corre la brigada de trading sobre el payload (velas + config de riesgo) y
    devuelve el veredicto de T7 + el estado por estación (para la pestaña)."""
    nodes = build_trading_dag(stations)
    task = Task(id=f"trading:{payload.get('instrument','?')}", payload=payload)
    bb = MemoryBlackboard()
    store = ExecutionStore()
    report: RunReport = await Orchestrator("trading").run(nodes, task, bb=bb, store=store, budget=budget)

    t7_rec = store.get(T7)
    out = t7_rec.output if (t7_rec and t7_rec.ok) else {}

    t8_rec = store.get(T8)
    lectura = t8_rec.output.get("lectura") if (t8_rec and t8_rec.ok and isinstance(t8_rec.output, dict)) else None

    stations_out = []
    for name in (T1, T2, T3, T4, T5, T6, T7, T8):
        rec = store.get(name)
        if rec is not None:
            estado = "ok" if rec.ok else ("abortada" if name in report.aborted else "fallo")
            o = rec.output if isinstance(rec.output, dict) else {}
            stations_out.append({
                "estacion": name, "estado": estado, "segundos": round(rec.seconds, 3),
                "error": rec.error, "requisito": o.get("requisito"),
                "chat": o.get("chat", []),
            })
        elif name in report.skipped:
            stations_out.append({"estacion": name, "estado": "salteada", "segundos": 0.0,
                                 "error": None, "requisito": None, "chat": []})
        else:
            stations_out.append({"estacion": name, "estado": "no-corrio", "segundos": 0.0,
                                 "error": None, "requisito": None, "chat": []})

    return {
        "ok": report.ok,
        "run_summary": report.summary,
        "stations": stations_out,
        "verdict": out.get("verdict"),
        "signal": out.get("signal"),
        "requisitos": out.get("requisitos", []),
        "lectura_esses": lectura,  # juicio discrecional del LLM (T8), o None si no corrió
    }
