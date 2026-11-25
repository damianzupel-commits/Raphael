"""Auditor: secretos, dependencias (con adaptadores), configuración, triage, convergencia y reporte."""

from __future__ import annotations

import json

import httpx

from raphael_seguridad.audit import run_audit
from raphael_seguridad.config_check import check_config
from raphael_seguridad.deps import (
    MockSource,
    OffSource,
    OsvSource,
    parse_package_json,
    parse_pyproject,
    parse_requirements,
    scan_deps,
    source_from_env,
)
from raphael_seguridad.report import render
from raphael_seguridad.secrets_scan import scan_text

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def test_detecta_secretos_y_los_tacha():
    found = scan_text("app/x.py", f'KEY = "{AWS}"\ntoken = "{GH}"\nok = 1\n')
    assert {f.rule_id for f in found} == {"aws-access-key", "github-token"}
    for f in found:
        assert AWS not in f.evidence and GH not in f.evidence and f.evidence.startswith("******")
        assert f.fix and f.severity == "critical"


def test_clave_privada_y_password():
    found = scan_text("k.pem", "-----BEGIN RSA PRIVATE KEY-----\nabc\n")
    assert found[0].rule_id == "private-key"
    assert scan_text("a.py", 'password = "hunter2hunter2"')[0].rule_id == "password-assign"
    assert scan_text("a.py", "password = os.environ['X']") == []


def test_parsers_de_dependencias():
    assert [(d.name, d.version) for d in parse_requirements("r.txt", "Django==1.11.0  # viejo\nrequests>=2\n")] == [("django", "1.11.0")]
    assert [d.name for d in parse_pyproject("p.toml", '[project]\ndependencies=["pyyaml==5.3.1"]')] == ["pyyaml"]
    assert [(d.name, d.version) for d in parse_package_json("package.json", json.dumps({"dependencies": {"lodash": "^4.17.15", "x": "*"}}))] == [("lodash", "4.17.15")]


def test_dependencias_con_el_adaptador_simulado_y_apagado(tmp_path):
    (tmp_path / "requirements.txt").write_text("django==1.11.0\n")
    files = [tmp_path / "requirements.txt"]
    found, why = scan_deps(tmp_path, files, MockSource())
    assert why is None and found[0].simulated and found[0].severity == "high" and "1.11.29" in found[0].fix
    found, why = scan_deps(tmp_path, files, OffSource())
    assert found == [] and "apagada" in why
    assert isinstance(source_from_env({}), OffSource) and isinstance(source_from_env({"SEGURIDAD_ADVISORIES": "osv"}), OsvSource)


def test_osv_real_con_transporte_falso(tmp_path):
    (tmp_path / "requirements.txt").write_text("django==1.11.0\nflask==3.0.0\n")

    def handler(req: httpx.Request) -> httpx.Response:
        assert "api.osv.dev" in str(req.url)
        return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-1", "summary": "xss", "database_specific": {"severity": "HIGH"}}]}, {}]})

    src = OsvSource(httpx.Client(transport=httpx.MockTransport(handler)))
    found, why = scan_deps(tmp_path, [tmp_path / "requirements.txt"], src)
    assert why is None and len(found) == 1 and found[0].severity == "high" and not found[0].simulated


def test_osv_caido_se_avisa_no_rompe(tmp_path):
    (tmp_path / "requirements.txt").write_text("django==1.11.0\n")
    src = OsvSource(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    found, why = scan_deps(tmp_path, [tmp_path / "requirements.txt"], src)
    assert found == [] and "no se pudo consultar osv" in why


def test_config_insegura(tmp_path):
    (tmp_path / ".env").write_text("A=1\n")
    (tmp_path / ".env.plantilla").write_text("A=\n")
    (tmp_path / "Dockerfile").write_text("FROM python\n")
    (tmp_path / "s.py").write_text("import subprocess\nsubprocess.run(x, shell=True)\nr = requests.get(u, verify=False)\n"
                                   "DEBUG = True\nyaml.load(f)\ncur.execute(f\"select * from t where id={i}\")\n")
    rules = {f.rule_id for f in check_config(tmp_path)}
    assert rules == {"env-committed", "docker-root", "shell-true", "tls-verify-off", "debug-on", "yaml-unsafe", "sql-concat"}


def test_pipeline_triage_convergencia_y_reporte(tmp_path):
    (tmp_path / "app.py").write_text(f'KEY = "{AWS}"\npassword = "changeme-please"\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text('DEBUG = True\n')
    (tmp_path / "requirements.txt").write_text("django==1.11.0\n")
    res = run_audit(tmp_path, MockSource())
    by = {(f.rule_id, f.file): f for f in res.findings}
    assert by[("password-assign", "app.py")].status == "false_positive"
    assert by[("debug-on", "tests/test_a.py")].status == "test"
    assert by[("aws-access-key", "app.py")].status == "open"
    assert [s["step"][:2] for s in res.steps] == ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]
    text = render(res)
    assert AWS not in text and "SIMULADOS" in text and "cómo corregirlo" in text and "CRÍTICO" in text
    (tmp_path / "app.py").write_text("KEY = os.environ['K']\n")
    res2 = run_audit(tmp_path, MockSource(), previous=res)
    assert "corregidos" in res2.steps[5]["detail"] and not any(f.rule_id == "aws-access-key" for f in res2.findings)


def test_repo_limpio_y_carpeta_inexistente(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n")
    assert "sin hallazgos" in render(run_audit(tmp_path)).lower()
    assert run_audit(tmp_path / "nada").steps[0]["state"] == "error"
