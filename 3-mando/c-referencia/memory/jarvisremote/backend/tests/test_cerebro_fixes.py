"""Arreglos de la Ronda 2 de Cerebro (2026-11-12), sin modelo ni embeddings reales:
- la consolidación no agrupa un distractor que puntúa 0.74-0.77 contra notas que puntúan 0.91 entre sí;
- el prompt de Cerebro endurece la guarda anti-invención (dato real / admitir «no sé»)."""

from __future__ import annotations

from app.config import settings
from app.obsidian import consolidation
from brigades import cerebro

TH, GAP = 0.85, 0.08

# Escena real de la validación: 2 notas relacionadas (0.91 entre sí) + 1 distractor (0.74-0.77 contra ambas).
ESCENA = {("a", "b"): 0.91, ("a", "d"): 0.77, ("b", "d"): 0.74}


def test_defaults_endurecidos():
    assert settings.consolidation_similarity_threshold >= 0.85
    assert 0 < settings.consolidation_similarity_gap <= 0.1


def test_el_distractor_no_entra_al_grupo_con_los_defaults():
    pairs = consolidation.select_pairs(ESCENA, TH, GAP)
    assert pairs == [("a", "b")]
    assert consolidation._cluster_from_pairs(pairs) == [["a", "b"]]


def test_el_umbral_viejo_0_6_si_lo_mezclaba():  # documenta el bug que motivó el cambio
    pairs = consolidation.select_pairs(ESCENA, 0.6, None)
    assert len(consolidation._cluster_from_pairs(pairs)[0]) == 3


def test_la_brecha_sola_ya_separa_el_distractor_aunque_el_umbral_sea_flojo():
    pairs = consolidation.select_pairs(ESCENA, 0.6, GAP)
    assert pairs == [("a", "b")]


def test_comportamiento_normal_cadena_de_notas_realmente_parecidas_se_agrupa():
    # tres notas del mismo tema (0.93, 0.90, 0.88): el grupo de 3 se conserva
    sims = {("a", "b"): 0.93, ("b", "c"): 0.90, ("a", "c"): 0.88}
    assert len(consolidation._cluster_from_pairs(consolidation.select_pairs(sims, TH, GAP))[0]) == 3


def test_notas_aisladas_sin_pares_no_forman_cluster():
    sims = {("a", "b"): 0.5, ("b", "c"): 0.4, ("a", "c"): 0.3}
    assert consolidation.select_pairs(sims, TH, GAP) == []


def test_sin_dos_notas_no_hay_nada_que_romper():
    assert consolidation.select_pairs({}, TH, GAP) == []


def test_find_clusters_de_punta_a_punta_con_embeddings_falsos(monkeypatch):
    vecs = {"a": "A", "b": "B", "d": "D"}
    monkeypatch.setattr(consolidation.embeddings, "load_index", lambda: vecs)
    table = {frozenset(("A", "B")): 0.91, frozenset(("A", "D")): 0.77, frozenset(("B", "D")): 0.74}
    monkeypatch.setattr(consolidation.embeddings, "cosine_similarity", lambda x, y: table[frozenset((x, y))])
    assert consolidation.find_clusters(["a", "b", "d"], TH) == [["a", "b"]]  # gap por default de settings
    assert consolidation.find_clusters(["a", "b", "d"], 0.6, gap=999) == [["a", "b", "d"]]  # sin brecha, umbral flojo: el bug viejo


def test_prompt_de_cerebro_exige_el_dato_real_y_admitir_no_se():
    p = cerebro.CEREBRO_PROMPT
    assert "FIDELIDAD A LOS DATOS" in p
    assert "dato REAL" in p and "«no sé»" in p
    assert "No mezcles" in p  # tampoco mezclar notas de temas distintos
    assert "NO inventes" in p  # lo previo se conserva
    assert "SEGURIDAD (no negociable)" in p  # y la frontera instrucción-vs-dato también
