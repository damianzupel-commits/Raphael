"""Tests del core de analogía / structure-mapping (app/obsidian/analogy.py, Fase 7).

`clustering_coefficient`, `role_signature`, `signature_distance` y
`structural_similarity` son puros -> grafos sintéticos, sin vault ni embeddings."""

from app.obsidian.analogy import (
    clustering_coefficient,
    role_signature,
    signature_distance,
    structural_similarity,
)


def test_clustering_triangulo_vs_estrella():
    # triángulo: los 2 vecinos de A están conectados entre sí -> clustering 1.0
    tri = {"A": {"B", "C"}, "B": {"A", "C"}, "C": {"A", "B"}}
    assert clustering_coefficient("A", tri) == 1.0
    # estrella: los vecinos del centro NO se conectan entre sí -> 0.0
    star = {"H": {"A", "B", "C"}, "A": {"H"}, "B": {"H"}, "C": {"H"}}
    assert clustering_coefficient("H", star) == 0.0
    # grado < 2 -> 0.0
    assert clustering_coefficient("A", {"A": {"B"}}) == 0.0


def test_role_signature_normalizada():
    adj = {"H": {"A", "B"}, "A": {"H"}, "B": {"H"}}
    domains = {"H": "d1", "A": "d2", "B": "d3"}
    sig = role_signature("H", adj, domains, maxdeg=2, ndom_total=3)
    # grado 2/2=1.0 ; clustering 0 ; se conecta a 2 dominios de 3 = 0.666
    assert sig[0] == 1.0
    assert sig[1] == 0.0
    assert round(sig[2], 3) == 0.667


def test_signature_distance_y_similitud():
    a = (1.0, 0.0, 0.5)
    assert signature_distance(a, a) == 0.0
    assert structural_similarity(a, a) == 1.0
    # roles bien distintos -> similitud baja
    assert structural_similarity((1.0, 1.0, 1.0), (0.0, 0.0, 0.0)) == 0.0


def test_dos_hubs_en_dominios_distintos_son_analogos():
    # dos "hubs" idénticos en forma, en dominios distintos -> misma firma
    adj = {
        "d1/H": {"d1/a", "d1/b"}, "d1/a": {"d1/H"}, "d1/b": {"d1/H"},
        "d2/H": {"d2/a", "d2/b"}, "d2/a": {"d2/H"}, "d2/b": {"d2/H"},
    }
    domains = {k: k.split("/")[0] for k in adj}
    s1 = role_signature("d1/H", adj, domains, 2, 2)
    s2 = role_signature("d2/H", adj, domains, 2, 2)
    assert structural_similarity(s1, s2) == 1.0  # mismo rol, otro dominio = análogos
