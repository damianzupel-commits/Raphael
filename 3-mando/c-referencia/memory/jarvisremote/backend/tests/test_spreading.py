"""Tests del core de spreading activation (app/obsidian/spreading.py, Fase 1 de
la estructura informacional cerebro-símil).

`propagate` es una función PURA (semillas + adyacencia -> activación), así que se
testea con grafos sintéticos sin tocar el vault real, embeddings ni ningún modelo.
Verifica las tres propiedades que tienen que cumplirse:
  1. Decaimiento por distancia (cada salto vale menos).
  2. Convergencia: un nodo alcanzado desde varias semillas SUMA activación.
  3. Pesos Hebbianos (Fase 2): una arista con peso amplifica la propagación.
"""

from app.obsidian.spreading import propagate


def test_decaimiento_por_distancia():
    # Cadena A - B - C - D. Semilla en A, hops=2. La activación decae con la distancia.
    adj = {"A": {"B"}, "B": {"A", "C"}, "C": {"B", "D"}, "D": {"C"}}
    act = propagate({"A": 1.0}, adj, hops=2, decay=0.5)
    # A sigue siendo la más activada (recibe algo de retorno desde B); los vecinos
    # más lejanos, menos. D queda sin alcanzar a 2 saltos.
    assert act["A"] > act["B"] > act["C"]
    assert round(act["B"], 4) == 0.5   # 1.0 * 0.5 (1 salto)
    assert round(act["C"], 4) == 0.25  # 0.5 * 0.5 (2 saltos)
    assert act.get("D", 0.0) == 0.0    # a 2 saltos todavía no llega


def test_convergencia_desde_varias_semillas():
    # Triángulo con un hub B conectado a dos semillas A y C. B debe SUMAR de ambas.
    adj = {"A": {"B"}, "B": {"A", "C"}, "C": {"B"}}
    act = propagate({"A": 1.0, "C": 1.0}, adj, hops=1, decay=0.5)
    # B no era semilla pero, al estar cableado a dos relevantes, emerge a 1.0
    # (0.5 desde A + 0.5 desde C). Esa convergencia es el corazón del spreading.
    assert round(act["B"], 4) == 1.0
    assert round(act["A"], 4) == 1.0
    assert round(act["C"], 4) == 1.0


def test_peso_hebbiano_amplifica():
    # Misma arista A-B pero con peso 2.0 (uso repetido la fortaleció). Debe propagar más.
    adj = {"A": {"B"}, "B": {"A"}}
    sin_peso = propagate({"A": 1.0}, adj, hops=1, decay=0.5)
    con_peso = propagate({"A": 1.0}, adj, hops=1, decay=0.5, edge_weights={("A", "B"): 2.0})
    assert round(sin_peso["B"], 4) == 0.5          # 1.0 * 0.5
    assert round(con_peso["B"], 4) == 1.0          # 1.0 * 0.5 * 2.0
    assert con_peso["B"] > sin_peso["B"]


def test_sin_semillas_no_rompe():
    assert propagate({}, {"A": {"B"}}, hops=2) == {}


def test_hops_cero_devuelve_solo_semillas():
    adj = {"A": {"B"}, "B": {"A"}}
    assert propagate({"A": 1.0}, adj, hops=0) == {"A": 1.0}
