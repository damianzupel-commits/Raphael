"""Cómputo de grafo puro, con grafos sintéticos (sin vault ni embeddings). Incluye la regresión de la Ronda 2 de Cerebro."""

from __future__ import annotations

import pytest

from raphael_memoria import graph
from raphael_memoria.embeddings import cosine
from raphael_memoria.learning import as_propagate_weights, bump


def adj(*pairs):
    return graph.adjacency_from_edges([{"source": a, "target": b} for a, b in pairs])


# --- propagación ---
def test_la_activacion_se_propaga_y_se_atenua_por_salto():
    out = graph.propagate({"a": 1.0}, adj(("a", "b"), ("b", "c"), ("c", "d")), hops=2, decay=0.5)
    assert out["b"] == pytest.approx(0.5) and out["c"] == pytest.approx(0.25)
    assert out["a"] == pytest.approx(1.25)                  # la activación también rebota hacia la semilla
    assert "d" not in out                                   # 3 saltos: no llega con hops=2


def test_la_convergencia_desde_varias_semillas_suma():
    out = graph.propagate({"a": 1.0, "c": 1.0}, adj(("a", "b"), ("c", "b")), hops=1, decay=0.5)
    assert out["b"] == pytest.approx(1.0)                   # 0.5 + 0.5: el nodo del medio converge


def test_hops_cero_deja_solo_las_semillas_y_sin_vecinos_no_rompe():
    assert graph.propagate({"a": 0.7}, {}, hops=0) == {"a": 0.7}
    assert graph.propagate({"a": 0.7}, {}, hops=3) == {"a": 0.7}


def test_los_pesos_hebbianos_refuerzan_la_via_usada():
    g = adj(("a", "b"), ("a", "c"))
    w = as_propagate_weights(bump({}, ["a", "b"], 1.0))
    out = graph.propagate({"a": 1.0}, g, hops=1, decay=0.5, edge_weights=w)
    assert out["b"] > out["c"] and out["c"] == pytest.approx(0.5)


def test_con_decay_menor_a_1_no_diverge_aunque_haya_ciclos():
    out = graph.propagate({"a": 1.0}, adj(("a", "b"), ("b", "c"), ("c", "a")), hops=10, decay=0.5)
    assert all(v < 10 for v in out.values())


# --- MMR ---
def test_mmr_baja_a_los_casi_duplicados():
    vecs = {"a": [1, 0], "a2": [0.99, 0.01], "b": [0, 1]}
    scores = {"a": 1.0, "a2": 0.95, "b": 0.7}
    order = graph.mmr_order(["a", "a2", "b"], scores, vecs, cosine, lam=0.5)
    assert order[0] == "a" and order[1] == "b"              # la copia casi igual queda detrás de lo distinto


def test_mmr_sin_vectores_conserva_el_orden_y_vacio_es_vacio():
    assert graph.mmr_order(["x", "y", "z"], {"x": 3, "y": 2, "z": 1}, {}, cosine) == ["x", "y", "z"]
    assert graph.mmr_order([], {}, {}, cosine) == []


# --- confianza ---
def test_confianza_sale_del_proceso_no_de_un_modelo():
    assert graph.note_confidence(1.0, 1.0, True) == 1.0
    assert graph.note_confidence(1.0, 1.0, False) < 1.0              # una asociación de rebote vale menos que una semilla
    assert graph.note_confidence(0.0, 0.0, True) == 0.0
    claro = graph.overall_confidence([1.0, 0.2], [0.9])
    parejo = graph.overall_confidence([1.0, 0.98], [0.9])
    assert claro > parejo and graph.overall_confidence([], []) == 0.0


@pytest.mark.parametrize("c,r", [(0.9, "alta"), (0.5, "media"), (0.1, "baja"), (0.6, "alta"), (0.35, "baja")])
def test_recomendacion(c, r):
    assert graph.recommendation(c) == r


