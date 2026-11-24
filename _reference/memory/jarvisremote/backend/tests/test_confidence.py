"""Tests de la metacognición/confianza (app/obsidian/confidence.py, Fase 9). Todo puro."""

from app.obsidian.confidence import note_confidence, overall_confidence, recommendation


def test_note_confidence():
    # score == max, semilla, fuerza neutra -> 1.0
    assert note_confidence(1.0, 1.0, True, 1.0) == 1.0
    # una asociación de rebote vale 0.75 de lo que valdría como semilla
    assert note_confidence(1.0, 1.0, False, 1.0) == 0.75
    # score bajo -> confianza baja
    assert note_confidence(0.2, 1.0, True, 1.0) < 0.3


def test_overall_confidence_ganador_claro_vs_parejo():
    # ganador clarísimo + semilla fuerte -> confianza alta
    alta = overall_confidence([1.0, 0.1, 0.05], [0.8])
    # todo parejo + semilla floja -> confianza baja
    baja = overall_confidence([0.5, 0.49, 0.48], [0.31])
    assert alta > baja
    assert alta >= 0.6
    assert baja <= 0.45


def test_overall_confidence_vacio():
    assert overall_confidence([], [0.8]) == 0.0


def test_recommendation():
    assert recommendation(0.9) == "alta"
    assert recommendation(0.5) == "media"
    assert recommendation(0.2) == "baja"
