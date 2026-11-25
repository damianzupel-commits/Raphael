import pytest
from kit import ID, System


def test_modo_simulado_se_avisa_en_la_salud():
    h = System().rt.status()["brigades"][ID]["health"]
    assert h["ok"] and "SIMULADO" in h["detail"]


def test_modo_real_sin_claves_sigue_sano_y_dice_cuales_faltan():
    h = System({"modo": "real"}).rt.status()["brigades"][ID]["health"]
    assert h["ok"] and "SHODAN_KEY" in h["detail"]


@pytest.mark.parametrize("cfg", [{"modo": "otro"}, {"pines_max": 3}, {"pines_max": "x"}, {"cualquiera": 1}])
def test_config_invalida_no_monta(cfg):
    with pytest.raises(AssertionError):
        System(cfg)
