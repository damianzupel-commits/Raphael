"""Tests de audit_report.generate_report: compila hallazgos de seguridad +
calidad ya cacheados y fixes/ediciones ya auditados (mockeando audit_log.read_entries
para no tocar el audit.log real) en una nota Markdown guardada en el vault de
Obsidian."""

from datetime import datetime, timezone

import pytest

from app import audit_report
from app.findings.models import Finding, ScanResult
from app.obsidian import vault
from app.quality import store as quality_store
from app.security import store as security_store
from app.testing import store as test_store
from app.testing.models import RunOutcome


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(security_store.settings, "security_scan_dir", str(tmp_path / "security_cache"))
    monkeypatch.setattr(quality_store.settings, "quality_scan_dir", str(tmp_path / "quality_cache"))
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(test_store.settings, "test_run_dir", str(tmp_path / "test_run_cache"))


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    return root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_generate_report_raises_without_any_scan(project):
    with pytest.raises(ValueError):
        audit_report.generate_report(str(project))


def test_generate_report_compiles_findings_fixes_and_summary(project, monkeypatch):
    sec_finding = Finding(
        id="sec1", tool="bandit", file="app.py", line=6, end_line=6,
        severity="high", rule_id="B608", message="sqli", cwe=["CWE-89"],
    )
    qual_finding = Finding(
        id="qual1", tool="ruff", file="app.py", line=1, end_line=1,
        severity="low", rule_id="F401", message="unused import",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[sec_finding],
    ))
    quality_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["ruff"], tools_skipped={}, findings=[qual_finding],
    ))

    fix_entry = {
        "target": "code", "tool": "code_apply_fix", "ok": True,
        "arguments": {"path": str(project), "file": "app.py", "commit_message": "fix: sqli", "confirm": True},
        "result": {"applied": True, "file": "app.py", "committed": True, "commit_hash": "abc123", "diff": "..."},
    }
    edit_entry = {
        "target": "fs", "tool": "fs_write_file", "ok": True,
        "arguments": {"path": str(project), "file": "notes.md", "append": False},
        "result": {"committed": True, "commit_hash": "def456", "note": "ok"},
    }
    unrelated_entry = {
        "target": "code", "tool": "code_apply_fix", "ok": True,
        "arguments": {"path": str(project.parent / "other_proj"), "file": "x.py", "commit_message": "fix"},
        "result": {"applied": True, "committed": True, "commit_hash": "zzz"},
    }

    def _fake_read_entries(target=None, tool=None):
        entries = [fix_entry, edit_entry, unrelated_entry]
        if tool is not None:
            entries = [e for e in entries if e["tool"] == tool]
        return entries

    monkeypatch.setattr(audit_report.audit_log, "read_entries", _fake_read_entries)

    result = audit_report.generate_report(str(project))

    assert result["security_findings"] == 1
    assert result["quality_findings"] == 1
    assert result["fixes_applied"] == 1
    assert result["general_edits_applied"] == 1
    assert "abc123" in result["content_preview"]
    assert "def456" in result["content_preview"]
    assert "zzz" not in result["content_preview"]  # de otro proyecto, no debe aparecer

    note = vault.read_note(result["note_id"])
    assert note.author == "jarvis"
    assert "reportes" in note.tags
    assert "B608" in note.content
    assert "F401" in note.content


def test_generate_report_excludes_known_noise_from_executive_summary(project):
    """B101 (bandit assert_used) es ruido conocido -- confirmado auditando
    httpie/cli, donde dominaba el conteo total sin ser una vulnerabilidad real.
    El resumen ejecutivo tiene que destacar el hallazgo real (B608) y excluir
    el B101 del conteo destacado, pero sin borrarlo del todo -- sigue en la
    tabla de detalle, marcado como ruido conocido."""
    real_finding = Finding(
        id="sec1", tool="bandit", file="app.py", line=6, end_line=6,
        severity="high", rule_id="B608", message="sqli real", cwe=["CWE-89"],
    )
    noise_finding = Finding(
        id="sec2", tool="bandit", file="tests/test_app.py", line=12, end_line=12,
        severity="low", rule_id="B101", message="Use of assert detected.",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={},
        findings=[real_finding, noise_finding],
    ))

    result = audit_report.generate_report(str(project))

    assert result["security_findings"] == 2  # el total sigue contando todo, sin ocultar nada
    note = vault.read_note(result["note_id"])
    summary_section = note.content.split("## Resumen ejecutivo")[1].split("## Hallazgos de seguridad")[0]
    assert "1 hallazgo(s) de seguridad real(es)" in summary_section
    assert "excluyeron 1 hallazgo(s)" in summary_section
    assert "B101" in summary_section
    assert "B608" in note.content
    assert "B101" in note.content  # sigue en la tabla de detalle, no se borra
    assert "ruido conocido" in note.content


