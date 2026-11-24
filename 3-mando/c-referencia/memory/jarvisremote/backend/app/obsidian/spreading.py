"""Spreading activation sobre el grafo del vault (Fase 1 de la estructura
informacional cerebro-símil -- ver docs/SPEC-estructura-informacional-cerebro.md).

Recuperación por ASOCIACIÓN en vez de solo por lista (top-k coseno). Modelo de
redes semánticas de Collins & Loftus (1975): una consulta activa nodos semilla
(por similitud de embedding) y la activación se PROPAGA por los wikilinks a los
vecinos, atenuándose con la distancia (decay). Un nodo alcanzado desde varias
semillas SUMA activación -- esa convergencia es lo que hace emerger lo relevante
"que no matcheaba literal pero está conectado".

PROCESADOR: tier 0 -- cómputo de grafo PURO, NO toca ningún LLM. Solo reusa el
modelo de embeddings (para las semillas) que ya está separado. Determinista,
instantáneo, gratis.

El core (`propagate`) es una función pura (semillas + adyacencia -> activación),
testeable con grafos sintéticos sin tocar el vault real.
"""

from __future__ import annotations

from collections import defaultdict

from . import activation_trace, attention, confidence, embeddings, hebbian, strength, successor, vault

# Peso del empujón anticipatorio (Fase 5): cuánto suma al ranking la predicción de
# sucesor de una nota. Moderado: orienta, no domina a la activación asociativa.
_ANTICIP_WEIGHT = 0.5


def propagate(
    seeds: dict[str, float],
    adjacency: dict[str, set[str]],
    hops: int = 2,
    decay: float = 0.5,
    edge_weights: dict[tuple[str, str], float] | None = None,
) -> dict[str, float]:
    """Difunde la activación de las semillas por el grafo.

    - `seeds`: nodo -> activación inicial (ej. coseno de la semilla).
    - `adjacency`: nodo -> set de vecinos (grafo no dirigido).
    - `hops`: cuántos saltos propaga (1-2 es lo normal).
    - `decay`: atenuación por salto (0.5 = cada salto vale la mitad).
    - `edge_weights`: opcional (Fase 2, Hebbian) -- peso por arista (clave = tupla
      ordenada de los dos nodos). Si se pasa, el factor de un salto es
      `decay * peso(arista)` en vez de `decay` plano.

    Devuelve nodo -> activación total ACUMULADA (semilla + todo lo propagado).
    La activación fluye en ambos sentidos por cada arista (grafo no dirigido), así
    que un nodo puede recibir algo de retorno de sus propios vecinos en saltos
    posteriores -- eso es esperado y la semilla igual queda como la más activada.
    El `decay < 1` garantiza que el aporte se achica cada salto y no diverge."""
    activation: dict[str, float] = defaultdict(float)
    for node, a in seeds.items():
        activation[node] += a

    frontier = dict(seeds)  # lo que se activó en el salto anterior
    for _ in range(max(0, hops)):
        contrib: dict[str, float] = defaultdict(float)
        for node, act in frontier.items():
            for nb in adjacency.get(node, ()):  # vecinos
                w = decay
                if edge_weights is not None:
                    key = (node, nb) if node < nb else (nb, node)
                    w = decay * edge_weights.get(key, 1.0)
                contrib[nb] += act * w
        if not contrib:
            break
        for nb, c in contrib.items():
            activation[nb] += c  # ACUMULA (convergencia desde varias semillas)
        frontier = contrib

    return dict(activation)


def _adjacency_from_graph() -> dict[str, set[str]]:
    """Adyacencia no dirigida a partir de `vault.build_graph()` (edges = wikilinks)."""
    g = vault.build_graph()
    adj: dict[str, set[str]] = defaultdict(set)
    for e in g.get("edges", []):
        s, t = e["source"], e["target"]
        adj[s].add(t)
        adj[t].add(s)
    return adj


def _seed_activation(query: str, seed_k: int, min_seed: float) -> dict[str, float] | None:
    """Semillas = las `seed_k` notas con mayor coseno contra la query (por encima de
    `min_seed`). None si no hay embeddings (no se puede hacer spreading sin semillas)."""
    qv = embeddings.get_embedding(query)
    if qv is None:
        return None
    index = embeddings.load_index()
    if not index:
        return None
    scored: list[tuple[float, str]] = []
    for note in vault.list_notes():
        v = index.get(note.id)
        if v is None:
            continue
        s = embeddings.cosine_similarity(qv, v)
        if s >= min_seed:
            scored.append((s, note.id))
    scored.sort(reverse=True)
    return {nid: s for s, nid in scored[:seed_k]}


