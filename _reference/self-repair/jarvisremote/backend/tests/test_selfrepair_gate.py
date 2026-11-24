"""Tests del interruptor maestro del autorediseño (SELF_REDESIGN_ENABLED) wireado
en app/tools/selfrepair.py::selfrepair_propose_fix (2026-10-06).

Verifican la intención de Damian: "dejalo siempre encendido, que siempre me
pregunte antes de cambiar algo":
  - APAGADO -> ni siquiera se puede proponer.
  - ENCENDIDO -> se puede proponer, PERO las líneas rojas (config/auth/gate/.env/
    authorized_targets) siguen bloqueadas aunque el flag esté on.
"""

from app.config import settings
from app.tools import selfrepair


def test_autorediseno_apagado_bloquea_toda_propuesta(monkeypatch):
    monkeypatch.setattr(settings, "self_redesign_enabled", False)
    r = selfrepair.selfrepair_propose_fix(
        file="app/agent.py", old_snippet="x", new_snippet="y",
        rationale="test", commit_message="test",
    )
    assert r["proposal_id"] is None
    assert "deshabilitado" in r["error"].lower()


def test_autorediseno_encendido_igual_respeta_lineas_rojas(monkeypatch):
    monkeypatch.setattr(settings, "self_redesign_enabled", True)
    monkeypatch.setattr(settings, "self_protected_paths",
                        "authorized_targets.yaml,app/selfrepair/gate.py,app/auth.py,.env,app/config.py")
    r = selfrepair.selfrepair_propose_fix(
        file="app/config.py", old_snippet="x", new_snippet="y",
        rationale="test", commit_message="test",
    )
    # El flag ON no habilita tocar una línea roja: sigue bloqueado.
    assert r.get("linea_roja") is True
    assert r["proposal_id"] is None
