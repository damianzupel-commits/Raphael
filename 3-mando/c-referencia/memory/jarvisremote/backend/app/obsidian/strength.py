"""Fuerza de recuperación de las notas del vault -- olvido adaptativo (Fase 4 de la
estructura informacional cerebro-símil, ver docs/SPEC-estructura-informacional-cerebro.md
§3.7). Complementa los pesos Hebbianos de aristas (Fase 2, [[hebbian]]) con una fuerza
por NODO.

Distinción de Bjork (storage strength ≠ retrieval strength): la memoria episódica ya
tiene `salience` (importancia intrínseca, fija en la captura). ESTO es otra cosa: la
**fuerza de recuperación**, que sube cuando una nota se USA y **decae con el tiempo sin
uso**. Una nota muy usada hace poco se recupera más fácil; si pasa mucho sin usarse,
ese impulso se desvanece y vuelve a lo neutro. Es "retrieval-dependent forgetting".

Olvido como FEATURE, no avería (§3.7): nada se borra en duro -- el crudo firmado de la
memoria episódica queda intacto (§3.3). Lo único que pasa es que una nota que no se usa
hace rato pierde su impulso y **baja en el ranking** del recall, para dejar arriba lo
que de verdad estás usando. El factor nunca baja de 1.0 (neutro): no enterramos nada por
debajo de lo normal, solo dejamos de darle el boost a lo que ya no tocás.

PROCESADOR: tier 0 -- cómputo PURO (decaimiento exponencial + bump). NO toca ningún LLM
ni embeddings. Persistencia: JSON junto al índice de embeddings (profile-aware), mismo
criterio que [[hebbian]]. El `bump` al usar una nota es también el lado de "retrieval
strength" de la reconsolidación (§3.5): recuperar y usar una nota la refuerza.

El core (`effective_boost`/`factor`) es puro y testeable sin disco ni reloj real.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import settings
from . import profile

# Vida media del impulso en días: a los `_HALF_LIFE_DAYS` sin usar, el boost cae a la
# mitad. Cada uso suma `_INCREMENT` al boost (topeado en `_CAP`). El factor de ranking
# es 1.0 + boost_efectivo (nunca < 1.0).
_HALF_LIFE_DAYS = 14.0
_INCREMENT = 0.5
_CAP = 2.0  # boost máximo -> factor máximo 3.0
# Valencia NEGATIVA (Etapa B / marcado aversivo, 2026-10-06): una nota que llevó a un
# error recibe un boost NEGATIVO, que la baja en el ranking -- pero con PISO, nunca la
# suprime del todo (homeostasis). Boost mínimo -0.5 -> factor mínimo 0.5: sigue
# recuperable, solo pesa menos. La aversión también decae con el tiempo (como el boost).
_FLOOR_BOOST = -0.5
_FLOOR_FACTOR = 0.5


def effective_boost(boost: float, last_used_iso: str, now: datetime, half_life_days: float = _HALF_LIFE_DAYS) -> float:
    """Boost decaído exponencialmente según los días transcurridos desde `last_used`.
    Función PURA. Funciona con boost positivo (refuerzo) y negativo (aversión): la
    MAGNITUD decae hacia 0 conservando el signo. Fecha ilegible -> sin decaer (conservador)."""
    if boost == 0.0:
        return 0.0
    try:
        last = datetime.fromisoformat(last_used_iso)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return boost
    elapsed_days = max(0.0, (now - last).total_seconds() / 86400.0)
    if half_life_days <= 0.0:
        return 0.0
    return boost * (0.5 ** (elapsed_days / half_life_days))


def factor(boost: float, last_used_iso: str, now: datetime, half_life_days: float = _HALF_LIFE_DAYS) -> float:
    """Multiplicador de ranking para una nota: 1.0 (neutro) + su boost decaído. El boost
    positivo la sube; el negativo (aversión) la baja, pero con PISO `_FLOOR_FACTOR` --
    nunca se entierra del todo."""
    return max(_FLOOR_FACTOR, 1.0 + effective_boost(boost, last_used_iso, now, half_life_days))


def _bump_entry(entry: dict | None, now: datetime, increment: float = _INCREMENT, cap: float = _CAP) -> dict:
    """Aplica un refuerzo (increment>0) o una aversión (increment<0) a una entrada: parte
    del boost decaído de hoy, le suma `increment`, lo acota a [`_FLOOR_BOOST`, `cap`] y
    marca `last_used=now`. PURO."""
    boost0 = effective_boost(entry.get("boost", 0.0), entry.get("last_used", ""), now) if entry else 0.0
    return {"boost": max(_FLOOR_BOOST, min(cap, boost0 + increment)), "last_used": now.isoformat()}


# --- persistencia (profile-aware, junto al índice de embeddings) -----------------

def _path():
    from pathlib import Path

    emb = Path(profile.current_embeddings_path(settings.obsidian_embeddings_path))
    p = emb.parent / "retrieval_strength.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load() -> dict[str, dict]:
    import json

    p = _path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict[str, dict]) -> None:
    import json

    _path().write_text(json.dumps(data), encoding="utf-8")


def bump(note_ids: list[str], *, increment: float = _INCREMENT, now: datetime | None = None) -> int:
    """Refuerza la fuerza de recuperación de cada nota usada. Devuelve cuántas tocó.
    Es el 'se recuperó y se usó -> se refuerza' (reconsolidación §3.5, lado nodo)."""
    ids = [n for n in dict.fromkeys(note_ids) if n]  # únicos, en orden
    if not ids:
        return 0
    now = now or datetime.now(timezone.utc)
    data = load()
    for nid in ids:
        data[nid] = _bump_entry(data.get(nid), now, increment=increment)
    save(data)
    return len(ids)


def factors_for(note_ids: list[str], now: datetime | None = None) -> dict[str, float]:
    """Factor de ranking (>=1.0) por nota. Una nota sin entrada = 1.0 (neutro): nunca
    se penaliza una nota por no haber sido usada todavía (no enterramos lo nuevo)."""
    now = now or datetime.now(timezone.utc)
    data = load()
    out: dict[str, float] = {}
    for nid in note_ids:
        e = data.get(nid)
        out[nid] = factor(e.get("boost", 0.0), e.get("last_used", ""), now) if e else 1.0
    return out
