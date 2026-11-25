"""Vigilancia de tendencias: intervalo, novedad, relevancia, tope diario, sin proveedor y borrado."""

from datetime import timedelta

import pytest
from kit import make_env

from raphael_investigacion import trends
from raphael_investigacion.casefile import CaseError


def test_seguir_y_revisar_avisa_solo_lo_nuevo_y_relevante():
    ev: list = []
    env = make_env(events=ev)
    trends.follow(env, "baterías estado sólido")
    r = trends.review(env)
    assert [a["url"] for a in r["alerts"]] == ["https://ejemplo.test/baterias-estado-solido"]
    a = r["alerts"][0]
    assert a["published"] == "2026-11-10" and a["retrieved_at"] and a["resumen_por"] == "fragmento del buscador"
    assert ev == [("tendencia.relevante", {"count": 1, "topics": ["baterías estado sólido"], "titles": [a["title"]]})]
    # misma hora: no le toca; pasado el intervalo: no hay nada nuevo
    assert trends.review(env)["revisados"] == []
    env.clock["now"] += timedelta(hours=25)
    assert trends.review(env)["alerts"] == []


def test_umbral_y_palabras_clave():
    env = make_env()
    trends.follow(env, "ia local", keywords=["modelos", "blockchain", "cuantica"], min_score=0.9, queries=["ia local"])
    assert trends.review(env)["alerts"] == []
    env2 = make_env()
    trends.follow(env2, "ia local", keywords=["modelos"], queries=["ia local"])
    assert len(trends.review(env2)["alerts"]) == 1


def test_tope_diario_no_pierde_lo_que_quedo():
    env = make_env({"trends": {"max_alerts_per_day": 1}})
    trends.follow(env, "x", keywords=[], queries=["noticias"])
    r = trends.review(env)
    assert len(r["alerts"]) == 1 and r["revisados"][0]["capped"]
    env.clock["now"] += timedelta(days=1, hours=1)
    assert len(trends.review(env)["alerts"]) == 1                          # el segundo sale al otro día


def test_sin_proveedor_lo_dice_y_no_inventa():
    env = make_env({"search": {"providers": ["brave"]}})
    trends.follow(env, "algo")
    r = trends.review(env)
    assert r["alerts"] == [] and "sin proveedor" in r["revisados"][0]["status"]
    assert trends.watches(env)[0]["last_status"].startswith("sin proveedor")


def test_resumen_con_modelo():
    env = make_env(ask=lambda p, m: "Resume el avance.")
    trends.follow(env, "baterías estado sólido")
    a = trends.review(env)["alerts"][0]
    assert a["summary"] == "Resume el avance." and a["resumen_por"] == "modelo"


def test_pausar_reanudar_borrar_y_limites():
    env = make_env()
    w = trends.follow(env, "baterías estado sólido")
    trends.set_active(env, w["id"], False)
    assert trends.review(env)["revisados"] == []
    trends.set_active(env, w["id"], True)
    trends.review(env)
    assert trends.delete(env, w["id"])["alerts_deleted"] == 1 and trends.watches(env) == []
    with pytest.raises(CaseError):
        trends.follow(env, " ")
    with pytest.raises(CaseError):
        trends.set_active(env, "no-existe", True)
    for i in range(trends.MAX_WATCHES):
        trends.follow(env, f"tema{i}")
    with pytest.raises(CaseError, match="ya hay"):
        trends.follow(env, "uno más")
