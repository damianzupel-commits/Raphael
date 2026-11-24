"""Pesos Hebbianos sobre las aristas del grafo del vault (Fase 2 de la estructura
informacional cerebro-símil -- ver docs/SPEC-estructura-informacional-cerebro.md §3.6).

"Lo que se activa junto, se cablea junto" (Hebb, 1949): cuando dos notas se
recuperan/usan JUNTAS en una tarea, el peso de la arista que las une sube. El
spreading activation (Fase 1) propaga más fuerte por las aristas pesadas, así que
con el uso el grafo se auto-organiza según cómo Damian REALMENTE asocia las cosas,
no según cómo cargó la info. La estructura emerge del uso.

PROCESADOR: tier 0 -- contador/cómputo PURO. NO toca ningún LLM ni embeddings.
Persistencia: un JSON en el mismo directorio que el índice de embeddings
(backend/data/, gitignored), profile-aware. Clave de arista = par ORDENADO de
note_ids unido por tab (la arista es no dirigida: (a,b) == (b,a)).

El core (`bump`) es una función pura (pesos + ids -> pesos nuevos), testeable sin
tocar disco ni el vault.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

from ..config import settings
from . import profile

_KEY_SEP = "\t"

# Peso neutro de una arista no reforzada (el spreading la multiplica por esto, o sea
# sin cambio). Cada co-activación suma `_DEFAULT_AMOUNT`; `_CAP` evita que una arista
# muy usada domine todo el grafo (saturación, como la potenciación sináptica real).
_NEUTRAL = 1.0
_DEFAULT_AMOUNT = 0.5
_CAP = 5.0
# Piso de una arista debilitada (LTD / marcado aversivo, Etapa B 2026-10-06): una vía que
# llevó a un error baja por debajo de lo neutro ("no vuelvas por ahí"), pero nunca por
# debajo de `_FLOOR` -- homeostasis: se desincentiva el camino, no se corta del todo.
_FLOOR = 0.3


def _edge_key(a: str, b: str) -> str:
    """Clave canónica (ordenada) de la arista no dirigida entre `a` y `b`."""
    return f"{a}{_KEY_SEP}{b}" if a <= b else f"{b}{_KEY_SEP}{a}"


def bump(
    weights: dict[str, float],
    note_ids: list[str],
    amount: float = _DEFAULT_AMOUNT,
    cap: float = _CAP,
) -> dict[str, float]:
    """Refuerza (en una copia) la arista de CADA par de `note_ids` co-activados.

    Función PURA: no toca disco. Una arista nueva arranca en `_NEUTRAL` y sube
    `amount` por co-activación, topeada en `cap`. Ids repetidos y auto-pares
    (a,a) se ignoran. Devuelve el dict de pesos actualizado."""
    uniq = sorted({nid for nid in note_ids if nid})
    if len(uniq) < 2:
        return dict(weights)
    out = dict(weights)
    for a, b in combinations(uniq, 2):
        key = _edge_key(a, b)
        out[key] = min(cap, out.get(key, _NEUTRAL) + amount)
    return out


def weaken(
    weights: dict[str, float],
    note_ids: list[str],
    amount: float = _DEFAULT_AMOUNT,
    floor: float = _FLOOR,
) -> dict[str, float]:
    """LTD: DEBILITA (en una copia) la arista de cada par de `note_ids` -- la vía que
    llevó a un error. Baja `amount` desde el valor actual (o desde `_NEUTRAL`), topeada
    por abajo en `floor`. Es la contraparte aversiva de `bump`. PURA."""
    uniq = sorted({nid for nid in note_ids if nid})
    if len(uniq) < 2:
        return dict(weights)
    out = dict(weights)
    for a, b in combinations(uniq, 2):
        key = _edge_key(a, b)
        out[key] = max(floor, out.get(key, _NEUTRAL) - amount)
    return out


def as_propagate_weights(weights: dict[str, float]) -> dict[tuple[str, str], float]:
    """Convierte las claves string ('a\\tb') al formato de tuplas ordenadas que
    espera `spreading.propagate(edge_weights=...)`."""
    out: dict[tuple[str, str], float] = {}
    for key, w in weights.items():
        a, _, b = key.partition(_KEY_SEP)
        if b:
            out[(a, b)] = w
    return out


# --- persistencia (profile-aware, junto al índice de embeddings) -----------------

def _weights_path() -> Path:
    emb = Path(profile.current_embeddings_path(settings.obsidian_embeddings_path))
    path = emb.parent / "hebbian_weights.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_weights() -> dict[str, float]:
    import json

    path = _weights_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_weights(weights: dict[str, float]) -> None:
    import json

    _weights_path().write_text(json.dumps(weights), encoding="utf-8")


def reforzar(note_ids: list[str], amount: float = _DEFAULT_AMOUNT) -> int:
    """Carga los pesos, refuerza las aristas entre `note_ids` y persiste.
    Devuelve cuántas aristas distintas quedaron tocadas. Es el 'wire together'
    que llama el recall cuando esas notas se usaron juntas en una tarea."""
    uniq = sorted({nid for nid in note_ids if nid})
    if len(uniq) < 2:
        return 0
    weights = bump(load_weights(), uniq, amount=amount)
    save_weights(weights)
    return len(list(combinations(uniq, 2)))


def debilitar(note_ids: list[str], amount: float = _DEFAULT_AMOUNT) -> int:
    """Carga los pesos, DEBILITA (LTD) las aristas entre `note_ids` y persiste. El
    'no vuelvas por ahí' que llama el crédito negativo cuando esas notas llevaron a un
    error. Devuelve cuántas aristas distintas quedaron tocadas."""
    uniq = sorted({nid for nid in note_ids if nid})
    if len(uniq) < 2:
        return 0
    weights = weaken(load_weights(), uniq, amount=amount)
    save_weights(weights)
    return len(list(combinations(uniq, 2)))
