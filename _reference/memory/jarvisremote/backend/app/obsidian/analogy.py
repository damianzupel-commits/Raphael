"""Analogía / structure-mapping -- recuperación por correspondencia ESTRUCTURAL
(Fase 7 de la estructura informacional, ver docs/SPEC-raphael-predictivo.md §3).

Tesis (Hofstadter; Gentner): pensar no es medir similitud de contenido, es mapear la
ESTRUCTURA relacional de un dominio sobre otro. "X es a su dominio como Y es al suyo",
aunque X e Y no se parezcan en nada. De ahí salen las ideas nuevas (ej. conectoma ↔
Raphael: estructura que siembra función). Un coseno de embeddings nunca encuentra eso
-- justamente busca lo PARECIDO en contenido.

Este módulo busca, para una nota, sus ANÁLOGOS en OTROS dominios: notas que ocupan un
ROL estructural parecido en su propio barrio del grafo (grado, cómo de agrupado está su
vecindario, a cuántos dominios se conecta), preferentemente con contenido DISTINTO. El
grafo de wikilinks es no-tipado, así que esto es una v1 pragmática: aproxima el rol por
la forma local de la conectividad, no por relaciones tipadas.

PROCESADOR: tier 0 -- cómputo de grafo PURO para lo estructural; si hay embeddings, los
usa solo para premiar el contenido DISTINTO (analogía de verdad = misma forma, otra
materia). El core (`role_signature`, `signature_distance`, `clustering_coefficient`) es
puro y testeable con grafos sintéticos.
"""

from __future__ import annotations

import math

from . import embeddings, vault

_SQRT3 = math.sqrt(3.0)


# --- core PURO -------------------------------------------------------------------

def clustering_coefficient(node: str, adjacency: dict[str, set[str]]) -> float:
    """Fracción de los vecinos de `node` que están conectados entre sí (0..1). Mide
    cuán 'cerrado' es su barrio. Puro."""
    neigh = list(adjacency.get(node, set()))
    k = len(neigh)
    if k < 2:
        return 0.0
    links = 0
    for i in range(k):
        for j in range(i + 1, k):
            if neigh[j] in adjacency.get(neigh[i], set()):
                links += 1
    return links / (k * (k - 1) / 2)


def role_signature(node: str, adjacency: dict[str, set[str]], domains: dict[str, str], maxdeg: int, ndom_total: int) -> tuple[float, float, float]:
    """Firma estructural del ROL de un nodo, normalizada a 0..1 en cada eje:
    (grado relativo, coeficiente de agrupamiento, diversidad de dominios a los que
    se conecta). Puro."""
    neigh = adjacency.get(node, set())
    deg = len(neigh) / maxdeg if maxdeg else 0.0
    clus = clustering_coefficient(node, adjacency)
    linked_domains = {domains.get(x) for x in neigh if domains.get(x)}
    div = len(linked_domains) / ndom_total if ndom_total else 0.0
    return (deg, clus, div)


def signature_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Distancia euclidiana entre dos firmas (0 = idéntico rol estructural). Puro."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def structural_similarity(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """1 = mismo rol, 0 = roles opuestos. Puro."""
    return max(0.0, 1.0 - signature_distance(a, b) / _SQRT3)


# --- backed por el vault ---------------------------------------------------------

def _graph_maps():
    g = vault.build_graph()
    adj: dict[str, set[str]] = {}
    domains: dict[str, str] = {}
    for n in g.get("nodes", []):
        nid = n["id"]
        domains[nid] = nid.split("/", 1)[0]
        adj.setdefault(nid, set())
    for e in g.get("edges", []):
        adj.setdefault(e["source"], set()).add(e["target"])
        adj.setdefault(e["target"], set()).add(e["source"])
    return adj, domains


def find_analogies_for(note_id: str, limit: int = 8) -> list[dict]:
    """Análogos estructurales de `note_id` en OTROS dominios. Combina similitud de rol
    (estructura) con contenido DISTINTO (si hay embeddings). Devuelve la lista rankeada."""
    adj, domains = _graph_maps()
    if note_id not in domains:
        return []
    maxdeg = max((len(v) for v in adj.values()), default=1) or 1
    ndom = len(set(domains.values())) or 1
    sigs = {nid: role_signature(nid, adj, domains, maxdeg, ndom) for nid in domains}
    qsig = sigs[note_id]
    qdom = domains[note_id]

    index = embeddings.load_index()
    qvec = index.get(note_id)

    scored = []
    for nid, sig in sigs.items():
        if domains.get(nid) == qdom or nid == note_id:
            continue
        struct = structural_similarity(qsig, sig)
        if struct <= 0.0:
            continue
        combined = struct
        content_dist = None
        v = index.get(nid)
        if qvec is not None and v is not None:
            content_sim = embeddings.cosine_similarity(qvec, v)
            content_dist = round(1.0 - content_sim, 3)
            # analogía = misma forma, otra materia: premiamos contenido distinto
            combined = struct * (0.5 + 0.5 * (1.0 - content_sim))
        scored.append((combined, struct, content_dist, nid))

    scored.sort(reverse=True, key=lambda x: x[0])
    by_id = {n.id: n for n in vault.list_notes()}
    out = []
    for combined, struct, cdist, nid in scored[:limit]:
        n = by_id.get(nid)
        if n is None:
            continue
        out.append({
            "id": nid,
            "titulo": n.title,
            "dominio": domains.get(nid),
            "similitud_estructural": round(struct, 3),
            "distancia_contenido": cdist,
            "score": round(combined, 3),
        })
    return out


def resolve_note_id(query: str) -> str | None:
    """Encuentra el id de una nota por id exacto, por stem de archivo, o por título."""
    q = query.strip().lower()
    for n in vault.list_notes():
        if n.id.lower() == q or n.id.split("/")[-1].lower() == q or n.title.strip().lower() == q:
            return n.id
    # match parcial por título como último recurso
    for n in vault.list_notes():
        if q in n.title.strip().lower():
            return n.id
    return None
