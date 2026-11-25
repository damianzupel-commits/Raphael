"""Lo que Cerebro hace solo: apagado por default, nunca escribe sin aprobación y avisa los cambios de salud una vez."""

from __future__ import annotations

from datetime import timedelta

from kit import System, answers
from test_consolidation import SINTESIS, A, B


def armar(tmp_path, proactive=True, transport=None):
    x = System(tmp_path, {"proactive": {"enabled": proactive, "every_minutes": 60}}, transport=transport)
    x.save(*A)
    x.save(*B)
    return x


def test_apagado_no_hace_nada(tmp_path):
    x = armar(tmp_path, False, answers([SINTESIS]))
    antes = x.cmd("proactivo", "actividad")
    x.tick()
    assert x.pending() == [] and x.cmd("proactivo", "actividad") == antes


def test_prendido_propone_consolidar_y_espera_aprobacion_sin_insistir(tmp_path):
    x = armar(tmp_path, True, answers([SINTESIS]))
    x.tick()
    assert len(x.pending("consolidar")) == 1
    x.tick(x.clock() + timedelta(hours=2))
    assert len(x.pending("consolidar")) == 1                  # el mismo grupo no se pide de nuevo
    x.approve(x.pending("consolidar")[0]["id"])
    assert len(x.cmd("recuperador", "notas", {"tag": "consolidacion"})) == 1


def test_no_vuelve_a_correr_antes_del_intervalo(tmp_path):
    x = armar(tmp_path, True)
    x.tick()
    n = len(x.cmd("proactivo", "actividad"))
    x.tick(x.clock() + timedelta(minutes=10))
    assert len(x.cmd("proactivo", "actividad")) == n


def test_sin_modelo_lo_anota_pero_no_pide_nada(tmp_path):
    x = armar(tmp_path, True)
    x.tick()
    assert x.pending() == [] and any("no hay modelo local" in i["detalle"] for i in x.cmd("proactivo", "actividad"))


def test_pasada_manual_corre_aunque_el_automatico_este_apagado(tmp_path):
    x = armar(tmp_path, False, answers([SINTESIS]))
    r = x.cmd("proactivo", "pasada")
    assert r["consolidacion"]["a_consolidar"] == 1 and len(x.pending("consolidar")) == 1


def test_avisa_una_vez_cuando_cae_el_modelo_local_y_cuando_vuelve(tmp_path):
    x = armar(tmp_path, False, answers([]))
    eventos = []
    x.rt.bus.subscribe("memoria.degradada", lambda e, d: eventos.append(e), owner="test")
    x.rt.bus.subscribe("memoria.recuperada", lambda e, d: eventos.append(e), owner="test")
    models = x.rt.models
    x.tick()                                                   # primer estado: sin aviso
    x.rt.models = None
    x.tick()
    x.tick()
    x.rt.models = models
    x.tick()
    assert eventos == ["memoria.degradada", "memoria.recuperada"]