def _save_test_run(project, **overrides) -> None:
    defaults = dict(
        root=str(project), ran_at=_now(), detected=True, command="python -m pytest",
        language="Python", detect_reason="x", exit_code=0, passed=True, timed_out=False,
        stdout="1 passed", stderr="", stdout_truncated=False, stderr_truncated=False,
    )
    defaults.update(overrides)
    test_store.save_last_run(RunOutcome(**defaults))


def test_generate_report_flags_that_tests_were_never_run(project):
    """Gap principal identificado en el informe de estado 2026-08-10: el reporte
    NUNCA debe poder leerse como "resuelto" sin decir si hubo (o no) una
    verificación de tests real -- si nunca se corrió, el resumen ejecutivo lo
    dice explícitamente en la primera línea, no lo omite en silencio."""
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))

    result = audit_report.generate_report(str(project))

    assert result["tests"] is None
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "Nunca se corrió una verificación de tests real" in summary


def test_generate_report_flags_when_no_test_suite_was_detected(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, detected=False, command=None, language=None, detect_reason=None, exit_code=None, passed=False, stdout="")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["detected"] is False
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "No se detectó ninguna suite de tests real" in summary


def test_generate_report_flags_a_green_test_run(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, passed=True, command="python -m pytest")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["passed"] is True
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "EN VERDE" in summary


def test_generate_report_prominently_flags_a_failed_test_run(project):
    security_store.save_scan(ScanResult(root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[]))
    _save_test_run(project, passed=False, exit_code=1, command="python -m pytest", stdout="1 failed")

    result = audit_report.generate_report(str(project))

    assert result["tests"]["passed"] is False
    note = vault.read_note(result["note_id"])
    summary = note.content.split("## Resumen ejecutivo")[1]
    assert "FALLÓ" in summary
    assert "no dar este proyecto por estable" in summary.lower()


# ---------------------------------------------------------------------------
# Capa client-facing: narrativa del LLM + anexo técnico. Desde 2026-09-22 `generate_client_report` delega en la
# brigada (app/harness/audit_brigade.py) y cae al pipeline lineal si falla; estos tests prueban el LINEAL directo
# (la red de seguridad), sin pasar por los modelos reales de la brigada.
# Se mockea _client_narrative para NO pegarle al LLM real (convención del proyecto).
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_client_report_usa_narrativa_del_llm_y_conserva_el_anexo_tecnico(project, monkeypatch):
    sec_finding = Finding(
        id="sec1", tool="semgrep", file="views.py", line=81, end_line=81,
        severity="high", rule_id="subprocess-injection", message="user input into subprocess",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["semgrep"], tools_skipped={}, findings=[sec_finding],
    ))

    async def _fake_triage(root, findings):
        # El triage lo confirma como real (es una vuln genuina).
        return [
            Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "alcanzable desde input"})
            for f in findings
        ]

    monkeypatch.setattr(audit_report.triage, "triage_findings", _fake_triage)

    async def _fake_narrative(name, digest):
        assert "subprocess-injection" in digest  # el hallazgo real le llegó al LLM
        return (
            "## Resumen ejecutivo\n\nTu sistema está expuesto a que un atacante ejecute comandos.\n\n"
            "## Riesgos prioritarios\n\n### Inyección de comandos\n"
            "**Qué es:** un dato del usuario llega a la consola del servidor.\n"
            "**Por qué te importa:** pueden tomar control del servidor.\n"
            "**Cómo se arregla:** validar/sanitizar esa entrada."
        )

    monkeypatch.setattr(audit_report, "_client_narrative", _fake_narrative)

    async def _passthru_catador(name, narrative, evidence):
        return narrative, []

    monkeypatch.setattr(audit_report, "_catador_review", _passthru_catador)

    result = await audit_report._generate_client_report_linear(str(project))

    assert result["narrative_generated"] is True
    assert "Inyección de comandos" in result["content_preview"]
    note = vault.read_note(result["note_id"])
    assert "cliente" in note.tags
    assert "Resumen ejecutivo" in note.content
    assert "## Anexo técnico" in note.content
    assert "subprocess-injection" in note.content  # la tabla técnica cruda sigue estando


