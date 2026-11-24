import pytest
from pydantic import ValidationError

from raphael_core import Level
from raphael_core.manifest import load_manifest, manifest_from

BASE = {
    "id": "saludo",
    "name": "Brigada de saludo",
    "version": "1.0.0",
    "contract": ">=2.0,<3",
    "cooks": [{"id": "saludador", "entry": "raphael_saludo:Greeter"}],
    "actions": {"saludar": {"level": "automatico"}, "regalar": {"level": "aprobacion", "tags": ["spend"]}},
    "tools": [{"name": "leer_agenda"}, {"name": "escanear_red", "active_scan": True},
              {"name": "abrir_shell", "dangerous": True, "level": "humano"}],
    "events": {"publishes": ["saludo.hecho"], "consumes": ["pendiente.creado"]},
}


def m(**over):
    return manifest_from({**BASE, **over})


def test_manifiesto_valido():
    man = m()
    assert man.space == "saludo" and man.supports_contract()
    assert man.actions["regalar"].risky and not man.actions["saludar"].risky
    assert man.actions["saludar"].level is Level.AUTO


def test_en_la_nube_no_entra_nada_peligroso_ni_de_escaneo_activo():
    assert [t.name for t in m().tools_for("cloud")] == ["leer_agenda"]
    assert len(m().tools_for("personal")) == 3


def test_contrato_incompatible_se_detecta():
    assert not m(contract=">=3.0").supports_contract()
    assert m(contract="^2.0").supports_contract("2.5.0")


@pytest.mark.parametrize("over", [
    {"id": "Saludo"},                                                     # id con mayúscula
    {"version": "uno"},
    {"contract": "=>2"},
    {"actions": {"saludar": {}}},                                         # acción sin nivel
    {"actions": {"saludar": {"level": "quizas"}}},
    {"actions": {"saludar": {"level": "automatico", "tags": ["barato"]}}},
    {"cooks": [], "chief": None},                                         # sin nadie que trabaje
    {"cooks": [{"id": "a", "entry": "m:A"}, {"id": "a", "entry": "m:B"}]},
    {"cooks": [{"id": "a", "entry": "sin-dos-puntos"}]},
    {"events": {"publishes": ["Mal Evento"]}},
    {"tools": [{"name": "x"}, {"name": "x"}]},
    {"desconocido": 1},                                                   # nada fuera del esquema
    {"editions": []},
])
def test_manifiesto_invalido(over):
    with pytest.raises(ValidationError):
        m(**over)


def test_brigada_solo_con_jefe_y_espacio_propio():
    man = m(cooks=[], chief="raphael_inv.spec:SPEC", store={"space": "inv"})
    assert man.space == "inv"


def test_carga_desde_yaml(tmp_path):
    p = tmp_path / "manifest.yaml"
    p.write_text("id: x\nname: X\nversion: 0.1.0\ncontract: '^2.0'\ncooks:\n  - {id: c, entry: 'pkg.mod:C'}\n",
                 encoding="utf-8")
    assert load_manifest(p).id == "x"
