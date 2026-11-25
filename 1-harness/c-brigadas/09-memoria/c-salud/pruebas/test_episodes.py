"""Memoria episódica: crudo siempre, episodio selectivo, fail-safe a personal, registro encadenado y olvido a pedido."""

from __future__ import annotations

from datetime import datetime, timedelta

from kit import System, answers
from raphael_core.store import Store

from raphael_memoria import episodes as E

TECH = [{"role": "user", "content": "Arreglá el bug del endpoint de la api, falló el test"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_tests"}}]},
        {"role": "assistant", "content": "Listo, quedó resuelto."}]
CHARLA = [{"role": "user", "content": "gracias"}, {"role": "assistant", "content": "de nada"}]
T0 = datetime(2026, 11, 25, 10, 0)


def store(mirror=None):
    return E.EpisodeStore(Store().space("m"), lambda: T0, mirror)


def test_clasificacion_fail_safe_a_personal():
    assert E.classify("bug en el endpoint de la api con pytest") == "tecnico"
    assert E.classify("bug en el endpoint, pero me siento mal") == "personal"
    assert E.classify("hablemos de otra cosa") == "personal" and E.classify("api") == "personal"
    assert E.classify("lo que sea", dominio="trading") == "tecnico"


def test_lo_trivial_queda_en_el_crudo_sin_episodio_y_lo_sustantivo_se_destila():
    s = store()
    assert s.capture("c1", CHARLA) is None and len(s.space.list("crudo")) == 1 and s.list() == []
    ep = s.capture("c1", TECH)
    assert ep.resultado == "exito" and ep.acciones == ["run_tests"] and ep.sensibilidad == "tecnico"
    assert {b.kind for b in ep.beats} == {"fallo"} and len(s.space.list("crudo")) == 2


def test_capturar_nunca_rompe_un_turno():
    assert store().capture("c", [{"role": "user", "content": object()}] * 2) is None or True
    assert store().capture("c", []) is None


def test_la_leccion_la_mejora_el_modelo_y_si_falla_queda_la_heuristica():
    turn = E.current_turn(TECH)
    ok = E.distill(turn, conv_id="c", dominio="", sensibilidad="tecnico", ts_inicio="a", ts_fin="b", ai=lambda m: "Se arregló el bug.")
    assert ok.porque == "Se arregló el bug." and ok.distilled_by == "modelo-local"

    def boom(m):
        raise ConnectionError
    mal = E.distill(turn, conv_id="c", dominio="", sensibilidad="tecnico", ts_inicio="a", ts_fin="b", ai=boom)
    assert mal.distilled_by == "heuristica" and "Listo" in mal.porque


def test_recall_auto_filtra_personales_si_el_prompt_puede_salir_y_prioriza_recientes():
    a = E.Episode("a", timestamp_inicio=T0.isoformat(), sensibilidad="personal", salience=0.1)
    b = E.Episode("b", timestamp_inicio=(T0 - timedelta(days=9)).isoformat(), sensibilidad="tecnico", salience=0.9)
    c = E.Episode("c", timestamp_inicio=(T0 - timedelta(days=8)).isoformat(), sensibilidad="tecnico", salience=0.2)
    assert [e.id for e in E.recall_auto([a, b, c], T0)] == ["a", "b", "c"]
    assert [e.id for e in E.recall_auto([a, b, c], T0, include_personal=False)] == ["b", "c"]


def test_recall_por_tema_solo_trae_lo_que_lo_nombra():
    a = E.Episode("a", trigger="arreglar la api", salience=0.9)
    b = E.Episode("b", trigger="receta de ñoquis", salience=0.9)
    assert [e.id for e in E.recall_query([a, b], "api")] == ["a"] and E.recall_query([a, b], "zzz") == []


def test_el_registro_detecta_manipulacion_y_el_olvido_no_guarda_el_contenido():
    s = store()
    ep = s.capture("c", TECH)
    assert s.verify() == {"ok": True, "entries_checked": 1, "broken_at_seq": None, "reason": ""}
    assert s.forget(ep.id) is True and s.get(ep.id) is None and s.forget("nope") is False
    v = s.verify()
    assert v["ok"] and v["entries_checked"] == 3
    assert "bug" not in str(s.space.list("registro")[-2:])
    e = s.space.get("registro", "00000001")
    s.space.put("registro", "00000001", {**e, "payload": {**e["payload"], "resultado": "fallo"}})
    assert s.verify()["ok"] is False and s.verify()["broken_at_seq"] == 1


def test_el_turno_por_evento_arma_el_episodio_y_el_espejo_en_el_vault(tmp_path):
    x = System(tmp_path, transport=answers(["Se arregló."]))
    x.publish("memoria.turno", {"conv_id": "c1", "history": TECH, "dominio": "web"})
    ep = x.space().list("episodios")[0]
    assert ep["conv_id"] == "c1" and ep["distilled_by"] == "modelo-local"
    assert (x.vault / "12-Memoria-Raphael" / f"{ep['id']}.md").exists()
    r = x.cmd("consolidador", "episodios", {"tema": "bug"})
    assert ep["id"] in r["texto"] and x.cmd("consolidador", "verificar_registro")["ok"]


def test_olvidar_un_episodio_pide_aprobacion_y_borra_el_espejo(tmp_path):
    x = System(tmp_path)
    x.publish("memoria.turno", {"conv_id": "c1", "history": TECH})
    eid = x.space().list("episodios")[0]["id"]
    x.cmd("consolidador", "olvidar", {"kind": "episodio", "id": eid})
    assert x.space().get("episodios", eid)
    x.approve(x.pending("olvidar")[0]["id"])
    assert x.space().get("episodios", eid) is None and not (x.vault / "12-Memoria-Raphael" / f"{eid}.md").exists()


def test_con_episodios_apagados_el_turno_se_ignora(tmp_path):
    x = System(tmp_path, {"episodes": {"enabled": False}})
    x.publish("memoria.turno", {"conv_id": "c1", "history": TECH})
    assert x.space().list("episodios") == [] and x.space().list("crudo") == []
