"""La suite de contrato del harness v2 y la matriz de montaje, con los adaptadores simulados."""

from kit import BRIGADE_DIR, System
from raphael_core.testing.contract import run_contract_suite


def test_pasa_la_suite_de_contrato_en_la_edicion_personal():
    r = run_contract_suite(BRIGADE_DIR, edition="personal")
    assert r.ok, r.text()


def test_se_monta_sin_errores_ni_avisos_raros(tmp_path):
    x = System(sandbox=tmp_path)
    assert x.report["errors"] == {} and "operaciones" in x.rt.brigades