# --- analogía ---
def test_firma_estructural_y_agrupamiento():
    g = adj(("h", "a"), ("h", "b"), ("a", "b"), ("h", "c"))
    assert graph.clustering_coefficient("h", g) == pytest.approx(1 / 3)
    assert graph.clustering_coefficient("c", g) == 0.0
    doms = {"h": "x", "a": "y", "b": "y", "c": "z"}
    sig = graph.role_signature("h", g, doms, maxdeg=3, ndom_total=3)
    assert sig[0] == 1.0 and sig[2] == pytest.approx(2 / 3)
    assert graph.structural_similarity(sig, sig) == 1.0 and graph.structural_similarity((0, 0, 0), (1, 1, 1)) == 0.0


# --- curiosidad ---
def test_huecos_faltantes_ordenados_por_pedidos_y_huerfanas():
    notes = [{"id": "1", "title": "Uno", "links": ["Dos", "Falta X", "Falta Y"]},
             {"id": "2", "title": "Dos", "links": ["Falta X", "Uno", ""]},
             {"id": "3", "title": "Sola", "links": []}]
    gaps = graph.find_gaps(notes)
    assert [f["titulo"] for f in gaps["faltantes"]] == ["falta x", "falta y"] and gaps["faltantes"][0]["citada_por"] == 2
    assert [h["id"] for h in gaps["huerfanas"]] == ["3"]
    assert graph.find_gaps(notes, min_citas=2)["faltantes"][0]["titulo"] == "falta x"
    assert len(graph.find_gaps(notes, min_citas=2)["faltantes"]) == 1


# --- clusters: regresión de la Ronda 2 (12 nov) ---
TH, GAP = 0.85, 0.08
ESCENA = {("a", "b"): 0.91, ("a", "d"): 0.77, ("b", "d"): 0.74}    # 2 notas relacionadas + 1 distractor


def test_el_distractor_no_entra_al_grupo_con_los_defaults():
    pairs = graph.select_pairs(ESCENA, TH, GAP)
    assert pairs == [("a", "b")] and graph.cluster_from_pairs(pairs) == [["a", "b"]]


def test_el_umbral_viejo_0_6_si_lo_mezclaba():          # documenta el bug que motivó el cambio
    assert len(graph.cluster_from_pairs(graph.select_pairs(ESCENA, 0.6, None))[0]) == 3


def test_la_brecha_sola_separa_el_distractor_aunque_el_umbral_sea_flojo():
    assert graph.select_pairs(ESCENA, 0.6, GAP) == [("a", "b")]


def test_una_cadena_de_notas_realmente_parecidas_se_agrupa():
    sims = {("a", "b"): 0.93, ("b", "c"): 0.90, ("a", "c"): 0.88}
    assert len(graph.cluster_from_pairs(graph.select_pairs(sims, TH, GAP))[0]) == 3


def test_notas_aisladas_y_vacio_no_forman_cluster():
    assert graph.select_pairs({("a", "b"): 0.5, ("b", "c"): 0.4, ("a", "c"): 0.3}, TH, GAP) == []
    assert graph.select_pairs({}, TH, GAP) == [] and graph.cluster_from_pairs([]) == []


def test_los_clusters_respetan_el_tamano_maximo():
    pairs = [(f"n{i}", f"n{i + 1}") for i in range(8)]                # una cadena de 9
    assert graph.cluster_from_pairs(pairs, 2, 6) == [] and len(graph.cluster_from_pairs(pairs, 2, 9)[0]) == 9


def test_calibrar_umbral_y_brecha_contra_una_verdad_etiquetada():
    grupos = [["a", "b"]]
    mal = graph.evaluar_agrupamiento(ESCENA, grupos, 0.6, None)
    bien = graph.evaluar_agrupamiento(ESCENA, grupos, TH, GAP)
    assert mal["precision"] < 1.0 and bien["precision"] == 1.0 and bien["recall"] == 1.0 and bien["f1"] == 1.0
    mejor = graph.barrer_umbrales(ESCENA, grupos)[0]
    assert mejor["precision"] == 1.0 and mejor["recall"] == 1.0


def test_schema_fit_distingue_lo_establecido_de_lo_nuevo():
    assert graph.schema_fit(["a", "b"], {}) == 1.0 and graph.schema_fit(["a"], {}) == 1.0
    assert graph.schema_fit(["a", "b"], {"a\tb": 3.0}) == 3.0