@pytest.mark.anyio
async def test_client_report_cae_a_resumen_mecanico_si_no_hay_narrativa(project, monkeypatch):
    sec_finding = Finding(
        id="sec1", tool="bandit", file="app.py", line=1, end_line=1,
        severity="critical", rule_id="B201", message="flask debug true",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[sec_finding],
    ))

    async def _fake_triage(root, findings):
        return [
            Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "real"})
            for f in findings
        ]

    monkeypatch.setattr(audit_report.triage, "triage_findings", _fake_triage)

    async def _no_narrative(name, digest):
        return None

    monkeypatch.setattr(audit_report, "_client_narrative", _no_narrative)

    result = await audit_report._generate_client_report_linear(str(project))

    assert result["narrative_generated"] is False
    note = vault.read_note(result["note_id"])
    assert "Resumen ejecutivo" in note.content  # fallback mecánico
    assert "## Anexo técnico" in note.content
    assert "B201" in note.content


@pytest.mark.anyio
async def test_client_report_triage_descarta_falsos_positivos_y_no_los_muestra_como_riesgo(project, monkeypatch):
    # El caso del `flask lint` del Test B: un subprocess en un comando CLI de dev.
    # El triage lo marca falso positivo -> NO entra en los riesgos prioritarios,
    # va a la sección "Descartados por triage" con su razón.
    fp_finding = Finding(
        id="fp1", tool="semgrep", file="conduit/commands.py", line=41, end_line=41,
        severity="medium", rule_id="dangerous-subprocess-use", message="subprocess call",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["semgrep"], tools_skipped={}, findings=[fp_finding],
    ))

    async def _fake_triage(root, findings):
        return [
            Finding(**{
                **f.to_dict(),
                "triage_status": "false_positive",
                "triage_reasoning": "es un comando CLI de dev, sin input de usuario",
            })
            for f in findings
        ]

    monkeypatch.setattr(audit_report.triage, "triage_findings", _fake_triage)

    captured = {}

    async def _fake_narrative(name, digest):
        captured["digest"] = digest
        return "## Resumen ejecutivo\n\nPostura buena.\n\n## Riesgos prioritarios\n\nSin riesgos relevantes."

    monkeypatch.setattr(audit_report, "_client_narrative", _fake_narrative)

    async def _passthru_catador(name, narrative, evidence):
        return narrative, []

    monkeypatch.setattr(audit_report, "_catador_review", _passthru_catador)

    result = await audit_report._generate_client_report_linear(str(project))

    assert result["false_positives_discarded"] == 1
    assert result["security_findings_real_after_triage"] == 0
    # El falso positivo NO llegó al LLM como riesgo prioritario.
    assert "dangerous-subprocess-use" not in captured["digest"]
    note = vault.read_note(result["note_id"])
    assert "Descartados por triage" in note.content
    assert "comando CLI de dev" in note.content  # la razón queda registrada


# ---------------------------------------------------------------------------
# E2 (contexto por ruta) + E6 (Catador / QA) -- brigada de auditoría, 2026-09-06.
# Motivado por la calibración de flask-oficial: la narrativa dijo "MD5" cuando el
# código es sha1, y "RCE en producción" para un debug=True que estaba en tests.
# ---------------------------------------------------------------------------


def test_path_context_clasifica_por_ruta():
    assert audit_report._path_context("tests/test_basic.py") == "tests"
    assert audit_report._path_context("myproj/tests/unit/test_x.py") == "tests"
    assert audit_report._path_context("src/app.spec.ts") == "tests"
    assert audit_report._path_context("examples/tutorial/auth.py") == "examples"
    assert audit_report._path_context("docs/conf.py") == "docs"
    assert audit_report._path_context("node_modules/foo/bar.js") == "vendor"
    assert audit_report._path_context("src/flask/sessions.py") == "production"
    assert audit_report._path_context("app/models/user.py") == "production"


