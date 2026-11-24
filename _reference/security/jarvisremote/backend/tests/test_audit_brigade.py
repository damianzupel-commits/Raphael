"""Test de la brigada de auditoría ensamblada como DAG (Fase C).

Usa las estaciones REALES pero les inyecta fakes en las llamadas externas
(escáner, triage con LLM, narrativa con LLM, catador con LLM, guardado en vault),
así se ejercita toda la lógica real de merge/split/contexto/ensamblado sin tocar
LLM ni escáneres. Sync-envuelto para correr bajo pytest sin plugins.
"""

from __future__ import annotations

import asyncio

from app.findings.models import Finding, make_finding_id
from app.harness import audit_brigade as brig
from app.harness.audit_brigade import (
    E1, E2, E3, E4, E5, E6, E7,
    AssembleStation, CatadorStation, ConfigStation, ContextStation,
    NarrativeStation, ScanStation, TriageStation, run_audit_brigade,
)


def _finding(file, rule="B324", sev="high", tool="bandit", status=None):
    return Finding(
        id=make_finding_id(tool, file, 1, rule),
        tool=tool, file=file, line=1, end_line=None,
        severity=sev, rule_id=rule, message="msg de prueba",
        triage_status=status,
    )


class _FakeScan:
    def __init__(self, findings):
        self.findings = findings
        self.scanned_at = "2026-09-20T00:00:00Z"
        self.tools_run = ["bandit"]


class _FakeNote:
    id = "note-123"
    title = "Reporte de prueba"


def _fake_stations():
    prod = _finding("app/main.py", rule="B324", sev="high")
    nonprod = _finding("tests/test_x.py", rule="B105", sev="medium")
    cfg = _finding("settings.py", rule="CFG001-debug-true", sev="high", tool="config-check", status="real")

    async def fake_triage(root, findings, llm=None, model=None):
        return findings  # no cambia nada (todos siguen reales)

    async def fake_narrate(project, digest, llm=None, model=None):
        return "## Resumen ejecutivo\n\nRiesgo alto.\n\n## Riesgos prioritarios\n### SQLi\n**Qué es:** x"

    async def fake_review(name, narrative, evidence, llm=None, model=None):
        return narrative, []  # el catador no corrige nada

    return {
        E1: ScanStation(load_sec=lambda root: _FakeScan([prod, nonprod]), load_qual=lambda root: None),
        E4: ConfigStation(scan=lambda root: [cfg]),
        E3: TriageStation(triage_fn=fake_triage),  # split real
        E2: ContextStation(),                       # is_production real
        E5: NarrativeStation(narrate=fake_narrate), # digest real
        E6: CatadorStation(build_evidence=lambda root, fs: "", review=fake_review),
        E7: AssembleStation(save_note=lambda **kw: _FakeNote()),
    }


def test_brigada_corre_de_punta_a_punta(tmp_path):
    result = asyncio.run(run_audit_brigade(str(tmp_path), stations=_fake_stations()))
    assert result["ok"] is True
    # las 7 estaciones corrieron ok
    assert result["run_summary"]["ok"] == 7
    rep = result["report"]
    assert rep["note_id"] == "note-123"
    content = rep["content"]
    # la narrativa fake quedó en el reporte
    assert "Riesgos prioritarios" in content
    # el hallazgo de producción entró como riesgo real
    assert "app/main.py" in content
    # el hallazgo de config (E4) se mergeó y llegó al reporte
    assert "settings.py" in content


def test_e4_config_se_mergea_en_los_hallazgos_reales(tmp_path):
    result = asyncio.run(run_audit_brigade(str(tmp_path), stations=_fake_stations()))
    rep = result["report"]
    # prod (app/main.py) + config (settings.py) = 2 reales de producción; el de tests va aparte
    assert rep["security_findings_real"] == 2
    assert rep["nonproduction_findings"] == 1


def test_contexto_separa_no_produccion(tmp_path):
    # El hallazgo en tests/ NO debe contar como riesgo de producción.
    result = asyncio.run(run_audit_brigade(str(tmp_path), stations=_fake_stations()))
    content = result["report"]["content"]
    # tests/test_x.py aparece en la sección de no-producción, no en los riesgos reales
    assert "tests/test_x.py" in content


def test_scan_sin_escaneos_aborta_limpio(tmp_path):
    stations = _fake_stations()
    stations[E1] = ScanStation(load_sec=lambda root: None, load_qual=lambda root: None)
    result = asyncio.run(run_audit_brigade(str(tmp_path), stations=stations))
    assert result["ok"] is False
    # E1 abortó -> su rama (todo) se corta, no explota
    assert E1 in result["run_summary"]["aborted"]


def test_narrativa_opcional_no_voltea_la_corrida(tmp_path):
    # Si la narrativa (E5) falla, la brigada sigue y arma el reporte mecánico.
    stations = _fake_stations()

    async def narrate_falla(project, digest, llm=None, model=None):
        raise RuntimeError("LLM caído")

    stations[E5] = NarrativeStation(narrate=narrate_falla)
    result = asyncio.run(run_audit_brigade(str(tmp_path), stations=stations))
    # E5 y E6 son best-effort (skip); E7 igual arma el reporte
    assert result["report"].get("content")
    assert "Resumen ejecutivo" in result["report"]["content"]
