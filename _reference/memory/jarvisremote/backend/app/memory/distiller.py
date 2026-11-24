"""Destilador: convierte el historial de un turno en un Episodio (§4 del spec).

Guarda RECUERDOS, no el transcript crudo (eso lo guarda store.py aparte, capa
B). Dos modos:
- **Heurística** (default, Fase 1): sin LLM, barato, sin latencia. Extrae
  trigger/acciones/decisiones/resultado/beats de la estructura del historial.
- **LLM** (opt-in, `episodic_memory_distill_llm`): un resumen por modelo. SPLIT
  (Decisión 3): `tecnico` puede ir al modelo de chat (cloud); `personal` SIEMPRE
  local, jamás a la nube. Fase 1 deja el gancho; el modo por default es heurística.
"""

from __future__ import annotations

from typing import Any

from .schema import Beat, Episode, Outcome, now_iso

# Marcadores de "momento" (beat) por significado (no por paso mecánico).
_BEAT_MARKERS: list[tuple[str, str]] = [
    ("correccion", "no, así no"), ("correccion", "no es así"), ("correccion", "está mal"),
    ("correccion", "esta mal"), ("correccion", "mejor no"), ("correccion", "cambiá"),
    ("decision", "dale"), ("decision", "confirmo"), ("decision", "vamos con"),
    ("decision", "elijo"), ("decision", "prefiero"), ("preferencia", "me gusta más"),
    ("descubrimiento", "resultó que"), ("descubrimiento", "resulto que"),
    ("descubrimiento", "descubrí"), ("fallo", "falló"), ("fallo", "fallo"),
    ("fallo", "error"), ("fallo", "no funciona"), ("fallo", "no anduvo"),
]

_FALLO_HINTS = ("error", "falló", "fallo", "no funciona", "no anduvo", "exception", "traceback")
_EXITO_HINTS = ("listo", "funciona", "quedó", "quedo", "resuelto", "ok", "hecho", "perfecto")


def _tool_names(history: list[dict]) -> list[str]:
    """Nombres de tools invocadas en el turno (de los tool_calls del assistant)."""
    names: list[str] = []
    for m in history:
        for tc in (m.get("tool_calls") or []):
            fn = (tc.get("function") or {}).get("name")
            if fn and fn not in names:
                names.append(fn)
    return names


def _first_user_text(history: list[dict]) -> str:
    for m in history:
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):  # mensaje multimodal
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
    return ""


def _last_assistant_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"].strip():
            return m["content"]
    return ""


def _all_text(history: list[dict]) -> str:
    parts: list[str] = []
    for m in history:
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
    return "\n".join(parts)


def _detect_beats(history: list[dict]) -> list[Beat]:
    beats: list[Beat] = []
    for m in history:
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if not isinstance(c, str):
            continue
        low = c.lower()
        for kind, marker in _BEAT_MARKERS:
            if marker in low:
                beats.append(Beat(kind=kind, text=c.strip()[:200]))
                break  # un beat por mensaje
    return beats


def _outcome(history: list[dict]) -> Outcome:
    last = _last_assistant_text(history).lower()
    text = _all_text(history).lower()
    if any(h in last for h in _EXITO_HINTS):
        return "exito"
    if any(h in text for h in _FALLO_HINTS):
        return "fallo" if any(h in last for h in _FALLO_HINTS) else "parcial"
    return "sin_desenlace"


def _salience(episode: Episode) -> float:
    """Importancia 0-1: sube con beats (decisiones/fallos), acciones y desenlace."""
    s = 0.15
    s += min(0.4, 0.1 * len(episode.beats))
    s += min(0.25, 0.05 * len(episode.acciones))
    if episode.resultado in ("fallo", "exito"):
        s += 0.2
    if episode.pendientes:
        s += 0.1
    return round(min(1.0, s), 3)


def distill_heuristic(history: list[dict], *, conv_id: str, dominio: str,
                      sensibilidad: str, ts_inicio: str, ts_fin: str) -> Episode:
    ep = Episode(
        level="tarea", conv_id=conv_id,
        timestamp_inicio=ts_inicio, timestamp_fin=ts_fin,
        trigger=_first_user_text(history).strip()[:400],
        dominio=dominio,
        acciones=_tool_names(history),
        beats=_detect_beats(history),
        sensibilidad=sensibilidad,  # type: ignore[arg-type]
        distilled_by="heuristica",
    )
    ep.resultado = _outcome(history)
    # Decisiones = los beats de tipo decisión/corrección/preferencia (resumidos).
    ep.decisiones = [f"{b.kind}: {b.text}" for b in ep.beats
                     if b.kind in ("decision", "correccion", "preferencia")]
    # "Porqué": la última respuesta del asistente suele traer la conclusión/lección.
    ep.porque = _last_assistant_text(history).strip()[:400]
    ep.salience = _salience(ep)
    return ep


def distill(history: list[dict], *, conv_id: str, dominio: str, sensibilidad: str,
            ts_inicio: str, ts_fin: str, use_llm: bool = False) -> Episode:
    """Punto de entrada. Fase 1: heurística. El gancho LLM queda para Fase 2
    (respeta el split: `personal` nunca al cloud). Si el LLM falla o está off,
    cae a heurística — nunca rompe la captura."""
    ep = distill_heuristic(history, conv_id=conv_id, dominio=dominio,
                           sensibilidad=sensibilidad, ts_inicio=ts_inicio, ts_fin=ts_fin)
    if not use_llm:
        return ep
    # TODO Fase 2: llamada real al modelo (cloud si tecnico, local si personal).
    # Se deja armado el esqueleto para no reescribir la firma después.
    try:
        ep = _distill_llm(history, base=ep)  # noqa: F841
    except Exception:  # noqa: BLE001 -- el LLM nunca debe romper la captura
        pass
    return ep


def _distill_llm(history: list[dict], *, base: Episode) -> Episode:
    """Placeholder Fase 2. Debe respetar: si base.sensibilidad == 'personal',
    usar SOLO el modelo local (jamás cloud). Por ahora devuelve la heurística."""
    return base