_EXTRACTO_CHARS = 380


def extracto_relevante(content: str, query: str, max_chars: int = _EXTRACTO_CHARS) -> str:
    """Las oraciones de `content` que más tienen que ver con `query`, COPIADAS tal cual y en su orden original (nunca un
    resumen: cifras, nombres y fechas quedan como están). Puro y determinista: cuenta términos de la consulta (sin acentos,
    de 4+ letras) por oración; si ninguna oración matchea, el comienzo de la nota. Acotado a `max_chars`."""
    import re
    import unicodedata

    def norm(t: str) -> str:
        t = unicodedata.normalize("NFD", t or "")
        return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()

    texto = " ".join((content or "").split())
    if len(texto) <= max_chars:
        return texto
    terminos = {w for w in re.findall(r"[a-z0-9ñ]{4,}", norm(query))}
    oraciones = [o for o in re.split(r"(?<=[.!?…])\s+", texto) if o]
    puntajes = [sum(1 for t in terminos if t in norm(o)) for o in oraciones]
    if not terminos or max(puntajes, default=0) == 0:
        return texto[: max_chars - 1].rstrip() + "…"
    elegidas: set[int] = set()
    usado = 0
    for i in sorted(range(len(oraciones)), key=lambda k: (-puntajes[k], k)):
        if puntajes[i] == 0 or usado + len(oraciones[i]) + 1 > max_chars:
            continue
        elegidas.add(i)
        usado += len(oraciones[i]) + 1
    if not elegidas:  # la mejor oración sola ya no entra: se recorta
        mejor = max(range(len(oraciones)), key=lambda k: puntajes[k])
        return oraciones[mejor][: max_chars - 1].rstrip() + "…"
    return " ".join(oraciones[i] for i in sorted(elegidas))


