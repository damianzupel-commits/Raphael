"""Captura automática al cierre de turno (§4 del spec).

Regla (Decisión 4): **capturar es total y barato; destilar es selectivo.**
- El historial CRUDO del turno se guarda SIEMPRE (capa B) — nada se juzga
  trivial al capturar; un "gracias" queda igual, por si algún día importa.
- El EPISODIO destilado se arma solo si el turno fue SUSTANTIVO (usó tools, tuvo
  un momento saliente, o tiene contenido real) — para no llenar el grafo de
  "hola/gracias" resumidos. Lo trivial igual queda entero en el crudo.

Todo pasa por `on_turn_end`, que es 100% defensivo: envuelto en try/except y
gateado por el apagador global. JAMÁS rompe ni frena un turno de chat.
"""

from __future__ import annotations

import logging

from ..config import settings
from . import classifier, distiller, store
from .schema import Episode, RawMessage, now_iso

logger = logging.getLogger("jarvis.memory")


def _current_turn(history: list[dict]) -> list[dict]:
    """El turno en curso = desde el último mensaje 'user' hasta el final."""
    last_user = None
    for i, m in enumerate(history):
        if m.get("role") == "user":
            last_user = i
    if last_user is None:
        return [m for m in history if m.get("role") != "system"]
    return history[last_user:]


def _to_raw(turn: list[dict]) -> list[RawMessage]:
    out: list[RawMessage] = []
    ts = now_iso()
    for i, m in enumerate(turn):
        c = m.get("content")
        if isinstance(c, list):  # multimodal → dejamos solo el texto
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
        out.append(RawMessage(role=m.get("role", "?"), content=str(c or ""), timestamp=ts, index=i))
    return out


def _is_substantive(turn: list[dict]) -> bool:
    """¿Vale la pena destilar un episodio? (el crudo se guarda igual)."""
    for m in turn:
        if m.get("tool_calls"):
            return True
    text = " ".join(str(m.get("content") or "") for m in turn if isinstance(m.get("content"), str))
    return len(text.strip()) >= 400


def _dominio(trigger: str) -> str:
    try:
        from ..skills import classify
        skills = classify(trigger)
        return next(iter(skills)) if skills else ""
    except Exception:  # noqa: BLE001
        return ""


def on_turn_end(conv_id: str, history: list[dict]) -> None:
    """Hook del cierre de turno. Guardado total del crudo + episodio selectivo.
    Nunca lanza."""
    if not getattr(settings, "episodic_memory_enabled", False):
        return
    try:
        turn = _current_turn(history)
        if not turn:
            return
        ts_inicio = now_iso()

        # 1. crudo SIEMPRE (capa B, nada se tira)
        raw = _to_raw(turn)
        store.save_raw(conv_id, raw)

        # 2. episodio solo si sustantivo (destilado selectivo)
        if not _is_substantive(turn):
            return

        trigger = ""
        for m in turn:
            if m.get("role") == "user":
                c = m.get("content")
                trigger = c if isinstance(c, str) else ""
                break

        dominio = _dominio(trigger)
        all_text = " ".join(str(m.get("content") or "") for m in turn if isinstance(m.get("content"), str))
        sensibilidad = classifier.classify(all_text, dominio=dominio)

        ep: Episode = distiller.distill(
            turn, conv_id=conv_id, dominio=dominio, sensibilidad=sensibilidad,
            ts_inicio=ts_inicio, ts_fin=now_iso(),
            use_llm=getattr(settings, "episodic_memory_distill_llm", False),
        )
        store.save_episode(ep)
    except Exception as exc:  # noqa: BLE001 -- la memoria NUNCA rompe un turno
        logger.warning("captura episódica falló (se ignora): %r", exc)
