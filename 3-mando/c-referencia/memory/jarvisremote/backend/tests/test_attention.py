"""Tests de la atención / separación de patrones (app/obsidian/attention.py). Puro."""

from app.obsidian.attention import mmr_order


def _cos(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def test_mmr_empuja_el_casi_duplicado_abajo():
    # B es casi idéntico a A (el #1); C es distinto. Con diversidad, C debe subir
    # por encima de B aunque B tenga mejor score que C.
    ranked = ["A", "B", "C"]
    scores = {"A": 1.0, "B": 0.9, "C": 0.7}
    vecs = {"A": [1.0, 0.0], "B": [0.99, 0.01], "C": [0.0, 1.0]}
    out = mmr_order(ranked, scores, vecs, _cos, lam=0.5)
    assert out[0] == "A"
    assert out.index("C") < out.index("B")  # el distinto antes que el casi-duplicado


def test_mmr_lam_alto_respeta_el_orden_de_score():
    ranked = ["A", "B", "C"]
    scores = {"A": 1.0, "B": 0.9, "C": 0.7}
    vecs = {"A": [1.0, 0.0], "B": [0.99, 0.01], "C": [0.0, 1.0]}
    out = mmr_order(ranked, scores, vecs, _cos, lam=1.0)  # solo relevancia
    assert out == ["A", "B", "C"]


def test_mmr_vacio_y_sin_vectores():
    assert mmr_order([], {}, {}, _cos) == []
    # sin vectores -> diversidad neutra, mantiene el orden de score
    out = mmr_order(["A", "B"], {"A": 1.0, "B": 0.5}, {}, _cos, lam=0.5)
    assert out == ["A", "B"]
