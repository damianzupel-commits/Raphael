"""Aprendizaje del uso (tier 0: contadores, sin modelo): pesos hebbianos, fuerza de recuperación, sucesión y crédito.

- Hebb: lo que se usa junto, se cablea junto (aristas simétricas). Con piso y tope.
- Fuerza de recuperación: sube al usar una nota y decae sin uso (olvido como feature: nada se borra, solo baja en el
  ranking lo que no se toca; nunca baja de 0.5 ni se entierra lo nuevo).
- Sucesión: transiciones DIRIGIDAS "después de A, solés ir a B" (predicción anticipatoria y sorpresa).
- Crédito: del resultado de una tarea (tests, error, corrección, feedback explícito) a las notas usadas.

El núcleo son funciones puras; `LearningStore` las persiste en el espacio de la brigada. Portado de `hebbian.py`,
`strength.py`, `successor.py` y `feedback.py` de JarvisRemote.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations
from typing import Any

# --- Hebb -------------------------------------------------------------------------------------------------------------
NEUTRAL, CAP, FLOOR, AMOUNT = 1.0, 5.0, 0.3, 0.5


def edge_key(a: str, b: str) -> str:
    return f"{a}\t{b}" if a <= b else f"{b}\t{a}"


def bump(weights: dict[str, float], note_ids: list[str], amount: float = AMOUNT, cap: float = CAP) -> dict[str, float]:
    uniq = sorted({n for n in note_ids if n})
    out = dict(weights)
    for a, b in combinations(uniq, 2):
        k = edge_key(a, b)
        out[k] = min(cap, out.get(k, NEUTRAL) + amount)
    return out


def weaken(weights: dict[str, float], note_ids: list[str], amount: float = AMOUNT, floor: float = FLOOR) -> dict[str, float]:
    """LTD: debilita la vía que llevó a un error, con piso (no la borra)."""
    uniq = sorted({n for n in note_ids if n})
    out = dict(weights)
    for a, b in combinations(uniq, 2):
        k = edge_key(a, b)
        out[k] = max(floor, out.get(k, NEUTRAL) - amount)
    return out


def as_propagate_weights(weights: dict[str, float]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for key, w in weights.items():
        a, _, b = key.partition("\t")
        if b:
            out[(a, b)] = w
    return out


# --- fuerza de recuperación -------------------------------------------------------------------------------------------
HALF_LIFE_DAYS, INCREMENT, BOOST_CAP, FLOOR_BOOST, FLOOR_FACTOR = 14.0, 0.5, 2.0, -0.5, 0.5


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def effective_boost(boost: float, last_used_iso: str, now: datetime, half_life_days: float = HALF_LIFE_DAYS) -> float:
    """Boost decaído exponencialmente; la MAGNITUD decae hacia 0 conservando el signo. Fecha ilegible: sin decaer."""
    if boost == 0.0:
        return 0.0
    try:
        last = _aware(datetime.fromisoformat(last_used_iso))
    except (ValueError, TypeError):
        return boost
    if half_life_days <= 0.0:
        return 0.0
    days = max(0.0, (_aware(now) - last).total_seconds() / 86400.0)
    return boost * (0.5 ** (days / half_life_days))


def factor(boost: float, last_used_iso: str, now: datetime) -> float:
    """Multiplicador de ranking: 1.0 + boost decaído, con piso (nunca se entierra del todo)."""
    return max(FLOOR_FACTOR, 1.0 + effective_boost(boost, last_used_iso, now))


def bump_entry(entry: dict | None, now: datetime, increment: float = INCREMENT, cap: float = BOOST_CAP) -> dict:
    b0 = effective_boost(entry.get("boost", 0.0), entry.get("last_used", ""), now) if entry else 0.0
    return {"boost": max(FLOOR_BOOST, min(cap, b0 + increment)), "last_used": _aware(now).isoformat()}


# --- sucesión (predictivo) --------------------------------------------------------------------------------------------
def observe_pairs(trans: dict[str, dict[str, float]], from_ids: list[str], to_ids: list[str],
                  amount: float = 1.0) -> dict[str, dict[str, float]]:
    out = {k: dict(v) for k, v in trans.items()}
    for a in dict.fromkeys(f for f in from_ids if f):
        for b in dict.fromkeys(t for t in to_ids if t):
            if a != b:
                out.setdefault(a, {})
                out[a][b] = out[a].get(b, 0.0) + amount
    return out


def successor_scores(trans: dict[str, dict[str, float]], from_ids: list[str], top: int | None = None) -> dict[str, float]:
    """Sucesores probables agregados sobre `from_ids` (probabilidad condicional promedio, escalada a 0..1)."""
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
    return dict(sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:top]) if top else scored


def decay_all(trans: dict[str, dict[str, float]], factor_: float = 0.9, floor: float = 0.05) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for a, row in trans.items():
        nr = {b: c * factor_ for b, c in row.items() if c * factor_ >= floor}
        if nr:
            out[a] = nr
    return out


def surprise_of(trans: dict[str, dict[str, float]], last_focus: list[str], current: list[str]) -> float:
    """Error de predicción: 0 = lo esperado, 1 = sorpresa total. Sin foco anterior no hay expectativa (0); con foco pero
    sin transiciones aprendidas, 0.5."""
    cur = [i for i in current if i]
    if not last_focus or not cur:
        return 0.0
    pred = successor_scores(trans, last_focus)
    if not pred:
        return 0.5
    return round(1.0 - min(1.0, max(pred.get(i, 0.0) for i in cur)), 3)


# --- crédito por resultado --------------------------------------------------------------------------------------------
_IMPLICIT_TRUSTED = {"codigo", "auditoria", "recall", "accion_externa", "ingesta"}


def reward_from_signals(signals: dict, situacion: str = "recall") -> float:
    """Reward en [-1, 2]. El feedback explícito pesa fuerte; las señales implícitas solo cuentan en situaciones
    objetivas (tests, fix verificado), no en conversación o consejo."""
    r = 0.0
    if signals.get("explicit") is not None:
        r += float(signals["explicit"])
    if situacion in _IMPLICIT_TRUSTED:
        if signals.get("tests_ok") is True:
            r += 1.0
        elif signals.get("tests_ok") is False:
            r -= 1.0
        if signals.get("had_error"):
            r -= 0.5
        if signals.get("corrected"):
            r -= 0.5
    return max(-1.0, min(2.0, round(r, 3)))


class LearningStore:
    """Persiste Hebb, fuerza y sucesión en el espacio de la brigada (colección `aprendizaje`, un doc por tema)."""

    COLLECTION = "aprendizaje"

    def __init__(self, space: Any, now) -> None:
        self.space = space
        self._now = now

    def _get(self, key: str) -> dict:
        return self.space.get(self.COLLECTION, key) or {}

    def _put(self, key: str, doc: dict) -> None:
        self.space.put(self.COLLECTION, key, doc)

    # Hebb
    def weights(self) -> dict[str, float]:
        return self._get("hebb").get("w", {})

    def reinforce(self, ids: list[str], amount: float = AMOUNT) -> int:
        uniq = sorted({n for n in ids if n})
        if len(uniq) < 2:
            return 0
        self._put("hebb", {"w": bump(self.weights(), uniq, amount)})
        return len(list(combinations(uniq, 2)))

    def weaken(self, ids: list[str], amount: float = AMOUNT) -> int:
        uniq = sorted({n for n in ids if n})
        if len(uniq) < 2:
            return 0
        self._put("hebb", {"w": weaken(self.weights(), uniq, amount)})
        return len(list(combinations(uniq, 2)))

    # fuerza
    def strengths(self) -> dict[str, dict]:
        return self._get("strength").get("s", {})

    def strengthen(self, ids: list[str], increment: float = INCREMENT) -> int:
        uniq = [n for n in dict.fromkeys(ids) if n]
        if not uniq:
            return 0
        data, now = self.strengths(), self._now()
        for nid in uniq:
            data[nid] = bump_entry(data.get(nid), now, increment=increment)
        self._put("strength", {"s": data})
        return len(uniq)

    def factors_for(self, ids: list[str]) -> dict[str, float]:
        data, now = self.strengths(), self._now()
        return {nid: (factor(e.get("boost", 0.0), e.get("last_used", ""), now) if (e := data.get(nid)) else 1.0)
                for nid in ids}

    # sucesión
    def transitions(self) -> dict[str, dict[str, float]]:
        return self._get("succ").get("t", {})

    def last_focus(self) -> list[str]:
        return self._get("focus").get("ids", [])

    def step(self, current: list[str], amount: float = 1.0) -> int:
        """Un paso de pensamiento: foco anterior -> foco actual. Se llama cuando las notas se USARON de verdad."""
        cur = [i for i in dict.fromkeys(current) if i]
        last, n = self.last_focus(), 0
        if last and cur:
            self._put("succ", {"t": observe_pairs(self.transitions(), last, cur, amount)})
            n = len([1 for a in last for b in cur if a != b])
        if cur:
            self._put("focus", {"ids": cur})
        return n

    def predict(self, from_ids: list[str], top: int = 10) -> dict[str, float]:
        return successor_scores(self.transitions(), [i for i in from_ids if i], top=top)

    def surprise(self, current: list[str]) -> float:
        return surprise_of(self.transitions(), self.last_focus(), current)

    def age(self, factor_: float = 0.9) -> None:
        self._put("succ", {"t": decay_all(self.transitions(), factor_)})

    # crédito
    def credit(self, ids: list[str], reward: float = 1.0) -> dict:
        """reward>0 refuerza (LTP); reward<0 marca aversivo (LTD, con pisos); 0 no hace nada."""
        uniq = [n for n in dict.fromkeys(ids) if n]
        if not uniq or reward == 0:
            return {"tipo": "nada", "notas": 0, "aristas": 0, "reward": reward}
        if reward > 0:
            f = min(2.0, float(reward))
            return {"tipo": "refuerzo", "notas": self.strengthen(uniq, 0.5 * f),
                    "aristas": self.reinforce(uniq, 0.5 * f), "reward": round(float(reward), 3)}
        mag = min(1.0, -float(reward))
        return {"tipo": "aversion", "notas": self.strengthen(uniq, -0.5 * mag),
                "aristas": self.weaken(uniq, 0.4 * mag), "reward": round(float(reward), 3)}

    def outcome(self, ids: list[str], signals: dict, situacion: str = "recall") -> dict:
        out = self.credit(ids, reward_from_signals(signals, situacion))
        out["situacion"] = situacion
        return out
