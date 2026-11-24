"""Tests del rastro de activación (app/obsidian/activation_trace.py)."""

from app.obsidian import activation_trace


def test_record_y_latest():
    activation_trace.record("auditar repo", "spreading", {"n1": 1.0, "n2": 0.42})
    l = activation_trace.latest()
    assert l["mode"] == "spreading"
    assert l["query"] == "auditar repo"
    assert l["nodes"] == {"n1": 1.0, "n2": 0.42}
    assert l["seq"] >= 1
    assert l["ts"] > 0


def test_seq_incrementa_y_ultimo_gana():
    a = activation_trace.latest()["seq"]
    activation_trace.record("q", "keyword", {"x": 0.9})
    b = activation_trace.latest()
    assert b["seq"] == a + 1
    assert b["nodes"] == {"x": 0.9}
    assert b["mode"] == "keyword"


def test_niveles_redondeados():
    activation_trace.record("q", "spreading", {"n": 0.123456})
    assert activation_trace.latest()["nodes"]["n"] == 0.123