@pytest.mark.anyio
async def test_client_report_saca_hallazgos_no_productivos_de_los_riesgos(project, monkeypatch):
    """Un hallazgo en tests/ NO debe entrar en los riesgos prioritarios del cliente
    (no es riesgo de producción); va a una sección aparte. Es el caso del debug=True
    en tests/ de flask-oficial."""
    prod = Finding(
        id="p1", tool="bandit", file="app/views.py", line=10, end_line=10,
        severity="high", rule_id="B602", message="shell=True",
    )
    en_tests = Finding(
        id="t1", tool="bandit", file="tests/test_basic.py", line=1902, end_line=1902,
        severity="high", rule_id="B201", message="flask debug true",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={},
        findings=[prod, en_tests],
    ))

    async def _fake_triage(root, findings):
        return [Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "real"}) for f in findings]

    monkeypatch.setattr(audit_report.triage, "triage_findings", _fake_triage)

    captured = {}

    async def _fake_narrative(name, digest):
        captured["digest"] = digest
        return "## Resumen ejecutivo\n\nOk.\n\n## Riesgos prioritarios\n\n### Shell\n**Qué es:** x."

    monkeypatch.setattr(audit_report, "_client_narrative", _fake_narrative)

    async def _passthru_catador(name, narrative, evidence):
        return narrative, []

    monkeypatch.setattr(audit_report, "_catador_review", _passthru_catador)

    result = await audit_report._generate_client_report_linear(str(project))

    assert result["nonproduction_findings"] == 1
    # el hallazgo de tests NO llegó al LLM como riesgo prioritario...
    assert "B201" not in captured["digest"]
    assert "B602" in captured["digest"]  # ...pero el de producción sí
    note = vault.read_note(result["note_id"])
    assert "código no productivo" in note.content  # va a su sección aparte
    assert "tests/test_basic.py" in note.content


@pytest.mark.anyio
async def test_client_report_catador_corrige_y_deja_constancia(project, monkeypatch):
    """El Catador corrige una afirmación que el código no respalda (ej. 'MD5' cuando
    es sha1) y deja la corrección registrada en la sección de verificación."""
    finding = Finding(
        id="s1", tool="bandit", file="src/sessions.py", line=281, end_line=281,
        severity="high", rule_id="B324", message="hashlib weak",
    )
    security_store.save_scan(ScanResult(
        root=str(project), scanned_at=_now(), tools_run=["bandit"], tools_skipped={}, findings=[finding],
    ))

    async def _fake_triage(root, findings):
        return [Finding(**{**f.to_dict(), "triage_status": "real", "triage_reasoning": "real"}) for f in findings]

    monkeypatch.setattr(audit_report.triage, "triage_findings", _fake_triage)

    async def _fake_narrative(name, digest):
        return "## Resumen ejecutivo\n\nFirma con MD5.\n\n## Riesgos prioritarios\n\n### Sesiones\n**Qué es:** MD5."

    monkeypatch.setattr(audit_report, "_client_narrative", _fake_narrative)

    async def _fake_catador(name, narrative, evidence):
        corrected = narrative.replace("MD5", "SHA1")
        return corrected, ["Corregido 'MD5' -> 'SHA1' (el código usa hashlib.sha1)."]

    monkeypatch.setattr(audit_report, "_catador_review", _fake_catador)

    result = await audit_report._generate_client_report_linear(str(project))

    assert any("SHA1" in c for c in result["catador_corrections"])
    note = vault.read_note(result["note_id"])
    # La narrativa corregida (todo lo previo a la sección del Catador) ya no dice MD5;
    # la nota de transparencia del Catador sí puede mencionarlo al explicar la corrección.
    assert "MD5" not in note.content.split("## Verificación (Catador)")[0]
    assert "Verificación (Catador)" in note.content
    assert "hashlib.sha1" in note.content


@pytest.mark.anyio
async def test_client_report_cae_al_lineal_si_la_brigada_falla(project, monkeypatch):
    from app.harness import audit_brigade

    async def _brigada_rota(path):
        raise RuntimeError("brigada caída")

    async def _lineal(path):
        return {"pipeline": "lineal", "project": path}

    monkeypatch.setattr(audit_brigade, "run_audit_brigade", _brigada_rota)
    monkeypatch.setattr(audit_report, "_generate_client_report_linear", _lineal)

    result = await audit_report.generate_client_report(str(project))

    assert result["pipeline"] == "lineal"
