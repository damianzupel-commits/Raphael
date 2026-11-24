"""Composición de conceptos (vector-symbolic, v1) -- parte de la Fase 8 de la
estructura informacional (ver docs/SPEC-raphael-predictivo.md §4).

El recall normal trae lo parecido a UN concepto. La composición combina VARIOS en una
sola representación y trae lo que está en la INTERSECCIÓN/mezcla de todos — no lo
parecido a uno, sino a la combinación. Es el germen de "componer" ideas nuevas en vez
de solo recuperar las existentes.

v1 pragmática: se embeben los conceptos y se promedian componente a componente (un
binding simple en el espacio de embeddings); después se rankean las notas por cercanía a
ese vector compuesto. Un vector-symbolic de verdad (binding/unbinding con permutaciones o
productos) queda como investigación; esto ya captura el "y" conceptual de forma útil.

PROCESADOR: tier 0 + embeddings (nomic local). No toca el LLM de chat.
"""

from __future__ import annotations

from . import embeddings, vault


def compose(concepts: list[str], limit: int = 10) -> dict:
    """Trae las notas más cercanas a la COMBINACIÓN de `concepts` (promedio de sus
    embeddings). Read-only. Cae con gracia si no hay embeddings."""
    concepts = [c.strip() for c in concepts if c and c.strip()]
    if len(concepts) < 2:
        return {"mode": "error", "error": "pasá al menos 2 conceptos para componer", "resultados": []}

    vecs = []
    for c in concepts:
        v = embeddings.get_embedding(c)
        if v is not None:
            vecs.append(v)
    if not vecs:
        return {"mode": "sin-embeddings", "conceptos": concepts, "resultados": [],
                "nota": "no hay embeddings (¿LM Studio :1234 con el modelo cargado?)"}

    dim = len(vecs[0])
    vecs = [v for v in vecs if len(v) == dim]
    composite = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]

    index = embeddings.load_index()
    scored = []
    for note in vault.list_notes():
        v = index.get(note.id)
        if v is None or len(v) != dim:
            continue
        scored.append((embeddings.cosine_similarity(composite, v), note))
    scored.sort(key=lambda s: s[0], reverse=True)

    return {
        "mode": "composicion",
        "conceptos": concepts,
        "resultados": [
            {"id": n.id, "titulo": n.title, "afinidad": round(s, 3)}
            for s, n in scored[:limit]
        ],
    }
