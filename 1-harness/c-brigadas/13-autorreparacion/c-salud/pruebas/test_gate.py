"""Puerta de la brigada: contrato del harness, ningún import ajeno y NINGUNA escritura sin su nivel.

(a) todo `Action("x")` del código está declarado con nivel en el manifiesto (y todo lo declarado se usa);
(b) escribir y revertir código quedan pendientes y no tienen efecto hasta que la persona decide;
(c) los comandos que escriben o aplican los rechaza el harness si los pide el orquestador;
(d) lo `irreversible` nunca baja solo a automático por confianza progresiva;
(e) los dos manifiestos (el del paquete y el de desarrollo) son idénticos;
(f) la brigada no corre en la nube.
"""

from __future__ import annotations

import ast
import sys

import pytest
from kit import BRIGADE_DIR, FIX, System, make_project
from raphael_core import ActionError, Level
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_selfrepair"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED_IMPORTS = {"raphael_core", "raphael_selfrepair", "pydantic", "__future__"}


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), \
        "correr scripts/sync_manifest.py"


def test_suite_de_contrato_en_personal(tmp_path):
    r = run_contract_suite(BRIGADE_DIR, edition="personal", config={"root": str(make_project(tmp_path))})
    assert r.ok, r.text()


def test_suite_de_contrato_sin_raiz():
    r = run_contract_suite(BRIGADE_DIR, edition="personal", config={})
    assert r.ok, r.text()


def test_no_corre_en_la_nube():
    r = run_contract_suite(BRIGADE_DIR, edition="cloud", config={})
    assert not r.ok and any(c.name == "corre en la edición" and not c.ok for c in r.checks)


def test_solo_importa_el_nucleo_y_la_stdlib():
    bad = []
    stdlib = set(sys.stdlib_module_names)
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for n in names:
                top = n.split(".")[0]
                if top not in stdlib and top not in ALLOWED_IMPORTS:
                    bad.append(f"{f.name}: {n}")
    assert not bad, bad


def _used_action_types() -> set[str]:
    used: set[str] = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action" and node.args:
                a = node.args[0]
                if isinstance(a, ast.Constant):
                    used.add(a.value)
                elif isinstance(a, ast.Name):            # APPLY / REVERT, definidas como constantes del módulo
                    for n2 in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                        if isinstance(n2, ast.Assign) and any(getattr(t, "id", None) == a.id or
                                                               (isinstance(t, ast.Tuple) and a.id in [e.id for e in t.elts])
                                                               for t in n2.targets):
                            v = n2.value
                            if isinstance(v, ast.Tuple):
                                idx = [e.id for e in n2.targets[0].elts].index(a.id)
                                used.add(v.elts[idx].value)
                            elif isinstance(v, ast.Constant):
                                used.add(v.value)
    return used


def test_toda_accion_usada_esta_declarada_y_viceversa():
    used = _used_action_types()
    assert used == set(MANIFEST.actions), (used, set(MANIFEST.actions))


def test_escribir_codigo_es_aprobacion_e_irreversible():
    for name in ("aplicar_arreglo", "revertir_arreglo"):
        spec = MANIFEST.actions[name]
        assert spec.level is Level.APPROVAL
        assert "irreversible" in spec.tags
    assert not any(s.level is Level.AUTO for s in MANIFEST.actions.values())


def test_aplicar_deja_pendiente_y_no_escribe(tmp_path):
    root = make_project(tmp_path)
    s = System(root)
    pid = s.cmd("proponer", "proponer", FIX)["id"]
    before = (root / "app" / "calc.py").read_text()
    res = s.cmd("aplicar", "aplicar", {"proposal_id": pid})
    assert res["state"] == "pending" and res["level"] == "aprobacion"
    assert (root / "app" / "calc.py").read_text() == before
    assert len(s.pending()) == 1


def test_el_orquestador_no_puede_pedir_comandos_que_escriben(tmp_path):
    s = System(make_project(tmp_path))
    for name in ("proponer", "redactar", "aplicar", "revertir", "descartar", "analizar", "reflexionar"):
        cook = {"proponer": "proponer", "redactar": "proponer", "descartar": "proponer", "aplicar": "aplicar",
                "revertir": "aplicar"}.get(name, "introspeccion")
        with pytest.raises(ActionError):
            s.cmd(cook, name, {}, who="orquestador")


def test_el_orquestador_si_puede_leer(tmp_path):
    s = System(make_project(tmp_path))
    assert s.cmd("proponer", "propuestas", {}, who="orquestador") == []
    assert s.cmd("introspeccion", "hallazgos", {}, who="orquestador") == []
    assert "lineas_rojas" in s.cmd("introspeccion", "autoconocimiento", {}, who="orquestador")


def test_la_confianza_progresiva_no_baja_aplicar_a_automatico(tmp_path):
    root = make_project(tmp_path)
    s = System(root, trust={"enabled": True, "approvals_to_step_down": 3})
    for i in range(4):
        old = "    return sum(items)\n" if i % 2 else "    return sum(items) + 1\n"
        new = "    return sum(items) + 1\n" if i % 2 else "    return sum(items)\n"
        pid = s.cmd("proponer", "proponer", {**FIX, "old_snippet": old, "new_snippet": new})["id"]
        s.cmd("aplicar", "aplicar", {"proposal_id": pid})
        s.approve(s.pending()[-1]["id"])
    pid = s.cmd("proponer", "proponer", {**FIX, "new_snippet": "    return sum(items) + 2\n"})["id"]
    res = s.cmd("aplicar", "aplicar", {"proposal_id": pid})
    assert res["state"] == "pending"
