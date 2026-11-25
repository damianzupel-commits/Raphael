"""Líneas rojas: lo intocable no se propone ni se aplica, ni con aprobación."""

import pytest
from kit import FIX, System, make_project
from raphael_core import ActionError

from raphael_selfrepair import guardrail

PROTEGIDOS = [
    "authorized_targets.yaml", "app/auth.py", "app/.env", "data/raphael.env", "1-harness/b-codigo/src/raphael_core/policy.py",
    "1-harness/b-codigo/src/raphael_core/approvals.py", "1-harness/b-codigo/src/raphael_core/audit.py",
    "1-harness/c-brigadas/15-empresas/b-codigo/manifest.yaml", "installation.yaml", "modelos.yaml",
    "3-mando/b-herramientas/gate.py", ".git/config", ".github/workflows/x.yml", "secrets/x.txt", "claves/firma.jks",
    "1-harness/c-brigadas/13-autorreparacion/b-codigo/src/raphael_selfrepair/guardrail.py",
    "C:\\Users\\d\\raphael\\1-harness\\b-codigo\\src\\raphael_core\\policy.py",
]
LIBRES = ["app/calc.py", "src/raphael_empresas/cooks/orders.py",
          "1-harness/c-brigadas/00-orquestador/b-codigo/src/x/secretary.py",
          "src/authors.py", "README.md"]


@pytest.mark.parametrize("path", PROTEGIDOS)
def test_protegidos(path):
    assert guardrail.check(path), path


@pytest.mark.parametrize("path", LIBRES)
def test_libres(path):
    assert guardrail.check(path) is None, path


def test_mayusculas_y_barras_no_la_esquivan():
    assert guardrail.check("APP\\AUTH.PY")
    assert guardrail.check("Authorized_Targets.YAML")


def test_la_config_suma_pero_no_saca():
    assert guardrail.check("app/calc.py", ["calc.py"])
    assert guardrail.check("authorized_targets.yaml", ["otra-cosa"])


def test_proponer_un_archivo_protegido_se_rechaza(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="LÍNEA ROJA"):
        s.cmd("proponer", "proponer", {**FIX, "file": "app/auth.py", "old_snippet": "True", "new_snippet": "False"})
    assert s.cmd("proponer", "propuestas", {}) == []


def test_una_ruta_con_punto_punto_que_apunta_a_un_protegido_se_rechaza(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="LÍNEA ROJA"):
        bad = {**FIX, "file": "app/../authorized_targets.yaml", "old_snippet": "[]", "new_snippet": "['x']"}
        s.cmd("proponer", "proponer", bad)


def test_un_symlink_que_apunta_a_un_protegido_se_rechaza(tmp_path):
    root = make_project(tmp_path)
    try:
        (root / "app" / "inocente.py").symlink_to(root / "app" / "auth.py")
    except OSError:
        pytest.skip("este Windows no deja crear symlinks sin permisos extra")
    s = System(root)
    with pytest.raises(ActionError, match="LÍNEA ROJA"):
        s.cmd("proponer", "proponer", {**FIX, "file": "app/inocente.py", "old_snippet": "True", "new_snippet": "False"})


def test_fuera_de_la_raiz_se_rechaza(tmp_path):
    root = make_project(tmp_path / "proyecto")
    (tmp_path / "afuera.py").write_text("x = 1\n")
    s = System(root)
    for f in ("../afuera.py", str(tmp_path / "afuera.py")):
        with pytest.raises(ActionError, match="fuera de la raíz"):
            s.cmd("proponer", "proponer", {**FIX, "file": f, "old_snippet": "x = 1", "new_snippet": "x = 2"})


def test_la_linea_roja_vale_tambien_al_aplicar(tmp_path):
    """Aunque una propuesta ya guardada apunte a un archivo protegido (guardada a mano en el almacén), no se aplica."""
    root = make_project(tmp_path)
    s = System(root)
    from raphael_selfrepair import proposals
    p = {"id": "sf-deadbeef", "file": "app/auth.py", "old_snippet": "True", "new_snippet": "False", "diff": "",
         "digest": proposals.digest("app/auth.py", "True", "False"), "rationale": "x", "commit_message": "x",
         "status": proposals.PROPOSED, "created_at": "2026-11-25T10:00:00"}
    proposals.save(s.ctx("proponer").shared, p)
    with pytest.raises(ActionError, match="LÍNEA ROJA"):
        s.cmd("aplicar", "aplicar", {"proposal_id": "sf-deadbeef"})
    assert "SECRET_CHECK = True" in (root / "app" / "auth.py").read_text()
