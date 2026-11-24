"""Watchlist de Trading + estado por símbolo (2026-10-12, pedido de Damian).

El motor de trading (app/trading/, brigada T1–T8) corre bajo demanda sobre un símbolo y
devuelve veredicto (OPERAR/ESPERAR) + señal (long/short, R:R, confianza). Acá agregamos:
 - una watchlist de símbolos que el usuario quiere seguir (persistida), y
 - un cache del último estado de cada uno, refrescable desde la app.

SOLO análisis: nunca opera ni manda órdenes (la decisión y ejecución son del usuario).
Persistido en backend/data/trading_watch.json. Best-effort.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "trading_watch.json"
_LOCK = threading.Lock()


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"symbols": [], "status": {}}


def _save(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def list_symbols() -> list[dict]:
    return list(_load().get("symbols", []))


def add_symbol(instrument: str, source: str = "ccxt", timeframe: str = "1h") -> list[dict]:
    instrument = (instrument or "").strip()
    with _LOCK:
        data = _load()
        syms = data.setdefault("symbols", [])
        if instrument and not any(s.get("instrument") == instrument for s in syms):
            syms.append({"instrument": instrument, "source": source or "ccxt", "timeframe": timeframe or "1h"})
        _save(data)
        return syms


def remove_symbol(instrument: str) -> list[dict]:
    with _LOCK:
        data = _load()
        data["symbols"] = [s for s in data.get("symbols", []) if s.get("instrument") != instrument]
        data.get("status", {}).pop(instrument, None)
        _save(data)
        return data["symbols"]


def snapshot() -> dict:
    data = _load()
    status = data.get("status", {})
    out = []
    for s in data.get("symbols", []):
        inst = s.get("instrument")
        out.append({**s, **status.get(inst, {})})
    return {"symbols": out}


def _summarize(res: dict, demo: bool, win_rate=None) -> dict:
    verdict = res.get("verdict")
    sig = res.get("signal") or {}
    direction = sig.get("direction") if sig else None
    if verdict == "OPERAR" and sig:
        estado = "señal activa"
    elif sig:
        estado = "setup formándose"
    else:
        estado = "esperando"
    size = (sig.get("size") or {}) if sig else {}
    return {
        "verdict": verdict,
        "direction": direction,
        "rr": sig.get("rr") if sig else None,
        "confidence": sig.get("confidence") if sig else None,
        # Panel de riesgo (la señal ya trae niveles + sizing calculado por la estación T4).
        "entry": sig.get("entry") if sig else None,
        "sl": sig.get("sl") if sig else None,
        "tp": sig.get("tp") if sig else None,
        "zone": sig.get("zone") if sig else None,
        "units": size.get("units"),
        "risk_cash": size.get("risk_cash"),
        "win_rate": win_rate,  # track record (se llena con backtest(); None si no se corrió)
        "estado": estado,
        "demo": demo,
        "ts": time.time(),
    }


async def refresh(instrument: str | None = None) -> dict:
    """Corre el motor para cada símbolo (o uno) y actualiza su estado. Reusa el fetch del
    router (velas reales si ccxt/yfinance están; si no, cae a demo). Reporta a la brigada
    Trading del panel. Devuelve el snapshot nuevo."""
    from .routers.trading import _fetch
    from .harness.trading_brigade import run_trading_brigade

    data = _load()
    symbols = [s for s in data.get("symbols", []) if instrument is None or s.get("instrument") == instrument]
    status = data.setdefault("status", {})

    for s in symbols:
        inst = s.get("instrument")
        fetched = None
        try:
            fetched = _fetch(s.get("source", "ccxt"), inst, s.get("timeframe", "1h"), 300)
        except Exception:  # noqa: BLE001
            fetched = None
        payload: dict = {"instrument": inst, "timeframe": s.get("timeframe", "1h")}
        if fetched:
            payload["candles"] = fetched
        else:
            payload["demo"] = True
            payload["seed"] = 7
        try:
            res = await run_trading_brigade(payload)
        except Exception:  # noqa: BLE001 -- un símbolo roto no frena al resto
            continue
        prev = status.get(inst, {})
        summary = _summarize(res, demo=not bool(fetched), win_rate=prev.get("win_rate"))
        status[inst] = summary
        try:
            from . import mission_control

            tag = summary["estado"] + (f" {summary['direction']}" if summary.get("direction") else "")
            await mission_control.report("trd", f"📈 {inst}: {tag}", inc=1)
        except Exception:  # noqa: BLE001
            pass
        # Alerta: transición A "señal activa" → avisa al cel (panel + espejo de chat). Solo análisis.
        if summary["estado"] == "señal activa" and prev.get("estado") != "señal activa":
            await _alert(inst, summary)

    with _LOCK:
        cur = _load()
        cur["status"] = status
        cur["symbols"] = data.get("symbols", [])
        _save(cur)
    return snapshot()


async def _alert(instrument: str, summary: dict) -> None:
    """Avisa al usuario que apareció una señal. Reusa lo que ya tenemos: el panel (brigada
    Trading) + el espejo de chat (llega al celular como mensaje, sin FCM). SOLO análisis: el
    aviso dice qué ve el motor, nunca opera. Best-effort."""
    direction = (summary.get("direction") or "").upper()
    rr = summary.get("rr")
    texto = (
        f"🚨 Señal {direction} en {instrument}"
        + (f" · R:R {rr}" if rr else "")
        + (f" · entrada {summary.get('entry')} / SL {summary.get('sl')} / TP {summary.get('tp')}"
           if summary.get("entry") is not None else "")
        + ". Solo análisis — la decisión es tuya."
    )
    try:
        from . import mission_control

        await mission_control.report("trd", f"🚨 SEÑAL {instrument} {direction}", inc=0)
    except Exception:  # noqa: BLE001
        pass
    try:
        import time as _t

        from . import chat_link

        payload = {
            "type": "turn",
            "conversation_id": "default",
            "origin": None,
            "messages": [{"role": "assistant", "content": texto, "ts": _t.time()}],
        }
        await chat_link.broadcast("default", payload)
    except Exception:  # noqa: BLE001
        pass


async def backtest(instrument: str) -> dict:
    """Track record del símbolo: corre el backtest sobre histórico y devuelve win rate +
    expectativa. Guarda el win_rate en el estado del símbolo para mostrarlo sin re-correr."""
    from .routers.trading import _fetch
    from .trading import backtest as bt, engine as E, signals as S

    data = _load()
    sym = next((s for s in data.get("symbols", []) if s.get("instrument") == instrument), None)
    if not sym:
        return {"error": "ese símbolo no está en la watchlist"}
    fetched = None
    try:
        fetched = _fetch(sym.get("source", "ccxt"), instrument, sym.get("timeframe", "1h"), 500)
    except Exception:  # noqa: BLE001
        fetched = None
    if fetched:
        candles = []
        for i, c in enumerate(fetched):
            t, o, h, l, cl, *rest = c
            candles.append(E.Candle(t, float(o), float(h), float(l), float(cl), float(rest[0]) if rest else 0.0))
    else:
        candles = E.synth(n=500, seed=7)
    st = bt.simulate(candles, S.RiskConfig())
    st.pop("_trades", None)
    st["demo"] = not bool(fetched)
    # Persistir el win_rate en el estado del símbolo.
    with _LOCK:
        cur = _load()
        cur.setdefault("status", {}).setdefault(instrument, {})["win_rate"] = st.get("win_rate")
        _save(cur)
    return {"instrument": instrument, "stats": st}


async def watch_loop() -> None:
    """Loop de fondo (default OFF, flag TRADING_WATCH_LOOP_ENABLED): refresca la watchlist cada
    TRADING_WATCH_INTERVAL_MINUTES y dispara alertas al pasar a 'señal activa'. Arrancado desde
    el startup de FastAPI como los demás jobs. Un fallo se loguea y no corta el loop."""
    import asyncio
    import logging

    from .config import settings

    log = logging.getLogger("jarvis.trading_watch")
    if not getattr(settings, "trading_watch_loop_enabled", False):
        log.info("trading watch loop deshabilitado (TRADING_WATCH_LOOP_ENABLED=false)")
        return
    await asyncio.sleep(90.0)  # deja arrancar el backend
    while True:
        try:
            await refresh()
        except Exception:  # noqa: BLE001
            log.exception("el refresh de trading falló")
        await asyncio.sleep(max(300.0, getattr(settings, "trading_watch_interval_minutes", 30) * 60))
