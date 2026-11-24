import pytest

from raphael_core import CONTRACT_VERSION, Action, Level, Message, Origin, Trust, contract_compatible
from raphael_core.contract import parse_version


def test_version_del_contrato_es_semver():
    assert parse_version(CONTRACT_VERSION) == (2, 1, 0)
    assert parse_version("2.1") == (2, 1, 0)
    with pytest.raises(ValueError):
        parse_version("dos")


@pytest.mark.parametrize("spec,version,ok", [
    (">=2.0,<3", "2.0.0", True),
    (">=2.0,<3", "2.7.1", True),
    (">=2.0,<3", "3.0.0", False),
    (">=2.1", "2.0.5", False),
    ("^2.0", "2.4.0", True),
    ("^2.0", "3.0.0", False),
    ("~2.1", "2.1.9", True),
    ("~2.1", "2.2.0", False),
    ("2", "2.9.9", True),
    ("2", "1.9.9", False),
    ("2.0.0", "2.0.1", False),
    ("==2.0", "2.0.7", True),
])
def test_compatibilidad_de_contrato(spec, version, ok):
    assert contract_compatible(spec, version) is ok


@pytest.mark.parametrize("spec", ["", "=>2", ">=dos", ">=2,,"])
def test_restriccion_mal_escrita(spec):
    if spec == ">=2,,":  # comas de más se ignoran
        assert contract_compatible(spec, "2.0.0")
        return
    with pytest.raises(ValueError):
        contract_compatible(spec, "2.0.0")


def test_niveles_suben_y_bajan_un_escalon():
    assert Level.AUTO.weight < Level.APPROVAL.weight < Level.HUMAN.weight
    assert Level.HUMAN.lower() is Level.APPROVAL and Level.APPROVAL.lower() is Level.AUTO
    assert Level.AUTO.lower() is Level.AUTO and Level.HUMAN.higher() is Level.HUMAN
    assert Level("aprobacion") is Level.APPROVAL  # los valores siguen en castellano (los escribe la persona)


def test_mensaje_de_tercero_no_es_confiable_por_defecto():
    m = Message("whatsapp", "549341", "hola")
    assert m.contact == "whatsapp:549341" and m.trust is Trust.UNTRUSTED


def test_accion_ida_y_vuelta():
    a = Action("enviar_presupuesto", {"monto": 1000}, "Presupuesto", "whatsapp:1", Origin.THIRD_PARTY)
    b = Action.from_dict(a.to_dict())
    assert b == a and b.origin is Origin.THIRD_PARTY
    assert Action.from_dict({"type": "x"}).origin is Origin.SYSTEM
