"""Tests de la convergencia: generate_client_report DELEGA en la brigada, y cae
al pipeline lineal si la brigada no completa o falla. Con fakes, sin LLM/vault.
"""

from __future__ import annotations

import asyncio

import app.audit_report as ar
import app.harness.audit_brigade as brig_mod


def _run(coro):
    return asyncio.run(coro)


def test_delega_en_la_brigada(monkeypatch):
    async def fake_brig(path):
        return {
            "ok": True,
            "run_summary": {"ok": 7},
            "report": {
                "note_id": "n1", "note_title": "T", "content": "CONTENIDO",
                "security_findings_real": 5, "false_positives": 2,
                "nonproduction_findings": 1, "catador_corrections": ["sacó SQLi inventada"],
            },
        }

    monkeypatch.setattr(brig_mod, "run_audit_brigade", fake_brig)
    out = _run(ar.generate_client_report("/tmp/whatever"))
    assert out["pipeline"] == "brigada"
    assert out["note_id"] == "n1"
    assert out["security_findings_real_after_triage"] == 5
    assert out["catador_corrections"] == ["sacó SQLi inventada"]
    assert out["content_preview"] == "CONTENIDO"


def test_cae_al_lineal_si_la_brigada_no_completa(monkeypatch):
    async def fake_brig(path):
        return {"ok": False, "run_summary": {}, "report": {}}

    async def fake_linear(path):
        return {"note_id": "linear", "pipeline": "lineal"}

    monkeypatch.setattr(brig_mod, "run_audit_brigade", fake_brig)
    monkeypatch.setattr(ar, "_generate_client_report_linear", fake_linear)
    out = _run(ar.generate_client_report("/tmp/whatever"))
    assert out["note_id"] == "linear"


def test_cae_al_lineal_si_la_brigada_tira(monkeypatch):
    async def fake_brig(path):
        raise RuntimeError("brigada explotó")

    async def fake_linear(path):
        return {"note_id": "linear", "pipeline": "lineal"}

    monkeypatch.setattr(brig_mod, "run_audit_brigade", fake_brig)
    monkeypatch.setattr(ar, "_generate_client_report_linear", fake_linear)
    out = _run(ar.generate_client_report("/tmp/whatever"))
    assert out["note_id"] == "linear"


def test_propaga_error_de_uso_real(monkeypatch):
    async def fake_brig(path):
        raise ValueError("No hay escaneos guardados")

    monkeypatch.setattr(brig_mod, "run_audit_brigade", fake_brig)
    try:
        _run(ar.generate_client_report("/tmp/whatever"))
        assert False, "debería propagar ValueError"
    except ValueError:
        pass
