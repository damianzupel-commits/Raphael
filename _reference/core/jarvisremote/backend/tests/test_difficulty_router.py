"""Tests del router de dificultad del chat (app/harness/difficulty_router.py).

Puro y determinista: sin modelo, sin red.
"""

from app.harness import difficulty_router as dr


def test_simple_queda_en_base():
    assert dr.classify("hola, como andas?") == 2
    assert dr.classify("listame los archivos de mi escritorio") == 2


def test_vacio_o_none_devuelve_base():
    assert dr.classify("") == 2
    assert dr.classify(None) == 2
    assert dr.classify("   ") == 2


def test_base_tier_configurable():
    assert dr.classify("hola", base_tier=1) == 1
    # pero una tarea pesada escala igual, ignorando el base bajo
    assert dr.classify("auditá el repo", base_tier=1) == 3


def test_tareas_pesadas_escalan_a_3():
    for msg in [
        "auditá el código buscando vulnerabilidades",
        "refactorizá toda la arquitectura del backend",
        "explicá por qué este bug aparece",
        "revisá el código y hacé un code review",
        "diseñá una estrategia de testing",
    ]:
        assert dr.classify(msg) == 3, msg


def test_tareas_muy_dificiles_escalan_a_4():
    for msg in [
        "necesito una demostración formal de que termina",
        "usá el mejor modelo, es un problema muy complejo",
        "probá el teorema con una prueba matemática",
    ]:
        assert dr.classify(msg) == 4, msg


def test_mensaje_muy_largo_escala_aunque_no_tenga_keywords():
    largo = "contame una historia sobre un gato " * 60  # > 1200 chars, sin keywords
    assert len(largo) >= 1200
    assert dr.classify(largo) == 3


def test_acentos_y_mayusculas_no_afectan():
    assert dr.classify("AUDITÁ esto") == 3
    assert dr.classify("audita esto") == 3
    assert dr.classify("Demostración Formal requerida") == 4
