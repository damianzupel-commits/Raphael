"""Tests del core Hebbiano (app/obsidian/hebbian.py, Fase 2 de la estructura
informacional cerebro-símil).

`bump` y `as_propagate_weights` son funciones PURAS (no tocan disco ni el vault),
así que se testean solas. Además se verifica que los pesos efectivamente amplifican
la propagación del spreading activation (Fase 1 + Fase 2 integradas).
"""

from app.obsidian.hebbian import as_propagate_weights, bump
from app.obsidian.spreading import propagate


def test_bump_crea_y_sube_aristas():
    w = bump({}, ["A", "B"], amount=0.5)
    # arista nueva: parte del neutro 1.0 y sube 0.5
    assert w["A\tB"] == 1.5
    # reforzar de nuevo vuelve a subir
    w = bump(w, ["A", "B"], amount=0.5)
    assert w["A\tB"] == 2.0


def test_bump_todas_las_parejas_y_clave_canonica():
    w = bump({}, ["C", "A", "B"])  # 3 nodos -> 3 aristas, ids desordenados
    assert set(w) == {"A\tB", "A\tC", "B\tC"}  # claves ordenadas, no dirigidas
    # pasar los ids al revés cae en la MISMA arista (no se duplica)
    w2 = bump({}, ["B", "A"])
    assert list(w2) == ["A\tB"]


def test_bump_ignora_autopares_y_repetidos():
    assert bump({}, ["A"]) == {}          # un solo nodo: nada que cablear
    assert bump({}, ["A", "A"]) == {}     # repetido: no hay par real
    assert bump({}, []) == {}


def test_bump_topea_en_cap():
    w = {}
    for _ in range(100):
        w = bump(w, ["A", "B"], amount=0.5, cap=5.0)
    assert w["A\tB"] == 5.0  # satura, no crece infinito


def test_as_propagate_weights_formato_tupla():
    assert as_propagate_weights({"A\tB": 2.0}) == {("A", "B"): 2.0}
    assert as_propagate_weights({"basura-sin-sep": 3.0}) == {}  # tolerante a ruido


def test_pesos_amplifican_la_propagacion():
    # grafo A-B; con la arista reforzada, B recibe más activación desde A.
    adj = {"A": {"B"}, "B": {"A"}}
    pesos = as_propagate_weights(bump({}, ["A", "B"], amount=1.0))  # peso 2.0
    base = propagate({"A": 1.0}, adj, hops=1, decay=0.5)
    reforzado = propagate({"A": 1.0}, adj, hops=1, decay=0.5, edge_weights=pesos)
    assert reforzado["B"] > base["B"]
    assert round(reforzado["B"], 4) == 1.0  # 1.0 * 0.5 * 2.0
