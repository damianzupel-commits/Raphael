"""Aprendizaje del uso: Hebb, fuerza de recuperación (olvido adaptativo), sucesión (predicción) y crédito por resultado."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from raphael_core.store import Store

from raphael_memoria import learning as L

T0 = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)


# --- Hebb ---
def test_hebb_refuerza_con_tope_y_es_simetrico_y_puro():
    w = {}
    for _ in range(20):
        w = L.bump(w, ["b", "a"])
    assert w == {"a\tb": L.CAP} and L.bump({}, ["a", "a", ""]) == {}           # auto-pares y vacíos se ignoran
    base = {"a\tb": 1.0}
    L.bump(base, ["a", "b"])
    assert base == {"a\tb": 1.0}                                               # no muta el original


def test_ltd_debilita_con_piso_y_nunca_borra():
    w = {}
    for _ in range(10):
        w = L.weaken(w, ["a", "b"])
    assert w["a\tb"] == L.FLOOR


def test_pesos_como_tuplas_ordenadas():
    assert L.as_propagate_weights({"a\tb": 2.0, "malformada": 1.0}) == {("a", "b"): 2.0}


# --- fuerza ---
def test_el_boost_decae_a_la_mitad_cada_14_dias_y_conserva_el_signo():
    assert L.effective_boost(1.0, T0.isoformat(), T0 + timedelta(days=14)) == pytest.approx(0.5)
    assert L.effective_boost(-1.0, T0.isoformat(), T0 + timedelta(days=28)) == pytest.approx(-0.25)
    assert L.effective_boost(0.0, "", T0) == 0.0 and L.effective_boost(1.0, "no-es-fecha", T0) == 1.0


def test_el_factor_nunca_baja_del_piso_y_sube_con_el_uso():
    assert L.factor(-5.0, T0.isoformat(), T0) == L.FLOOR_FACTOR
    e = L.bump_entry(None, T0)
    assert L.factor(e["boost"], e["last_used"], T0) == pytest.approx(1.5)
    for _ in range(10):
        e = L.bump_entry(e, T0)
    assert e["boost"] == L.BOOST_CAP


def test_lo_que_no_se_toca_vuelve_a_neutro_pero_nunca_se_entierra_lo_nuevo():
    s = L.LearningStore(Store().space("m"), lambda: T0)
    assert s.factors_for(["nueva"]) == {"nueva": 1.0}
    s.strengthen(["a"])
    s._now = lambda: T0 + timedelta(days=140)
    assert 1.0 <= s.factors_for(["a"])["a"] < 1.01


# --- sucesión ---
def test_prediccion_de_sucesores_y_envejecimiento():
    t = L.observe_pairs({}, ["a"], ["b"])
    t = L.observe_pairs(t, ["a"], ["b"])
    t = L.observe_pairs(t, ["a"], ["c"])
    sc = L.successor_scores(t, ["a"])
    assert sc["b"] == 1.0 and sc["c"] == pytest.approx(0.5) and L.successor_scores(t, ["zzz"]) == {}
    assert L.successor_scores(t, ["a"], top=1) == {"b": 1.0}
    assert "a" not in L.decay_all({"a": {"b": 0.05}}, 0.5)


def test_sorpresa_es_el_error_de_prediccion():
    t = L.observe_pairs({}, ["a"], ["b"])
    assert L.surprise_of(t, [], ["b"]) == 0.0                 # sin foco previo no hay expectativa
    assert L.surprise_of(t, ["a"], ["b"]) == 0.0              # lo esperado
    assert L.surprise_of(t, ["a"], ["z"]) == 1.0              # lo inesperado
    assert L.surprise_of({}, ["a"], ["z"]) == 0.5             # foco sin expectativas formadas


def test_el_paso_de_pensamiento_aprende_foco_anterior_a_foco_actual():
    s = L.LearningStore(Store().space("m"), lambda: T0)
    assert s.step(["a"]) == 0           # el primer foco no tiene anterior
    assert s.step(["b"]) == 1
    assert s.predict(["a"]) == {"b": 1.0} and s.last_focus() == ["b"]


# --- crédito ---
def test_reward_explicito_pesa_y_las_senales_implicitas_solo_en_situaciones_objetivas():
    assert L.reward_from_signals({"explicit": 1}, "conversacion") == 1.0
    assert L.reward_from_signals({"tests_ok": True}, "conversacion") == 0.0
    assert L.reward_from_signals({"tests_ok": True}, "codigo") == 1.0
    assert L.reward_from_signals({"tests_ok": False, "had_error": True, "corrected": True}, "codigo") == -1.0
    assert L.reward_from_signals({"explicit": 9}, "recall") == 2.0 and L.reward_from_signals({}, "recall") == 0.0


def test_credito_positivo_refuerza_y_negativo_marca_aversion_con_pisos():
    s = L.LearningStore(Store().space("m"), lambda: T0)
    r = s.credit(["a", "b"], 1.0)
    assert r["tipo"] == "refuerzo" and r["notas"] == 2 and r["aristas"] == 1 and s.weights()["a\tb"] > 1.0
    for _ in range(10):
        r = s.credit(["a", "b"], -1.0)
    assert r["tipo"] == "aversion" and s.weights()["a\tb"] == L.FLOOR
    assert all(f >= L.FLOOR_FACTOR for f in s.factors_for(["a", "b"]).values())
    assert s.credit(["a"], 0)["tipo"] == "nada" and s.credit([], 1)["tipo"] == "nada"


def test_outcome_cierra_el_lazo():
    s = L.LearningStore(Store().space("m"), lambda: T0)
    out = s.outcome(["a", "b"], {"tests_ok": False}, "codigo")
    assert out["tipo"] == "aversion" and out["situacion"] == "codigo"
