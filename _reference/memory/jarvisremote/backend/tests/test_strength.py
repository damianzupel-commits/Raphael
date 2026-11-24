"""Tests del core de fuerza de recuperación (app/obsidian/strength.py, Fase 4).

`effective_boost`, `factor` y `_bump_entry` son puros (reciben `now`), así que se
testean con un reloj fijo, sin disco ni tiempo real."""

from datetime import datetime, timedelta, timezone

from app.obsidian.strength import _bump_entry, effective_boost, factor

NOW = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dias_atras):
    return (NOW - timedelta(days=dias_atras)).isoformat()


def test_boost_sin_tiempo_no_decae():
    # usado recién -> el boost está casi intacto
    assert round(effective_boost(1.0, _iso(0), NOW), 4) == 1.0


def test_boost_decae_a_la_mitad_en_una_vida_media():
    # a 14 días (half-life default) el boost cae a la mitad
    assert round(effective_boost(1.0, _iso(14), NOW), 4) == 0.5
    assert round(effective_boost(1.0, _iso(28), NOW), 4) == 0.25


def test_factor_nunca_baja_de_uno():
    # sin boost -> factor neutro 1.0; con boost -> > 1.0; muy viejo -> tiende a 1.0
    assert factor(0.0, _iso(0), NOW) == 1.0
    assert factor(1.0, _iso(0), NOW) == 2.0
    assert 1.0 < factor(1.0, _iso(100), NOW) < 1.01  # casi neutro, nunca < 1.0


def test_bump_entry_nueva_y_acumula_con_decay():
    # nota nueva: boost = incremento
    e1 = _bump_entry(None, NOW, increment=0.5)
    assert e1["boost"] == 0.5 and e1["last_used"] == NOW.isoformat()
    # usarla de nuevo 14 días después: el 0.5 decayó a 0.25, + 0.5 = 0.75
    later = NOW + timedelta(days=14)
    e2 = _bump_entry(e1, later, increment=0.5)
    assert round(e2["boost"], 4) == 0.75


def test_bump_entry_topea_en_cap():
    e = {"boost": 0.0, "last_used": NOW.isoformat()}
    for _ in range(50):
        e = _bump_entry(e, NOW, increment=0.5, cap=2.0)
    assert e["boost"] == 2.0  # no crece infinito


def test_fecha_invalida_no_rompe():
    # si la fecha no parsea, se asume sin decaer (conservador, no tira)
    assert effective_boost(1.0, "no-es-fecha", NOW) == 1.0


def test_valencia_negativa_con_piso():
    # boost negativo (aversión) baja el factor por debajo de 1.0, pero con piso 0.5
    assert factor(-0.5, _iso(0), NOW) == 0.5
    assert factor(-5.0, _iso(0), NOW) == 0.5   # clampado al piso, no explota
    assert 0.5 < factor(-0.3, _iso(0), NOW) < 1.0
    # la aversión también decae con el tiempo (magnitud hacia 0)
    assert round(effective_boost(-1.0, _iso(14), NOW), 4) == -0.5


def test_bump_negativo_floored():
    # un bump negativo (aversión) crea una entrada con boost negativo, con piso
    e = _bump_entry(None, NOW, increment=-0.5)
    assert e["boost"] == -0.5
    e = _bump_entry(e, NOW, increment=-1.0)   # intentar bajar más
    assert e["boost"] == -0.5                  # floored en _FLOOR_BOOST
