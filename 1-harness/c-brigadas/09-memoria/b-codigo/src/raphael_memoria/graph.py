"""Cómputo de grafo puro (tier 0: sin modelo, determinista, gratis): propagación de activación, diversidad (MMR),
analogía estructural, huecos de conocimiento y clusters. Todo testeable con grafos sintéticos, sin vault ni embeddings.

Portado de `spreading.py`, `attention.py`, `analogy.py`, `curiosity.py` y el núcleo de `consolidation.py`.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from itertools import combinations


# --- spreading activation (Collins & Loftus 1975) ---------------------------------------------------------------------
def propagate(seeds: dict[str, float], adjacency: dict[str, set[str]], hops: int = 2, decay: float = 0.5,
              edge_weights: dict[tuple[str, str], float] | None = None) -> dict[str, float]:
    """Difunde la activación de las semillas por el grafo no dirigido. Un nodo alcanzado desde varias semillas SUMA
    activación: esa convergencia hace emerger lo relevante que no matcheaba literal. Con `edge_weights` (Hebb) el factor
    de un salto es `decay * peso(arista)`. `decay < 1` garantiza que no diverge."""
    activation: dict[str, float] = defaultdict(float)
    for node, a in seeds.items():
        activation[node] += a
    frontier = dict(seeds)
    for _ in range(max(0, hops)):
        contrib: dict[str, float] = defaultdict(float)
        for node, act in frontier.items():
            for nb in adjacency.get(node, ()):
                w = decay
                if edge_weights is not None:
                    w = decay * edge_weights.get((node, nb) if node < nb else (nb, node), 1.0)
                contrib[nb] += act * w
        if not contrib:
            break
        for nb, c in contrib.items():
            activation[nb] += c
        frontier = contrib
    return dict(activation)


def adjacency_from_edges(edges: list[dict]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    return adj


# --- atención / separación de patrones --------------------------------------------------------------------------------
def mmr_order(ranked_ids: list[str], scores: dict[str, float], vectors: dict[str, list[float]],
              cosine: Callable[[list[float], list[float]], float], lam: float = 0.72, consider: int = 40) -> list[str]:
    """Reordena con MMR: cada paso elige lo RELEVANTE y DISTINTO de lo ya elegido (no 5 copias de lo mismo). Solo los
    primeros `consider`; las notas sin vector no se penalizan."""
    if not ranked_ids:
        return []
    head, tail = ranked_ids[:consider], ranked_ids[consider:]
    mx = max((scores.get(i, 0.0) for i in head), default=0.0) or 1.0
    rel = {i: scores.get(i, 0.0) / mx for i in head}
    chosen: list[str] = []
    remaining = list(head)
    while remaining:
        best, best_val = remaining[0], -1e18
        for cid in remaining:
            vc = vectors.get(cid)
            sims = [cosine(vc, vectors[s]) for s in chosen if vc is not None and s in vectors]
            val = lam * rel.get(cid, 0.0) - (1.0 - lam) * (max(sims) if sims else 0.0)
            if val > best_val:
                best, best_val = cid, val
        chosen.append(best)
        remaining.remove(best)
    return chosen + tail


# --- confianza (metacognición): sale del proceso de recuperación, no de un modelo --------------------------------------
def note_confidence(score: float, max_score: float, is_seed: bool, fuerza: float = 1.0) -> float:
    base = (score / max_score) if max_score else 0.0
    base *= 1.0 if is_seed else 0.75
    base *= min(1.2, max(0.6, fuerza))
    return round(min(1.0, base), 3)


def overall_confidence(scores: list[float], seed_strengths: list[float]) -> float:
    """Mejor semilla 45 % + margen del ganador sobre el segundo 35 % + corroboración 20 %."""
    if not scores:
        return 0.0
    top = scores[0] or 1e-9
    second = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, (top - second) / top)
    best_seed = max(seed_strengths) if seed_strengths else 0.0
    corrob = min(1.0, len([s for s in scores if s >= 0.3 * top]) / 5.0)
    return round(min(1.0, 0.45 * min(1.0, best_seed) + 0.35 * margin + 0.20 * corrob), 3)


def recommendation(conf: float, high: float = 0.6, low: float = 0.35) -> str:
    """alta: confiá · media: usable con pinzas · baja: no confíes, volvé a la fuente."""
    return "alta" if conf >= high else "baja" if conf <= low else "media"


# --- analogía estructural (Gentner): mismo ROL en otro dominio -------------------------------------------------------
_SQRT3 = math.sqrt(3.0)


def clustering_coefficient(node: str, adjacency: dict[str, set[str]]) -> float:
    neigh = list(adjacency.get(node, set()))
    k = len(neigh)
    if k < 2:
        return 0.0
    links = sum(1 for i in range(k) for j in range(i + 1, k) if neigh[j] in adjacency.get(neigh[i], set()))
    return links / (k * (k - 1) / 2)


def role_signature(node: str, adjacency: dict[str, set[str]], domains: dict[str, str], maxdeg: int,
                   ndom_total: int) -> tuple[float, float, float]:
    """(grado relativo, agrupamiento del barrio, diversidad de dominios a los que se conecta), cada uno de 0 a 1."""
    neigh = adjacency.get(node, set())
    linked = {domains.get(x) for x in neigh if domains.get(x)}
    return (len(neigh) / maxdeg if maxdeg else 0.0, clustering_coefficient(node, adjacency),
            len(linked) / ndom_total if ndom_total else 0.0)


def structural_similarity(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return max(0.0, 1.0 - math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True))) / _SQRT3)


# --- curiosidad: huecos del grafo -------------------------------------------------------------------------------------
def find_gaps(notes: list[dict], min_citas: int = 1) -> dict:
    """`notes`: [{id, title, links}]. Faltantes = títulos citados con [[wikilink]] que no existen (los más pedidos
    primero); huérfanas = notas que nadie enlaza."""
    by_title = {n["title"].strip().lower(): n["id"] for n in notes}
    incoming: dict[str, int] = {n["id"]: 0 for n in notes}
    missing: dict[str, set[str]] = {}
    for n in notes:
        for lt in n.get("links", []):
            k = (lt or "").strip().lower()
            if not k:
                continue
            tgt = by_title.get(k)
            if tgt is None:
                missing.setdefault(k, set()).add(n["id"])
            elif tgt != n["id"]:
                incoming[tgt] += 1
    faltantes = [{"tipo": "falta_nota", "titulo": t, "citada_por": len(ids)} for t, ids in missing.items()
                 if len(ids) >= min_citas]
    faltantes.sort(key=lambda d: (-d["citada_por"], d["titulo"]))
    huerfanas = [{"tipo": "huerfana", "id": n["id"], "titulo": n["title"]} for n in notes if incoming[n["id"]] == 0]
    return {"faltantes": faltantes, "huerfanas": huerfanas}


# --- clusters para consolidar ----------------------------------------------------------------------------------------
def components(adjacency: dict[str, set[str]]) -> list[set[str]]:
    seen: set[str] = set()
    comps: list[set[str]] = []
    for start in adjacency:
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            node = stack.pop()
            if node in comp:
                continue
            comp.add(node)
            seen.add(node)
            stack.extend(adjacency.get(node, set()) - comp)
        comps.append(comp)
    return comps


def cluster_from_pairs(pairs: list[tuple[str, str]], min_size: int = 2, max_size: int = 6) -> list[list[str]]:
    adj: dict[str, set[str]] = {}
    for a, b in pairs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    out = [sorted(c) for c in components(adj) if min_size <= len(c) <= max_size]
    return sorted(out, key=lambda c: (-len(c), c[0]))


def select_pairs(sims: dict[tuple[str, str], float], threshold: float, gap: float | None) -> list[tuple[str, str]]:
    """Qué pares de notas se consideran vecinas. Dos criterios y AMBOS tienen que cumplirse (arreglo del 12 nov, Ronda 2
    de Cerebro: un distractor sin relación puntuaba 0.74-0.77 contra notas que puntuaban 0.91 entre sí y con el umbral
    viejo de 0.6 se mezclaban temas en la conclusión):
      1. absoluto: coseno >= `threshold`.
      2. relativo: el par está a lo sumo `gap` por debajo de la MEJOR similitud de cualquiera de sus dos notas."""
    best: dict[str, float] = {}
    for (a, b), s in sims.items():
        best[a] = max(best.get(a, -1.0), s)
        best[b] = max(best.get(b, -1.0), s)
    out = []
    for (a, b), s in sims.items():
        if s < threshold:
            continue
        if gap is not None and s < max(best[a], best[b]) - gap:
            continue
        out.append((a, b))
    return out


def schema_fit(cluster: list[str], weights: dict[str, float]) -> float:
    """Cuán encajado en un esquema ya establecido está un cluster: el peso hebbiano promedio entre sus notas (1.0 =
    nada establecido, genuinamente nuevo: conviene dejarlo madurar)."""
    pairs = list(combinations(sorted(cluster), 2))
    if not pairs:
        return 1.0
    return sum(weights.get(f"{a}\t{b}", 1.0) for a, b in pairs) / len(pairs)


def evaluar_agrupamiento(sims: dict[tuple[str, str], float], grupos: list[list[str]], threshold: float,
                         gap: float | None) -> dict:
    """Qué tan bien agrupa (`threshold`, `gap`) contra una verdad etiquetada a mano: precisión (baja = mezcla temas),
    recall y F1 sobre PARES. La precisión es la que más importa."""
    juntos = {frozenset((a, b)) for g in grupos for i, a in enumerate(g) for b in g[i + 1:]}
    dichos = {frozenset(p) for p in select_pairs(sims, threshold, gap)}
    bien = len(dichos & juntos)
    precision = bien / len(dichos) if dichos else 1.0
    recall = bien / len(juntos) if juntos else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": threshold, "gap": gap, "pares_agrupados": len(dichos), "pares_esperados": len(juntos),
            "correctos": bien, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def barrer_umbrales(sims: dict[tuple[str, str], float], grupos: list[list[str]],
                    thresholds: tuple[float, ...] = (0.70, 0.75, 0.80, 0.85, 0.90),
                    gaps: tuple[float | None, ...] = (None, 0.04, 0.08, 0.12)) -> list[dict]:
    """Todas las combinaciones evaluadas, la mejor primero: precisión 1.0 antes que nada, después recall."""
    filas = [evaluar_agrupamiento(sims, grupos, t, g) for t in thresholds for g in gaps]
    return sorted(filas, key=lambda r: (-(r["precision"] >= 1.0), -r["recall"], -r["precision"], -r["threshold"]))
