"""Representación sucesora -- la capa PREDICTIVA de Raphael (Fase 5 de la estructura
informacional, ver docs/SPEC-raphael-predictivo.md §2).

A diferencia de los pesos Hebbianos ([[hebbian]]), que son SIMÉTRICOS (A–B: "se usan
juntas"), esto guarda transiciones DIRIGIDAS y TEMPORALES: "después de la nota A,
Damian suele ir a la nota B" (A → B). Es el análogo de la *successor representation*
del hipocampo (Dayan 1993; Stachenfeld 2017): el cerebro no guarda solo dónde estás,
sino a dónde solés ir después. Con eso el recall deja de ser puramente reactivo y se
vuelve ANTICIPATORIO: puede pre-cargar lo que probablemente sigue en el hilo de
pensamiento, no solo lo asociado por similitud.

Aprende del USO real: cuando Raphael recupera notas y se marcan como usadas
(reforzar=True), registra la transición foco_anterior → foco_actual. El "foco
anterior" es estado de sesión (en memoria, se reinicia al reiniciar el backend); los
CONTEOS de transiciones se persisten (aprende a través de sesiones).

PROCESADOR: tier 0 -- conteo/cómputo PURO, NO toca ningún LLM ni embeddings.
El core (`observe_sequence`, `observe_pairs`, `successor_scores`) es puro y testeable.
"""

from __future__ import annotations

from ..config import settings
from . import profile

# Foco de la sesión actual: la(s) nota(s) sobre la(s) que estuvo el último recall.
# En memoria a propósito (un "dónde estoy pensando ahora" efímero); los conteos sí
# se persisten.
_last_focus: list[str] = []


# --- core PURO -------------------------------------------------------------------

def observe_sequence(trans: dict[str, dict[str, float]], ids: list[str], amount: float = 1.0) -> dict[str, dict[str, float]]:
    """Registra (en una copia) transiciones dirigidas entre elementos CONSECUTIVOS de
    `ids` (A→B→C da A→B y B→C). Puro."""
    out = {k: dict(v) for k, v in trans.items()}
    seq = [i for i in ids if i]
    for a, b in zip(seq, seq[1:]):
        if a == b:
            continue
        out.setdefault(a, {})
        out[a][b] = out[a].get(b, 0.0) + amount
    return out


def observe_pairs(trans: dict[str, dict[str, float]], from_ids: list[str], to_ids: list[str], amount: float = 1.0) -> dict[str, dict[str, float]]:
    """Registra (en una copia) transiciones de cada `from_id` a cada `to_id`. Puro."""
    out = {k: dict(v) for k, v in trans.items()}
    froms = [f for f in dict.fromkeys(from_ids) if f]
    tos = [t for t in dict.fromkeys(to_ids) if t]
    for a in froms:
        for b in tos:
            if a == b:
                continue
            out.setdefault(a, {})
            out[a][b] = out[a].get(b, 0.0) + amount
    return out


def successor_scores(trans: dict[str, dict[str, float]], from_ids: list[str], top: int | None = None) -> dict[str, float]:
    """Distribución de sucesores probables agregada sobre `from_ids`. Para cada origen
    normaliza sus salidas a probabilidad condicional y las promedia; después escala el
    resultado a 0..1. Devuelve {to_id: score}. Puro."""
    agg: dict[str, float] = {}
    for a in from_ids:
        row = trans.get(a)
        if not row:
            continue
        total = sum(row.values()) or 1.0
        for b, c in row.items():
            agg[b] = agg.get(b, 0.0) + c / total
    if not agg:
        return {}
    mx = max(agg.values()) or 1.0
    scored = {b: v / mx for b, v in agg.items()}
    if top:
        scored = dict(sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:top])
    return scored


def decay_all(trans: dict[str, dict[str, float]], factor: float = 0.9, floor: float = 0.05) -> dict[str, dict[str, float]]:
    """Envejece todas las transiciones (hábitos de pensamiento viejos pesan menos).
    Puro. Las que caen por debajo de `floor` se descartan."""
    out: dict[str, dict[str, float]] = {}
    for a, row in trans.items():
        nr = {b: c * factor for b, c in row.items() if c * factor >= floor}
        if nr:
            out[a] = nr
    return out


# --- persistencia (profile-aware, junto al índice de embeddings) -----------------

def _path():
    from pathlib import Path

    emb = Path(profile.current_embeddings_path(settings.obsidian_embeddings_path))
    p = emb.parent / "successor_transitions.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load() -> dict[str, dict[str, float]]:
    import json

    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(trans: dict[str, dict[str, float]]) -> None:
    import json

    _path().write_text(json.dumps(trans), encoding="utf-8")


# --- runtime (aprendizaje + predicción) ------------------------------------------

def step(current_ids: list[str], amount: float = 1.0) -> int:
    """Marca un 'paso de pensamiento': registra foco_anterior → foco_actual y actualiza
    el foco. Devuelve cuántas transiciones se registraron. Llamalo cuando esas notas se
    usaron de verdad (reforzar=True), no por explorar."""
    global _last_focus
    cur = [i for i in dict.fromkeys(current_ids) if i]
    n = 0
    if _last_focus and cur:
        trans = observe_pairs(load(), _last_focus, cur, amount=amount)
        save(trans)
        n = len([1 for a in _last_focus for b in cur if a != b])
    if cur:
        _last_focus = cur
    return n


def predict(from_ids: list[str], top: int = 10) -> dict[str, float]:
    """Sucesores probables del foco dado (read-only): {note_id: score 0..1}."""
    return successor_scores(load(), [i for i in from_ids if i], top=top)


def surprise(current_ids: list[str]) -> float:
    """Error de predicción (Fase 6): qué tan INESPERADO fue el foco actual dado el foco
    anterior de la sesión. 0 = totalmente predicho (lo que se esperaba), 1 = sorpresa
    total. Read-only (usa `_last_focus`, no lo modifica). Llamalo ANTES de `step`.

    - Sin foco anterior: 0 (no había expectativa, no puede sorprender).
    - Con foco anterior pero sin transiciones aprendidas desde él: 0.5 (había dónde
      estar parado pero ninguna expectativa formada -> sorpresa moderada)."""
    cur = [i for i in current_ids if i]
    if not _last_focus or not cur:
        return 0.0
    pred = successor_scores(load(), _last_focus)
    if not pred:
        return 0.5
    best = max(pred.get(i, 0.0) for i in cur)
    return round(1.0 - min(1.0, best), 3)
