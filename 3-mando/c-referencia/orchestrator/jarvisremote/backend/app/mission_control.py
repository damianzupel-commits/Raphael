"""Centro de Mando (2026-10-11, pedido de Damian): el panel único donde las brigadas
de Raphael se ven en vivo, con el orquestador maestro arriba. Este módulo es el ESTADO
en memoria + el broadcaster; el panel HTML lo sirve `main.py` (GET /centro-de-mando) y se
suscribe por WebSocket (/ws/mission-control). La actividad real llega por `report()` —
lo llaman el loop del agente (al ejecutar tools) y los jobs de fondo.

Estado en memoria + broadcast inyectable (testeable sin red real). No persiste: refleja
lo que está pasando AHORA; al reiniciar arranca "en espera".
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger("jarvis.mission_control")

# Las 9 brigadas definidas con Damian (orden y datos espejan el panel).
BRIGADES: list[dict] = [
    {"id": "seg", "nm": "Seguridad", "sub": "AUDITORÍA · PENTEST", "modes": ["⚔️ ATAQUE", "🛡️ DEFENSA"]},
    {"id": "mal", "nm": "Antimalware", "sub": "PROTECCIÓN ACTIVA"},
    {"id": "inv", "nm": "Investigación", "sub": "FORENSE"},
    {"id": "geo", "nm": "Geolocalización pública", "sub": "MAPA · OSINT"},
    {"id": "mem", "nm": "Memoria · Cerebro", "sub": "CONSOLIDACIÓN"},
    {"id": "ing", "nm": "Ingesta", "sub": "CONOCIMIENTO"},
    {"id": "trd", "nm": "Trading", "sub": "MERCADOS"},
    {"id": "ops", "nm": "Operaciones", "sub": "PC · CELULAR"},
    {"id": "rep", "nm": "Autorreparación", "sub": "AUTO-MEJORA"},
    {"id": "con", "nm": "Contenido", "sub": "IMAGEN · VIDEO", "future": True},
]
_IDS = {b["id"] for b in BRIGADES}

# Cuántas acciones recientes guarda cada brigada para el "monitor en vivo" del panel
# (2026-10-12, pedido de Damian para Operaciones: ver las tools que se están usando AHORA,
# no solo la última). Es general: todas las brigadas llevan su registro corto.
_RECENT_CAP = 8

_state: dict[str, dict] = {
    b["id"]: {
        "count": 0,
        "last": "en espera…",
        "mode": (b.get("modes") or [None, None])[1],
        "ts": 0.0,
        "recent": [],  # [{"m": <mensaje>, "ts": <epoch>}], más nuevo primero
    }
    for b in BRIGADES
}

# Mapa tool del agente -> brigada. Así, cuando el agente ejecuta una tool, la brigada
# correspondiente se "enciende" en el panel con actividad REAL (no simulada).
TOOL_BRIGADE: dict[str, str] = {
    # Seguridad: defensa = auditoría estática; ataque = pentest activo.
    "security_scan_project": "seg", "quality_scan_project": "seg", "codebase_index_project": "seg",
    "audit_report_brigade": "seg",
    "nmap_scan": "seg", "phone_nmap_scan": "seg", "sqlmap_scan": "seg", "zap_scan": "seg",
    # Memoria / cerebro.
    "obsidian_buscar_asociativo": "mem", "obsidian_analogia": "mem", "obsidian_componer": "mem",
    "memoria_consolidar": "mem", "obsidian_curiosidad": "mem", "obsidian_reindexar": "mem",
    "obsidian_search_notes": "mem", "obsidian_feedback": "mem",
    # Ingesta.
    "youtube_ingest_video": "ing", "youtube_ingest_playlist": "ing", "obsidian_ingerir_web": "ing",
    # Operaciones (PC / celular) = las "manos".
    "pc_run_command": "ops", "shell_exec": "ops", "desktop_launch_app": "ops",
    "desktop_click_element": "ops", "desktop_type_text": "ops", "desktop_screenshot": "ops",
    "desktop_focus_window": "ops", "phone_tap": "ops", "phone_swipe": "ops", "phone_type_text": "ops",
    "phone_run_command": "ops", "phone_take_photo": "ops", "phone_record_video": "ops",
    "phone_read_screen": "ops", "phone_global_action": "ops", "browser_open": "ops", "web_get": "ops",
    # Autorreparación.
    "selfrepair_propose_fix": "rep", "code_apply_fix": "rep",
    # Investigación forense.
    "investigation_analyze_link": "inv", "investigation_add_artifact": "inv",
    # Geolocalización pública / OSINT de infraestructura (cae como pin en el globo /globo).
    "ip_geolocate": "geo", "crypto_address_trace": "geo", "shodan_host_search": "geo",
    # Modo Ataque vs Defensa de Seguridad (para el badge del panel).
}
# Qué tools ponen la brigada Seguridad en modo ATAQUE (pentest activo); el resto, DEFENSA.
_ATTACK_TOOLS = {"nmap_scan", "phone_nmap_scan", "sqlmap_scan", "zap_scan"}

_subs: list[Any] = []


def register(ws: Any) -> None:
    _subs.append(ws)


def unregister(ws: Any) -> None:
    try:
        _subs.remove(ws)
    except ValueError:
        pass


def subscriber_count() -> int:
    return len(_subs)


def snapshot() -> dict:
    """Estado completo para la carga inicial del panel."""
    return {"brigades": BRIGADES, "state": _state, "master": {"model": "OPUS 5.5"}}


async def _broadcast(payload: dict, send: Callable[[Any, dict], Awaitable[None]] | None = None) -> int:
    sent = 0
    dead: list[Any] = []
    for ws in list(_subs):
        try:
            if send is not None:
                await send(ws, payload)
            else:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            sent += 1
        except Exception:  # noqa: BLE001 -- un panel caído no frena al resto
            dead.append(ws)
    for ws in dead:
        unregister(ws)
    return sent


async def report(
    brigade_id: str,
    msg: str | None = None,
    *,
    inc: int = 1,
    mode: str | None = None,
    send: Callable[[Any, dict], Awaitable[None]] | None = None,
) -> None:
    """Actualiza una brigada y lo re-emite al panel en vivo. No-op si el id no existe."""
    st = _state.get(brigade_id)
    if st is None:
        return
    st["ts"] = time.time()
    if inc:
        st["count"] += inc
    if msg:
        st["last"] = msg
        rec = st.setdefault("recent", [])
        rec.insert(0, {"m": msg, "ts": st["ts"]})  # más nuevo primero
        del rec[_RECENT_CAP:]
    if mode:
        st["mode"] = mode
    await _broadcast(
        {"type": "brigade", "id": brigade_id, "msg": st["last"], "count": st["count"],
         "mode": st["mode"], "ts": st["ts"], "recent": st["recent"]},
        send=send,
    )


def report_tool(tool_name: str, msg: str | None = None) -> None:
    """Mapea una tool_call del agente a su brigada y la reporta (fire-and-forget).
    Pensado para llamarse desde el loop async del agente; si no hay loop, es no-op."""
    bid = TOOL_BRIGADE.get(tool_name)
    if not bid:
        return
    mode = None
    if bid == "seg":
        mode = "⚔️ ATAQUE" if tool_name in _ATTACK_TOOLS else "🛡️ DEFENSA"
    try:
        asyncio.get_running_loop().create_task(report(bid, msg or tool_name, mode=mode))
    except RuntimeError:
        pass
