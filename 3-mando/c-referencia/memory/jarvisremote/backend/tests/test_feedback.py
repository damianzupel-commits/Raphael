"""Tests del crédito por resultado (app/obsidian/feedback.py, Etapa B).

`reward_from_signals` es puro. `credit`/`outcome` se chequean con strength/hebbian
mockeados (no tocar disco)."""

from app.obsidian import feedback
from app.obsidian.feedback import reward_from_signals


def test_reward_codigo_tests():
    assert reward_from_signals({"tests_ok": True}, "codigo") == 1.0
    assert reward_from_signals({"tests_ok": False}, "codigo") == -1.0
    assert reward_from_signals({"had_error": True}, "codigo") == -0.5


def test_reward_conversacion_solo_explicito():
    # en conversación las señales implícitas NO cuentan; solo el feedback explícito
    assert reward_from_signals({"tests_ok": False, "had_error": True}, "conversacion") == 0.0
    assert reward_from_signals({"explicit": 1.5}, "conversacion") == 1.5


def test_reward_explicito_domina_y_clamp():
    # explícito + implícito se suman, clampado a [-1, 2]
    assert reward_from_signals({"explicit": 2.0, "tests_ok": True}, "codigo") == 2.0  # clamp a 2
    assert reward_from_signals({"explicit": -1.0, "tests_ok": False}, "codigo") == -1.0  # clamp a -1


def test_credit_positivo_y_negativo(monkeypatch):
    calls = {}
    monkeypatch.setattr(feedback.strength, "bump", lambda ids, increment: calls.__setitem__("inc", increment) or len(ids))
    monkeypatch.setattr(feedback.hebbian, "reforzar", lambda ids, amount: len(ids))
    monkeypatch.setattr(feedback.hebbian, "debilitar", lambda ids, amount: len(ids))
    pos = feedback.credit(["a", "b"], reward=1.0)
    assert pos["tipo"] == "refuerzo" and calls["inc"] > 0
    neg = feedback.credit(["a", "b"], reward=-1.0)
    assert neg["tipo"] == "aversion" and calls["inc"] < 0  # incremento NEGATIVO
    assert feedback.credit([], reward=1.0)["tipo"] == "nada"
    assert feedback.credit(["a"], reward=0)["tipo"] == "nada"
