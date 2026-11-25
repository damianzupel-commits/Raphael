"""Contrato del harness, ningún import ajeno y NINGUNA acción con efecto sin su nivel."""

from __future__ import annotations

import ast

import pytest
from kit import BRIGADE_DIR
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_trading"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED = {"raphael_core", "raphael_trading", "pydantic", "httpx", "yaml", "__future__"}
STDLIB = __import__("sys").stdlib_module_names


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes()


def test_suite_de_contrato_personal():
    r = run_contract_suite(BRIGADE_DIR, edition="personal")
    assert r.ok, r.text()


def test_no_se_monta_en_la_nube():
    r = run_contract_suite(BRIGADE_DIR, edition="cloud")
    assert not r.ok   # Trading solo corre en la PC de Damián


def test_ningun_import_de_otra_brigada():
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for m in mods:
                top = m.split(".")[0]
                assert top in ALLOWED or top in STDLIB, f"{f.name} importa {m}"


def test_toda_accion_usada_esta_declarada_y_toda_declarada_se_usa():
    used = set()
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                used.add(node.args[0].value)
    declared = set(MANIFEST.actions)
    assert used <= declared, used - declared
    assert declared <= used | {"ejecutar_orden"}, declared - used   # ejecutar_orden se arma en _order_action


def test_ejecutar_y_cerrar_piden_aprobacion_y_nunca_son_automaticos():
    for name in ("ejecutar_orden", "cerrar_posicion"):
        a = MANIFEST.actions[name]
        assert a.level.value == "aprobacion"
        assert {"spend", "irreversible"} <= set(a.tags)


@pytest.mark.parametrize("cmd", ["agregar", "quitar", "escanear", "proponer", "cerrar", "pausar", "reanudar"])
def test_comandos_que_escriben_no_son_de_lectura(cmd):
    assert MANIFEST.commands[cmd].read is False
