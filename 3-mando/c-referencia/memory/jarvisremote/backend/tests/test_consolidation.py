"""Tests del core de consolidación (app/obsidian/consolidation.py, Fase 3).

`_components`, `_cluster_from_pairs` y `_consolidation_id` son puros -> se testean
con grafos sintéticos, sin tocar vault, embeddings ni LLM. `run_once` en dry-run se
verifica con fakes inyectados."""

import asyncio

from app.obsidian import consolidation
from app.obsidian.consolidation import _cluster_from_pairs, _components, _consolidation_id, schema_fit


def test_schema_fit_promedia_pesos_hebbianos():
    # cluster A,B,C con una arista reforzada (A-B=3.0) y las otras neutras (1.0)
    weights = {"A\tB": 3.0}
    fit = schema_fit(["A", "B", "C"], weights)
    # pares: A-B=3.0, A-C=1.0, B-C=1.0 -> promedio 5/3
    assert round(fit, 3) == round(5 / 3, 3)
    # cluster sin ningún refuerzo -> 1.0 (nada establecido, genuinamente nuevo)
    assert schema_fit(["X", "Y"], {}) == 1.0
    assert schema_fit(["solo"], {}) == 1.0


def test_components_separa_grupos():
    adj = {"A": {"B"}, "B": {"A"}, "C": {"D"}, "D": {"C"}, "E": set()}
    comps = sorted(sorted(c) for c in _components(adj))
    assert comps == [["A", "B"], ["C", "D"], ["E"]]


def test_cluster_filtra_por_tamano():
    # A-B-C forman un cluster de 3; D-E uno de 2; F solo (se descarta, min_size=2)
    pairs = [("A", "B"), ("B", "C"), ("D", "E")]
    clusters = _cluster_from_pairs(pairs, min_size=2, max_size=6)
    assert sorted(clusters) == [["A", "B", "C"], ["D", "E"]]


def test_cluster_descarta_demasiado_grandes():
    pairs = [("A", "B"), ("B", "C"), ("C", "D")]  # componente de 4
    assert _cluster_from_pairs(pairs, min_size=2, max_size=3) == []  # supera max_size


def test_consolidation_id_estable_e_independiente_del_orden():
    assert _consolidation_id(["A", "B", "C"]) == _consolidation_id(["C", "A", "B"])
    assert _consolidation_id(["A", "B"]) != _consolidation_id(["A", "C"])
    assert len(_consolidation_id(["A", "B"])) == 12


def test_run_once_dry_run_no_escribe(monkeypatch):
    class N:
        def __init__(self, i, t):
            self.id, self.title, self.content, self.updated = i, t, "x", "2026-10-05T00:00:00+00:00"

    notas = [N("n1", "Uno"), N("n2", "Dos")]
    monkeypatch.setattr(consolidation, "_recent_ids", lambda days: ["n1", "n2"])
    monkeypatch.setattr(consolidation, "find_clusters", lambda ids, th, **k: [["n1", "n2"]])
    monkeypatch.setattr(consolidation, "_existing_consolidation_ids", lambda: set())
    monkeypatch.setattr(consolidation.vault, "list_notes", lambda *a, **k: notas)
    escrito = {"n": 0}

    def fake_save(**kw):
        escrito["n"] += 1

    out = asyncio.run(consolidation.run_once(dry_run=True, save_note=fake_save, max_clusters=3))
    assert out["dry_run"] is True
    assert escrito["n"] == 0  # dry-run NO escribe
    assert out["a_consolidar"][0]["notas"] == ["Uno", "Dos"]
