"""La suite de contrato del harness v2 sobre la brigada real (personal y nube) y la matriz de montaje."""

from kit import BRIGADE_DIR
from raphael_core.testing.contract import run_contract_suite


def test_contrato_personal():
    r = run_contract_suite(str(BRIGADE_DIR), edition="personal")
    assert r.ok, r.text()


def test_contrato_nube():
    r = run_contract_suite(str(BRIGADE_DIR), edition="cloud")
    assert r.ok, r.text()


def test_manifiesto_de_desarrollo_igual_al_del_paquete():
    pkg = BRIGADE_DIR / "src" / "raphael_investigacion" / "manifest.yaml"
    assert pkg.read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), "corré scripts/sync_manifest.py"
