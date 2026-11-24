"""Tests de las piezas SIN modelo de la validación de Cerebro (validation/): evaluadores, baseline
y aislamiento. La corrida real contra Ollama es `python -m validation.cerebro`, no un test de pytest."""

from __future__ import annotations

import pytest

from validation import cerebro as scene
from validation import harness


# --- evaluadores ---------------------------------------------------------------
def test_citas_por_titulo_sin_importar_acentos_ni_mayusculas():
    ans = "Según [[Rotación de claves del servidor Orión]] y INCIDENTE DE ROTACION FALLIDA EN ORION, son 45 días."
    assert scene.cited_titles(ans, [t for t, _ in scene.SEEDS]) == [scene.N1_TITLE, scene.N2_TITLE]


def test_citas_por_id_de_nota():
    ans = "Fuentes: `jarvis/rotacion-de-claves-del-servidor-orion` y `jarvis/incidente-de-rotacion-fallida-en-orion`."
    assert scene.cited_titles(ans, [t for t, _ in scene.SEEDS]) == [scene.N1_TITLE, scene.N2_TITLE]
    assert scene.cited_titles("nada que ver", [t for t, _ in scene.SEEDS]) == []


def test_datos_de_las_notas():
    assert scene.found_facts("Se rota cada 45 días; falló con el disco al 98% y liberaron 14 GB.") == ["45_dias", "disco_98", "liberaron_14gb"]
    assert scene.found_facts("Se rota cada 30 días y el disco estaba al 50%.") == []  # datos inventados no cuentan


@pytest.mark.parametrize("text,ok", [
    ("No encontré información sobre quién aprobó el presupuesto.", True),
    ("No hay datos en mis notas sobre eso.", True),
    ("El presupuesto lo aprobó Marcos por $5000.", False),                      # inventa
    ("No hay registro, pero se aprobaron 5000 dólares.", False),                  # admite y aun así inventa monto
    # Respuesta REAL de nemotron (validación 2026-11-12): admite correctamente con otras palabras. Antes era un falso rojo.
    ("No está en mis notas. Busqué «presupuesto servidor Orión» y no apareció nada sobre un presupuesto ni sobre quién lo aprobó. "
     "Lo único que tengo guardado son estas dos notas: rota sus claves cada 45 días; liberaron 14 GB.", True),
    ("No sé quién lo aprobó.", True),
    ("El presupuesto fue aprobado por Marcos y la rotación es cada 45 días.", False),  # inventa un aprobador sin admitir nada
])
def test_detecta_si_admite_que_no_sabe(text, ok):
    assert scene.admits_ignorance(text) is ok


def test_marca_de_la_directriz_al_final():
    assert scene.ends_with_marker("Cada 45 días [[Rotación de claves del servidor Orión]]. FIN-DIRECTRIZ")
    assert scene.ends_with_marker("... fin-directriz.")
    assert not scene.ends_with_marker("FIN-DIRECTRIZ y después sigue hablando")


def test_la_escena_es_fija():
    # si alguien toca las notas/preguntas/directriz, el hash cambia y los baselines viejos se invalidan
    assert len(scene.SCENE_HASH) == 12 and len(scene.SEEDS) == 3


# --- baseline ------------------------------------------------------------------
BASE = {
    "scene_hash": "x", "model": "m", "embedding_model": "e",
    "retrieval": {"top2": ["a", "b"]},
    "answer": {"cited": ["a", "b"], "facts": ["45_dias"], "words": 40},
    "invention_probe": {"admitted": True},
    "directriz": {"marker": True, "words": 20},
    "conclusion": {"sources": ["a", "b"]},
}


def test_baseline_igual_no_marca_desbalances():
    assert harness.compare_to_baseline(BASE, dict(BASE)) == []


def test_baseline_marca_desbalances_de_conjuntos_booleanos_y_palabras():
    cur = {**BASE, "retrieval": {"top2": ["a", "c"]}, "invention_probe": {"admitted": False},
           "answer": {"cited": ["a", "b"], "facts": ["45_dias"], "words": 100}}
    drift = harness.compare_to_baseline(BASE, cur)
    assert any("retrieval.top2" in d for d in drift)
    assert any("invention_probe.admitted" in d for d in drift)
    assert any("answer.words" in d for d in drift)
    # variaciones chicas de longitud NO son desbalance
    assert harness.compare_to_baseline(BASE, {**BASE, "answer": {**BASE["answer"], "words": 50}}) == []


def test_baseline_de_otra_escena_no_es_comparable():
    drift = harness.compare_to_baseline(BASE, {**BASE, "scene_hash": "otro"})
    assert len(drift) == 1 and "--rebaseline" in drift[0]


def test_guardar_y_cargar_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "BASELINES_DIR", tmp_path / "baselines")
    assert harness.load_baseline("cerebro") is None
    harness.save_baseline("cerebro", {"scene_hash": "x"})
    assert harness.load_baseline("cerebro")["scene_hash"] == "x"


# --- aislamiento ---------------------------------------------------------------
def test_aislamiento_redirige_y_restaura_todo():
    from app.config import settings
    from brigades import cerebro_activity, chief, directrices

    real = (settings.obsidian_vault_path, settings.obsidian_embeddings_path, chief._STATE_DIR,
            cerebro_activity._PATH, directrices._PATH)
    with harness.isolated_environment() as env:
        assert settings.obsidian_vault_path == str(env.vault) != real[0]
        assert settings.obsidian_embeddings_path == str(env.embeddings) != real[1]
        for p in (chief._STATE_DIR, cerebro_activity._PATH, directrices._PATH):
            assert str(p).startswith(str(env.root))  # nada de estado de Cerebro queda en data/ real
        assert harness.assert_real_untouched(env).passed
        root = env.root
    assert (settings.obsidian_vault_path, settings.obsidian_embeddings_path, chief._STATE_DIR,
            cerebro_activity._PATH, directrices._PATH) == real
    assert not root.exists()  # se limpia al salir


def test_aislamiento_detecta_si_se_toca_lo_real(tmp_path):
    with harness.isolated_environment(keep=False) as env:
        sentinel = env.real_paths["directrices_cerebro"]
        before = harness._fingerprint({"x": sentinel})["x"]
        env.real_before["directrices_cerebro"] = ("distinto",)  # simula un cambio real
        assert not harness.assert_real_untouched(env).passed
        assert before == harness._fingerprint({"x": sentinel})["x"]  # (el test no toca nada real)
