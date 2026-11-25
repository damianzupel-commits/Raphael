"""Salud: solo da mal lo que de verdad rompe la brigada (config inválida); lo demás es aviso."""

import pytest
from kit import B, System, answers, make_project
from pydantic import ValidationError

from raphael_selfrepair.config import repair_config


def test_config_invalida_no_monta(tmp_path):
    with pytest.raises(AssertionError, match="min_repeats"):
        System(make_project(tmp_path), {"min_repeats": 1})


def test_config_con_campos_desconocidos_no_valida():
    with pytest.raises(ValidationError, match="foo"):
        repair_config({"foo": 1})


def test_monta_sin_raiz_ni_modelo(tmp_path, monkeypatch):
    monkeypatch.delenv("RAPHAEL_REPAIR_ROOT", raising=False)
    s = System(None)
    assert B in s.rt.brigades


def test_aviso_de_lo_que_falta(tmp_path, monkeypatch):
    from raphael_selfrepair.health import check
    monkeypatch.delenv("RAPHAEL_REPAIR_ROOT", raising=False)
    h = check(System(None).ctx("proponer"))
    assert h.ok and "RAPHAEL_REPAIR_ROOT" in h.detail and "sin modelo" in h.detail and "verificación" in h.detail


def test_sin_avisos_con_todo(tmp_path):
    from kit import PY_OK

    from raphael_selfrepair.health import check
    s = System(make_project(tmp_path, git=True), {"git_commit": True, "verify_command": PY_OK}, transport=answers([]))
    h = check(s.ctx("proponer"))
    assert h.ok and h.detail == "ok"
