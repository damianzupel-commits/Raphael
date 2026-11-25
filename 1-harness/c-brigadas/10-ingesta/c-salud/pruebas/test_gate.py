"""Puerta de la brigada: contrato del harness, ningún import ajeno y NINGUNA acción con efecto sin su nivel.

(a) todo `Action("x")` del código está declarado con nivel en el manifiesto (y todo lo declarado se usa);
(b) lo que deja la brigada trabajando sola o borra queda pendiente y no tiene efecto hasta que la persona decide;
(c) los comandos de escritura los rechaza el harness si los pide el orquestador;
(d) los dos manifiestos (el del paquete y el de desarrollo) son idénticos;
(e) ningún cocinero importa a otra brigada y solo se importa lo permitido.
"""

from __future__ import annotations

import ast
import sys

import pytest
from kit import BRIGADE_DIR, MINIMAL, URL_LIST, System
from raphael_core import ActionError
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_ingesta"
MANIFEST = load_manifest(SRC / "manifest.yaml")
# yt_dlp se importa solo adentro del adaptador real de YouTube (opcional); httpx solo en los reales de web y arXiv.
ALLOWED_IMPORTS = {"raphael_core", "raphael_ingesta", "httpx", "yt_dlp", "__future__"}


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), "correr scripts/sync_manifest.py"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition):
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config=MINIMAL)
    assert r.ok, r.text()


def test_solo_importa_el_nucleo_y_la_stdlib():
    bad = []
    stdlib = set(sys.stdlib_module_names)
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
                if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                else []
            )
            for n in names:
                top = n.split(".")[0]
                if top not in ALLOWED_IMPORTS and top not in stdlib:
                    bad.append(f"{f.name}:{node.lineno} importa {n}")
    assert not bad, bad


def _action_literals() -> set[str]:
    found = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "Action"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                found.add(node.args[0].value)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "t":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) and node.left.attr == "type":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_toda_accion_del_codigo_esta_declarada_con_nivel_y_viceversa():
    used = _action_literals()
    assert used - set(MANIFEST.actions) == set(), "acciones sin declarar en el manifiesto"
    assert set(MANIFEST.actions) - used == set(), "acciones declaradas que el código no usa"
    for name, spec in MANIFEST.actions.items():
        assert spec.level is not None and spec.description, name


def test_lo_irreversible_esta_etiquetado_y_pide_aprobacion():
    assert "irreversible" in MANIFEST.actions["borrar_nota"].tags
    assert MANIFEST.actions["borrar_nota"].level.value == "aprobacion"
    assert MANIFEST.actions["vigilar"].level.value == "aprobacion"


NOT_AUTO = sorted(a for a, s in MANIFEST.actions.items() if s.level.value != "automatico")
DATA = {"vigilar": ("youtube", {"ref": URL_LIST}), "borrar_nota": ("youtube", {"id": "youtube:MOCKVID0001"})}


@pytest.mark.parametrize("kind", NOT_AUTO)
def test_ninguna_accion_no_automatica_se_ejecuta_sin_ok(kind, tmp_path):
    x = System(vault=tmp_path)
    x.act("youtube", "ingerir_video", {"ref": "MOCKVID0001"})  # para que haya algo que borrar
    cook, data = DATA[kind]
    res = x.act(cook, kind, data)
    assert res["state"] == "pending"
    assert len(x.pending(kind)) == 1
    assert [e for e in x.rt.audit.entries() if e["what"] == "accion_ejecutada" and e.get("tipo") == kind] == []
    assert len(x.notes()) == 1 and x.ctx("youtube").shared.list("vigiladas") == []
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_el_orquestador_solo_corre_comandos_de_lectura():
    x = System()
    assert all(s.read for s in MANIFEST.commands.values())  # hoy todos son de lectura
    assert x.cmd("youtube", "estado", who="orquestador")["notas"] == 0
    with pytest.raises(ActionError):
        x.cmd("youtube", "borrar_todo", who="orquestador")  # no declarado: lo rechaza el harness
