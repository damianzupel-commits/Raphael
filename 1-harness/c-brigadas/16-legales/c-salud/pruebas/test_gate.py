"""Puerta: contrato del harness, ningún import ajeno, y NINGUNA acción con efecto sin su nivel."""

from __future__ import annotations

import ast
import sys

import pytest
from kit import BRIGADE_DIR, FULL
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_legales"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED_IMPORTS = {"raphael_core", "raphael_legales", "pydantic", "yaml", "__future__"}


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), \
        "copiar b-codigo/manifest.yaml a src/raphael_legales/manifest.yaml"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition):
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config=FULL)
    assert r.ok, r.text()


def test_solo_importa_el_nucleo_y_la_stdlib():
    bad = []
    stdlib = set(sys.stdlib_module_names)
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for n in names:
                top = n.split(".")[0]
                if top not in ALLOWED_IMPORTS and top not in stdlib:
                    bad.append(f"{f.name}:{node.lineno} importa {n}")
    assert not bad, bad


def _action_literals() -> set[str]:
    found = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) and node.left.attr == "type":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_toda_accion_del_codigo_esta_declarada_con_nivel_y_viceversa():
    used = _action_literals()
    assert used - set(MANIFEST.actions) == set()
    assert set(MANIFEST.actions) - used == set()
    for name, spec in MANIFEST.actions.items():
        assert spec.level is not None and spec.description, name


def test_lo_irreversible_pide_aprobacion_y_nada_firma_ni_envia():
    for a in ("emitir_documento", "borrar_registro"):
        spec = MANIFEST.actions[a]
        assert spec.level.value == "aprobacion" and "irreversible" in spec.tags
    assert not [a for a in MANIFEST.actions if any(w in a for w in ("enviar", "firmar", "presentar", "pagar", "publicar"))]


def test_las_acciones_automaticas_no_salen_al_mundo():
    for a, spec in MANIFEST.actions.items():
        if spec.level.value == "automatico":
            assert not set(spec.tags) & {"external", "spend", "irreversible"}, a


def test_el_codigo_no_lee_claves_ni_manda_mensajes():
    text = "\n".join(f.read_text(encoding="utf-8") for f in _py_files())
    assert "send(" not in text and ".write(" not in text and "API_KEY" not in text
