"""Tests del core de la representación sucesora (app/obsidian/successor.py, Fase 5).

`observe_sequence`, `observe_pairs`, `successor_scores` y `decay_all` son puros ->
se testean con dicts sintéticos, sin disco ni vault."""

from app.obsidian.successor import (
    decay_all,
    observe_pairs,
    observe_sequence,
    successor_scores,
)


def test_observe_sequence_dirigida():
    t = observe_sequence({}, ["A", "B", "C"])
    assert t == {"A": {"B": 1.0}, "B": {"C": 1.0}}
    # repetir refuerza, y es DIRIGIDA (A->B no implica B->A)
    t = observe_sequence(t, ["A", "B"])
    assert t["A"]["B"] == 2.0
    assert "A" not in t.get("B", {})


def test_observe_pairs_producto_sin_autopares():
    t = observe_pairs({}, ["A"], ["B", "C", "A"])
    assert t == {"A": {"B": 1.0, "C": 1.0}}  # A->A se ignora


def test_successor_scores_normaliza():
    t = {"A": {"B": 3.0, "C": 1.0}}
    s = successor_scores(t, ["A"])
    # prob condicional B=0.75, C=0.25; luego escalado por el máximo -> B=1.0, C=0.333
    assert s["B"] == 1.0
    assert round(s["C"], 3) == 0.333


def test_successor_scores_agrega_varios_origenes():
    t = {"A": {"X": 1.0}, "B": {"X": 1.0, "Y": 1.0}}
    s = successor_scores(t, ["A", "B"])
    # X recibe de A (1.0) y de B (0.5); Y solo de B (0.5) -> X es el más probable
    assert s["X"] > s["Y"]
    assert s["X"] == 1.0


def test_successor_scores_vacio():
    assert successor_scores({}, ["A"]) == {}
    assert successor_scores({"A": {"B": 1.0}}, ["Z"]) == {}


def test_decay_envejece_y_poda():
    t = {"A": {"B": 1.0, "C": 0.5}}
    d = decay_all(t, factor=0.5, floor=0.3)
    assert d["A"]["B"] == 0.5
    assert "C" not in d["A"]  # 0.5*0.5=0.25 < floor 0.3 -> podada


def test_top_limita():
    t = {"A": {"B": 5.0, "C": 3.0, "D": 1.0}}
    s = successor_scores(t, ["A"], top=2)
    assert set(s) == {"B", "C"}


def test_surprise(monkeypatch):
    from app.obsidian import successor
    monkeypatch.setattr(successor, "load", lambda: {"A": {"B": 9.0, "C": 1.0}})
    # sin foco anterior -> 0 (no hay expectativa)
    monkeypatch.setattr(successor, "_last_focus", [])
    assert successor.surprise(["B"]) == 0.0
    # foco anterior A: ir a B (muy esperado) -> poca sorpresa; ir a Z (no esperado) -> mucha
    monkeypatch.setattr(successor, "_last_focus", ["A"])
    assert successor.surprise(["B"]) < 0.2        # B era prob ~1.0 (normalizado) -> sorpresa ~0
    assert successor.surprise(["Z"]) == 1.0       # nunca se fue de A a Z -> sorpresa total


def test_surprise_sin_transiciones_es_moderada(monkeypatch):
    from app.obsidian import successor
    monkeypatch.setattr(successor, "load", lambda: {})
    monkeypatch.setattr(successor, "_last_focus", ["A"])
    assert successor.surprise(["B"]) == 0.5
