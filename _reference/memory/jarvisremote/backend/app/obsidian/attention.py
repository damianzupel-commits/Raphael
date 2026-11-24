"""Atención / separación de patrones -- la compuerta del recall (principios 9+ de la
estructura informacional, ver docs/SPEC-raphael-predictivo.md).

Dos funciones informacionales del cerebro que el recall base no tenía:
  - ATENCIÓN (gating): no todo lo que se activa entra al foco; se selecciona un
    subconjunto chico y pertinente (competencia sesgada, cuello de botella del workspace).
  - SEPARACIÓN DE PATRONES: mantener distintas las memorias parecidas para que no se
    pisen (anti-interferencia; el hipocampo lo hace). El recall por similitud, solo,
    tiende a traer 5 copias de lo mismo; esto lo evita.

Ambas se resuelven con **MMR (Maximal Marginal Relevance)**: reordena los candidatos
premiando a los que son RELEVANTES *y* DISTINTOS de lo ya elegido. El resultado es un
foco enfocado y diverso, no redundante.

PROCESADOR: tier 0 -- cómputo PURO (+ embeddings para medir "distinto"). El core
`mmr_order` es puro y testeable con vectores sintéticos.
"""

from __future__ import annotations

from collections.abc import Callable


def mmr_order(
    ranked_ids: list[str],
    scores: dict[str, float],
    vectors: dict[str, list[float]],
    cosine: Callable[[list[float], list[float]], float],
    lam: float = 0.72,
    consider: int = 40,
) -> list[str]:
    """Reordena `ranked_ids` (ya ordenados por score) con MMR: cada paso elige el
    candidato que maximiza `lam*relevancia - (1-lam)*máxima_similitud_con_lo_ya_elegido`.
    `lam` alto = más peso a la relevancia; bajo = más a la diversidad. Función PURA.

    Solo reordena los primeros `consider` (el resto queda detrás en su orden original:
    diversificar la cola no aporta y cuesta). Notas sin vector se tratan como de
    diversidad neutra (no se penalizan por no tener embedding)."""
    if not ranked_ids:
        return []
    head = ranked_ids[:consider]
    tail = ranked_ids[consider:]
    # normaliza relevancia a 0..1 sobre la cabeza
    mx = max((scores.get(i, 0.0) for i in head), default=0.0) or 1.0
    rel = {i: scores.get(i, 0.0) / mx for i in head}

    selected: list[str] = []
    remaining = list(head)
    while remaining:
        best, best_val = None, -1e18
        for cid in remaining:
            if not selected:
                div = 0.0
            else:
                vc = vectors.get(cid)
                sims = [cosine(vc, vectors[s]) for s in selected if vc is not None and s in vectors]
                div = max(sims) if sims else 0.0
            val = lam * rel.get(cid, 0.0) - (1.0 - lam) * div
            if val > best_val:
                best_val, best = val, cid
        selected.append(best)
        remaining.remove(best)
    return selected + tail
