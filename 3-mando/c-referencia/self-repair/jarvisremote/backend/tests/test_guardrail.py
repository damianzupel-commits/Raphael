"""Tests del guardrail de líneas rojas del auto-rediseño (app/selfrepair/guardrail.py, Etapa D)."""

from app.selfrepair import guardrail


def test_lineas_rojas_bloqueadas(monkeypatch):
    monkeypatch.setattr(guardrail.settings, "self_protected_paths",
                        "authorized_targets.yaml,app/selfrepair/gate.py,app/auth.py,.env,app/config.py")
    for f in ["backend/authorized_targets.yaml", "app/config.py", "app/selfrepair/gate.py", "app/auth.py", "backend/.env"]:
        assert guardrail.is_protected(f), f
        assert guardrail.check(f) is not None  # devuelve un motivo


def test_codigo_normal_permitido(monkeypatch):
    monkeypatch.setattr(guardrail.settings, "self_protected_paths", "authorized_targets.yaml,app/config.py")
    assert not guardrail.is_protected("app/obsidian/spreading.py")
    assert guardrail.check("app/agent.py") is None  # se puede proponer/aplicar (con confirmación)