def search_spreading(
    query: str,
    limit: int = 10,
    hops: int = 2,
    decay: float = 0.5,
    seed_k: int = 10,
    min_seed: float = 0.30,
    usar_pesos: bool = True,
    usar_fuerza: bool = True,
    anticipar: bool = False,
    diversificar: bool = False,
    reforzar: bool = False,
    extractos: bool = False,
) -> dict:
    """Recupera notas por activación propagada. Devuelve un dict con las notas
    rankeadas por activación total + metadatos (cuáles fueron semilla vs llegaron
    por asociación). Si no hay embeddings, cae a la búsqueda normal del vault.

    - `usar_pesos` (Fase 2): si hay pesos Hebbianos guardados, la propagación va
      más fuerte por las aristas que se usaron juntas (grafo auto-organizado).
    - `usar_fuerza` (Fase 4): si está, el ranking se multiplica por la fuerza de
      recuperación de cada nota (sube lo usado hace poco, decae lo que no se toca;
      ver [[strength]]). Nunca entierra una nota por debajo de lo neutro.
    - `reforzar` (Fase 2+4): si es True, al terminar refuerza las aristas entre las
      notas devueltas Y la fuerza de recuperación de cada una ("se activaron juntas
      -> se cablean juntas" + "se usó -> se refuerza", reconsolidación §3.5). Pasalo
      en True SOLO cuando esas notas se van a usar de verdad, no por explorar.

    Es READ-ONLY salvo que `reforzar=True` (que solo toca los JSON de pesos/fuerza,
    nunca las notas) y tier 0: no llama a ningún LLM."""
    seeds = _seed_activation(query, seed_k, min_seed)
    if seeds is None:
        # sin embeddings no hay semillas -> fallback a la búsqueda de siempre
        notas = vault.search_notes(query, limit=limit)
        # rastro plano: los hits bajan de nivel por posición
        activation_trace.record(
            query, "keyword",
            {n.id: round(max(0.3, 1.0 - i * 0.12), 3) for i, n in enumerate(notas)},
        )
        return {
            "mode": "fallback-keyword",
            "query": query,
            "resultados": [{"id": n.id, "titulo": n.title, "activacion": None, "origen": "keyword",
                            **({"extracto": extracto_relevante(n.content, query)} if extractos else {})} for n in notas],
        }

    adj = _adjacency_from_graph()
    edge_weights = hebbian.as_propagate_weights(hebbian.load_weights()) if usar_pesos else None
    activation = propagate(seeds, adj, hops=hops, decay=decay, edge_weights=edge_weights)

    # Fase 4: pondera la activación por la fuerza de recuperación (olvido adaptativo).
    fuerzas = strength.factors_for(list(activation)) if usar_fuerza else {}
    scored = {nid: act * fuerzas.get(nid, 1.0) for nid, act in activation.items()}

    # Fase 5: predicción anticipatoria. Suma al ranking los SUCESORES probables del
    # foco actual (las semillas) -- incluso notas que la asociación no activó, si es
    # probable que sigan en el hilo. Pre-carga "a dónde solés ir después".
    prediccion = successor.predict(list(seeds)) if anticipar else {}
    for nid, p in prediccion.items():
        scored[nid] = scored.get(nid, 0.0) + p * _ANTICIP_WEIGHT

    by_id = {n.id: n for n in vault.list_notes()}
    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    max_score = ranked[0][1] if ranked else 0.0

    # Atención / separación de patrones: diversifica el orden (MMR) para no traer
    # casi-duplicados -- un subconjunto enfocado Y distinto, no 5 copias de lo mismo.
    cand_ids = [nid for nid, _ in ranked]
    if diversificar and cand_ids:
        cand_ids = attention.mmr_order(cand_ids, scored, embeddings.load_index(), embeddings.cosine_similarity)

    resultados = []
    for nid in cand_ids[:limit]:
        n = by_id.get(nid)
        if n is None:
            continue
        score = scored.get(nid, 0.0)
        if nid in seeds:
            origen = "semilla"
        elif activation.get(nid, 0.0) > 0.0:
            origen = "asociacion"
        else:
            origen = "anticipacion"
        resultados.append({
            "id": nid,
            "titulo": n.title,
            "activacion": round(activation.get(nid, 0.0), 4),
            "score": round(score, 4),
            "fuerza": round(fuerzas.get(nid, 1.0), 3),
            "prediccion": round(prediccion.get(nid, 0.0), 3),
            "confianza": confidence.note_confidence(score, max_score, nid in seeds, fuerzas.get(nid, 1.0)),
            "origen": origen,
            # Evidencia estructurada (O-3): el TEXTO de la nota que responde la consulta, tal cual está escrito. Con esto quien
            # busca (el recuperador de Cerebro) no necesita una segunda búsqueda para leer las notas que encontró.
            **({"extracto": extracto_relevante(n.content, query)} if extractos else {}),
        })

    # Metacognición (Fase 9): confianza del recall entero + recomendación de acción.
    conf_global = confidence.overall_confidence([s for _, s in ranked], list(seeds.values()))
    reco = confidence.recommendation(conf_global)

    # rastro de activación para la UI (nivel = activación normalizada por el máximo)
    if activation:
        mx = max(activation.values()) or 1.0
        activation_trace.record(
            query, "spreading",
            {nid: a / mx for nid, a in activation.items() if a / mx > 0.05},
        )

    reforzadas = 0
    reforzadas_fuerza = 0
    transiciones = 0
    sorpresa = 0.0
    if reforzar and resultados:
        ids = [r["id"] for r in resultados]
        # Fase 6: la SORPRESA (error de predicción) escala la codificación -- lo que NO
        # se esperaba se graba más fuerte que lo repetido. Se mide ANTES de aprender.
        sorpresa = successor.surprise([resultados[0]["id"]])
        reforzadas = hebbian.reforzar(ids)
        reforzadas_fuerza = strength.bump(ids, increment=0.5 * (1.0 + sorpresa))
        # Fase 5: aprende el paso de pensamiento (foco anterior -> esta nota top).
        transiciones = successor.step([resultados[0]["id"]])

    proximas = []
    if anticipar and prediccion:
        for nid, p in sorted(prediccion.items(), key=lambda kv: kv[1], reverse=True)[:5]:
            n = by_id.get(nid)
            if n is not None:
                proximas.append({"id": nid, "titulo": n.title, "prob": round(p, 3)})

    return {
        "mode": "spreading",
        "query": query,
        "hops": hops,
        "decay": decay,
        "n_semillas": len(seeds),
        "pesos_hebbianos": bool(edge_weights),
        "fuerza_recuperacion": bool(fuerzas),
        "confianza_global": conf_global,
        "recomendacion": reco,
        "anticipatorio": bool(prediccion),
        "proximas_probables": proximas,
        "aristas_reforzadas": reforzadas,
        "notas_reforzadas": reforzadas_fuerza,
        "transiciones_aprendidas": transiciones,
        "sorpresa": sorpresa,
        "resultados": resultados,
    }
