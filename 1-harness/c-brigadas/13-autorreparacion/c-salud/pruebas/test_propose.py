"""Proponer arreglo: siempre en seco, con el modelo solo si hay, y sin inventar."""

import pytest
from kit import BUGGY, FIX, System, answers, make_project
from raphael_core import ActionError


def test_proponer_guarda_en_seco(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    r = s.cmd("proponer", "proponer", FIX)
    assert r["id"].startswith("sf-") and r["status"] == "propuesta" and "-    return sum(items) + 1" in r["diff"]
    assert (root / "app" / "calc.py").read_text() == BUGGY                # no escribió nada
    assert s.pending() == []                                              # proponer no pide aprobación: no hay efecto
    assert [p["id"] for p in s.cmd("proponer", "propuestas", {})] == [r["id"]]
    assert s.cmd("proponer", "ver_propuesta", {"proposal_id": r["id"]})["old_snippet"] == FIX["old_snippet"]


def test_sin_razon_no_propone(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="razón"):
        s.cmd("proponer", "proponer", {**FIX, "rationale": " "})


def test_snippet_que_no_existe_no_propone(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="no aparece"):
        s.cmd("proponer", "proponer", {**FIX, "old_snippet": "algo que no está"})


def test_sin_raiz_dice_que_falta(tmp_path, monkeypatch):
    monkeypatch.delenv("RAPHAEL_REPAIR_ROOT", raising=False)
    s = System(None)
    with pytest.raises(ActionError, match="RAPHAEL_REPAIR_ROOT"):
        s.cmd("proponer", "proponer", FIX)


def test_la_raiz_sale_de_la_variable_de_entorno(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    monkeypatch.setenv("RAPHAEL_REPAIR_ROOT", str(root))
    s = System(None)
    assert s.cmd("proponer", "proponer", FIX)["id"]


def test_descartar(tmp_path):
    s = System(make_project(tmp_path))
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    assert s.cmd("proponer", "descartar", {"proposal_id": pid})["status"] == "descartada"
    with pytest.raises(ActionError, match="descartada"):
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})
    with pytest.raises(ActionError):
        s.cmd("proponer", "descartar", {"proposal_id": pid})


def test_id_inventado(tmp_path):
    s = System(make_project(tmp_path))
    for bad in ("sf-00000000", "../x", "", None):
        with pytest.raises(ActionError):
            s.cmd("proponer", "ver_propuesta", {"proposal_id": bad})


def test_redactar_sin_modelo_no_inventa(tmp_path):
    s = System(make_project(tmp_path))
    with pytest.raises(ActionError, match="modelo"):
        s.cmd("proponer", "redactar", {"file": "app/calc.py", "problem": "suma de más"})
    assert s.cmd("proponer", "propuestas", {}) == []


def test_redactar_con_modelo_guarda_la_propuesta(tmp_path):
    root = make_project(tmp_path)
    resp = {"old_snippet": FIX["old_snippet"], "new_snippet": FIX["new_snippet"], "rationale": "sumaba 1 de más"}
    s = System(root, transport=answers(["Acá va:\n```json\n" + __import__("json").dumps(resp) + "\n```"]))
    r = s.cmd("proponer", "redactar", {"file": "app/calc.py", "problem": "el total da 1 de más", "finding_id": "hz-1"})
    assert r["status"] == "propuesta" and r["finding_id"] == "hz-1"
    assert (root / "app" / "calc.py").read_text() == BUGGY


@pytest.mark.parametrize("reply", ["no sé", "{not json", {"old_snippet": "", "new_snippet": "", "rationale": "no puedo"},
                                   {"old_snippet": "texto inexistente", "new_snippet": "x", "rationale": "r"}])
def test_redactar_con_respuesta_mala_no_guarda(tmp_path, reply):
    s = System(make_project(tmp_path), transport=answers([reply]))
    with pytest.raises(ActionError):
        s.cmd("proponer", "redactar", {"file": "app/calc.py", "problem": "x"})
    assert s.cmd("proponer", "propuestas", {}) == []


def test_redactar_un_protegido_ni_llama_al_modelo(tmp_path):
    seen = []
    s = System(make_project(tmp_path), transport=lambda *a: seen.append(a) or {})
    with pytest.raises(ActionError, match="LÍNEA ROJA"):
        s.cmd("proponer", "redactar", {"file": "app/auth.py", "problem": "x"})
    assert seen == []


def test_ai_private_sin_modelo_local_no_manda_el_codigo_a_la_nube(tmp_path):
    seen = []
    s = System(make_project(tmp_path), {"ai_private": True}, transport=lambda *a: seen.append(a) or {})
    with pytest.raises(ActionError, match="modelo"):
        s.cmd("proponer", "redactar", {"file": "app/calc.py", "problem": "x"})
    assert seen == []
