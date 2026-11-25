"""Aplicar arreglo: solo con aprobación, atado a la propuesta exacta, con verificación y vuelta atrás."""

import subprocess

import pytest
from kit import BUGGY, FIX, PY_FAIL, PY_OK, System, make_project
from raphael_core import ActionError

FIXED = BUGGY.replace("sum(items) + 1", "sum(items)")


def _pedir(s, pid):
    r = s.cmd("aplicar", "aplicar", {"proposal_id": pid})
    assert r["state"] == "pending"
    return r["id"]


def test_camino_feliz(tmp_path):
    root = make_project(tmp_path)
    s = System(root, {"verify_command": PY_OK})
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    pend = _pedir(s, pid)
    assert (root / "app" / "calc.py").read_text() == BUGGY               # hasta aprobar, nada
    res = s.approve(pend)
    assert res["state"] == "executed" and pid in res["text"] and "verificado" in res["text"]
    assert (root / "app" / "calc.py").read_text() == FIXED
    p = s.proposal(pid)
    assert p["status"] == "aplicada" and p["applied_at"]
    assert s.events("arreglo.aplicado")[0][1]["proposal_id"] == pid


def test_rechazar_no_escribe_y_marca_la_propuesta(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.reject(_pedir(s, pid), "no me gusta")
    assert (root / "app" / "calc.py").read_text() == BUGGY
    assert s.proposal(pid)["status"] == "rechazada"
    with pytest.raises(ActionError):
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})


def test_no_se_aplica_dos_veces(tmp_path):
    s = System(make_project(tmp_path))
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.approve(_pedir(s, pid))
    with pytest.raises(ActionError, match="aplicada"):
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})


def test_la_aprobacion_no_sirve_para_otra_propuesta(tmp_path):
    """Aprobar con `changes` que apunten a otro proposal_id no cuela un cambio distinto: la huella no coincide."""
    root = make_project(tmp_path)
    s = System(root)
    a = s.cmd("proponer", "proponer", FIX)["id"]
    b = s.cmd("proponer", "proponer", {**FIX, "new_snippet": "    return 0\n"})["id"]
    pend = _pedir(s, a)
    res = s.approve(pend, {"proposal_id": b})
    assert res["state"] == "error" and "huella" in res["error"]
    assert (root / "app" / "calc.py").read_text() == BUGGY
    assert s.proposal(b)["status"] == "propuesta"


def test_los_snippets_del_pendiente_no_se_usan(tmp_path):
    """La acción lleva solo id y huella: meter snippets en `changes` no cambia lo que se escribe."""
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.approve(_pedir(s, pid), {"old_snippet": "x", "new_snippet": "os.system('rm -rf /')", "file": "app/auth.py"})
    assert (root / "app" / "calc.py").read_text() == FIXED
    assert "SECRET_CHECK = True" in (root / "app" / "auth.py").read_text()


def test_propuesta_adulterada_en_el_almacen_no_se_aplica(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    p = s.proposal(pid)
    p["new_snippet"] = "    return 999\n"                                  # alguien tocó el almacén
    s.ctx("proponer").shared.put("proposals", pid, p)
    with pytest.raises(ActionError, match="consistente"):
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})


def test_si_el_archivo_cambio_despues_de_pedir_no_aplica(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    pend = _pedir(s, pid)
    (root / "app" / "calc.py").write_text("def total(items):\n    return 42\n")
    res = s.approve(pend)
    assert res["state"] == "error" and "ya no aplica" in res["error"]
    assert (root / "app" / "calc.py").read_text() == "def total(items):\n    return 42\n"


def test_si_cambio_antes_de_pedir_tampoco(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    (root / "app" / "calc.py").write_text("otra cosa\n")
    with pytest.raises(ActionError, match="ya no aplica"):
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})
    assert s.pending() == []


def test_verificacion_que_falla_deshace_solo(tmp_path):
    root = make_project(tmp_path)
    s = System(root, {"verify_command": PY_FAIL})
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    res = s.approve(_pedir(s, pid))
    assert res["state"] == "error" and "deshice" in res["error"] and "rompió" in res["error"]
    assert (root / "app" / "calc.py").read_text() == BUGGY
    assert s.proposal(pid)["status"] == "revertida_por_verificacion"
    assert s.events("arreglo.aplicado") == []


def test_revertir_con_aprobacion(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.approve(_pedir(s, pid))
    r = s.cmd("aplicar", "revertir", {"proposal_id": pid})
    assert r["state"] == "pending"
    assert (root / "app" / "calc.py").read_text() == FIXED               # hasta aprobar, sigue aplicado
    res = s.approve(r["id"])
    assert res["state"] == "executed" and "Deshecho" in res["text"]
    assert (root / "app" / "calc.py").read_text() == BUGGY
    assert s.proposal(pid)["status"] == "revertida"
    assert s.events("arreglo.revertido")


def test_revertir_si_el_archivo_cambio_pide_revision_a_mano(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.approve(_pedir(s, pid))
    r = s.cmd("aplicar", "revertir", {"proposal_id": pid})
    (root / "app" / "calc.py").write_text("def total(items):\n    return 7\n")
    res = s.approve(r["id"])
    assert res["state"] == "error" and "a mano" in res["error"]


def test_no_se_revierte_lo_que_no_se_aplico(tmp_path):
    s = System(make_project(tmp_path))
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    with pytest.raises(ActionError, match="solo se revierte una aplicada"):
        s.cmd("aplicar", "revertir", {"proposal_id": pid})


def test_commit_propio_y_revert_en_git(tmp_path):
    root = make_project(tmp_path, git=True)
    s = System(root, {"git_commit": True})
    pid = s.cmd("proponer", "proponer", {**FIX, "commit_message": "fix: total"})["id"]
    s.approve(_pedir(s, pid))
    p = s.proposal(pid)
    assert p["commit"]
    log = subprocess.run(["git", "-C", str(root), "log", "--format=%s", "-2"], capture_output=True, text=True).stdout.split("\n")
    assert log[0] == "fix: total"
    s.approve(s.cmd("aplicar", "revertir", {"proposal_id": pid})["id"])
    last = subprocess.run(["git", "-C", str(root), "log", "--format=%s", "-1"], capture_output=True, text=True).stdout
    assert last.strip() == "revert: fix: total"
    assert (root / "app" / "calc.py").read_text() == BUGGY


def test_dos_propuestas_sobre_el_mismo_archivo(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    a = s.cmd("proponer", "proponer", FIX)["id"]
    b = s.cmd("proponer", "proponer", {"file": "app/calc.py", "old_snippet": "'raphael'", "new_snippet": "'Raphael'",
                                       "rationale": "mayúscula"})["id"]
    s.approve(_pedir(s, a))
    s.approve(_pedir(s, b))
    assert (root / "app" / "calc.py").read_text() == FIXED.replace("'raphael'", "'Raphael'")


def test_la_auditoria_deja_rastro(tmp_path):
    s = System(make_project(tmp_path))
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    s.approve(_pedir(s, pid))
    whats = [e["what"] for e in s.rt.audit.entries()]
    assert {"propuesta_creada", "arreglo_pedido", "aprobado", "arreglo_aplicado"} <= set(whats)
