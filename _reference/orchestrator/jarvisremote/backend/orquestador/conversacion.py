"""Memoria de la CONVERSACIÓN del orquestador con Damian (P2.2): continuidad entre turnos y entre brigadas.

El orquestador es la única voz hacia el usuario y habla con él a través de TODAS las brigadas, así que necesita recordar
de qué se viene hablando. Esta memoria:

  - es ACOTADA: los últimos `MAX_TURNOS` turnos (pedido y mensaje recortados) + un RESUMEN determinista de los anteriores
    (una línea por turno viejo, hasta `MAX_RESUMEN`); no crece sin fin ni necesita otro modelo para resumirse;
  - NO mezcla datos entre brigadas: solo la lee la voz del orquestador (orquestador/voz.py), como DATO, para dar
    continuidad al mensaje. Nunca se le pasa a un jefe ni a un ayudante;
  - vive en `backend/data/orquestador/conversacion.json` (gitignoreado). Best-effort: si el disco falla, la voz sigue
    funcionando sin memoria. Apagable con ORQUESTADOR_MEMORIA=0.

Solo biblioteca estándar.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("orquestador.conversacion")

MAX_TURNOS = 8          # turnos recientes que se guardan con su texto
MAX_RESUMEN = 12        # líneas del resumen de turnos más viejos
MAX_PEDIDO = 300
MAX_MENSAJE = 500
_PATH = Path(__file__).resolve().parent.parent / "data" / "orquestador" / "conversacion.json"
_LOCK = threading.Lock()


def enabled() -> bool:
    return os.getenv("ORQUESTADOR_MEMORIA", "1").strip().lower() not in ("0", "false", "no", "off")


def _corto(texto: str, limite: int) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"


def _load() -> dict:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("turnos"), list) and isinstance(data.get("resumen"), list):
            return data
    except Exception:  # noqa: BLE001 — sin archivo o ilegible: se arranca de cero
        pass
    return {"turnos": [], "resumen": []}


def anotar(pedido: str, brigada: str, mensaje: str) -> None:
    """Suma un turno (lo que pidió Damian, qué brigada lo resolvió y qué se le comunicó) y compacta lo viejo."""
    if not enabled():
        return
    with _LOCK:
        data = _load()
        data["turnos"].append({"ts": round(time.time()), "brigada": brigada, "pedido": _corto(pedido, MAX_PEDIDO),
                               "mensaje": _corto(mensaje, MAX_MENSAJE)})
        while len(data["turnos"]) > MAX_TURNOS:  # lo que sale de la ventana queda como una línea de resumen
            viejo = data["turnos"].pop(0)
            data["resumen"].append(f"[{viejo.get('brigada', '?')}] {_corto(viejo.get('pedido', ''), 120)}")
        data["resumen"] = data["resumen"][-MAX_RESUMEN:]
        try:
            _PATH.parent.mkdir(parents=True, exist_ok=True)
            _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            logger.warning("no se pudo guardar la memoria de conversación del orquestador", exc_info=True)


def para_prompt() -> str:
    """La conversación previa como texto para la voz del orquestador ('' si no hay o está apagada). Es DATO."""
    if not enabled():
        return ""
    with _LOCK:
        data = _load()
    lineas: list[str] = []
    if data["resumen"]:
        lineas.append("Antes se habló de: " + " · ".join(str(x) for x in data["resumen"]))
    for t in data["turnos"]:
        lineas.append(f"- Damian pidió ({t.get('brigada', '?')}): {t.get('pedido', '')}\n  Raphael le dijo: {t.get('mensaje', '')}")
    return "\n".join(lineas)


def reset() -> None:
    """Borra la memoria de conversación (tests y validaciones: cada corrida arranca limpia)."""
    with _LOCK:
        try:
            _PATH.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
