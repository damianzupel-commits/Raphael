import pytest
from pydantic import ValidationError

from raphael_core import Level
from raphael_core.installation import installation_from


def test_instalacion_con_autonomia_corta_y_larga():
    inst = installation_from({
        "id": "clienta", "edition": "cloud", "plan": "pro",
        "brigades": {"empresas": {"config": {"sena_pct": 50}}, "legales": {"active": False}},
        "autonomy": {"empresas.enviar_presupuesto": "aprobacion",
                     "confirmar_turno": {"level": "automatico", "confirmed_by": "Ana"}},
    })
    assert inst.active_brigades() == ["empresas"]
    assert inst.brigade_config("empresas") == {"sena_pct": 50} and inst.brigade_config("nada") == {}
    assert inst.autonomy["empresas.enviar_presupuesto"].level is Level.APPROVAL
    assert inst.autonomy["confirmar_turno"].confirmed_by == "Ana"
    assert inst.trust.enabled and inst.trust.approvals_to_step_down == 10


@pytest.mark.parametrize("data", [
    {"id": "x", "edition": "marte"},
    {"id": "x", "edition": "cloud", "autonomy": {"Brigada Mala.accion": "automatico"}},
    {"id": "x", "edition": "cloud", "autonomy": {"accion": "siempre"}},
    {"id": "x", "edition": "cloud", "trust": {"approvals_to_step_down": 0}},
    {"id": "x", "edition": "cloud", "otra_cosa": True},
])
def test_instalacion_invalida(data):
    with pytest.raises(ValidationError):
        installation_from(data)
