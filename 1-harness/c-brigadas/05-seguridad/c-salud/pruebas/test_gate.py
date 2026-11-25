"""Puerta de la pieza: contrato del harness, ningún import ajeno, ninguna acción sin su nivel y el pentest fuera de la nube."""

from __future__ import annotations

import ast
import sys

import pytest
from kit import BRIGADE_DIR, System
from raphael_core import ActionError
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_seguridad"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED = {"raphael_core", "raphael_seguridad", "httpx", "yaml", "__future__"}


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), "correr scripts/sync_manifest.py"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition):
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config={})
    assert r.ok, r.text()


def test_solo_importa_el_nucleo_y_la_stdlib():
    bad, stdlib = [], set(sys.stdlib_module_names)
    for f in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for n in names:
                if n.split(".")[0] not in ALLOWED and n.split(".")[0] not in stdlib:
                    bad.append(f"{f.name}:{node.lineno} importa {n}")
    assert not bad, bad


def _literals() -> set[str]:
    found = set()
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) and node.left.attr == "type":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_toda_accion_del_codigo_esta_declarada_con_nivel_y_viceversa():
    assert _literals() == set(MANIFEST.actions)
    assert all(s.level is not None and s.description for s in MANIFEST.actions.values())


def test_nada_con_efecto_corre_en_automatico():
    assert {a for a, s in MANIFEST.actions.items() if s.level.value == "automatico"} == set()
    assert "external" in MANIFEST.actions["pentest_corrida"].tags and "irreversible" in MANIFEST.actions["purgar_historial"].tags


def test_las_tools_de_escaneo_activo_no_se_cargan_en_la_nube():
    active = {t.name for t in MANIFEST.tools if t.active_scan}
    assert active == {"nmap_scan", "zap_scan", "sqlmap_scan"}
    assert all(t.level.value == "aprobacion" for t in MANIFEST.tools if t.active_scan)
    cloud = System(edition="cloud")
    assert active.isdisjoint(cloud.rt.tools.names()) and "auditar_proyecto" in cloud.rt.tools.names()
    local = System(edition="personal")
    assert active <= set(local.rt.tools.names())


@pytest.mark.parametrize("cmd", [c for c, s in MANIFEST.commands.items() if not s.read])
def test_el_orquestador_no_corre_comandos_de_escritura(cmd):
    x = System()
    cook = "pentest" if cmd == "pentest_proponer" else "auditor"
    with pytest.raises(ActionError):
        x.cmd(cook, cmd, {}, who="orquestador")


def test_todos_los_comandos_de_los_cocineros_estan_declarados():
    for cid, cook in System().rt.brigades["seguridad"].cooks.items():
        assert set(cook.commands) <= set(MANIFEST.commands), cid


def test_el_jefe_ruta_la_red_al_efimero_de_red():
    from raphael_seguridad.spec import SPEC

    assert SPEC.routing.classify("revisa mi wifi") == "red"
    assert SPEC.routing.classify("auditá el repo") == "auditor"
    assert SPEC.routing.classify("probá zap en mi sitio web") == "web"
    assert {h.mode for h in SPEC.helpers} == {"auditor", "red", "web"}


def test_red_local_da_una_red_privada_o_dice_que_no_pudo():
    import ipaddress

    from raphael_seguridad.tools import local_network

    r = local_network()
    if r["found"]:
        assert ipaddress.ip_network(r["network"]).prefixlen == 24
    else:
        assert r["error"]


def test_el_efimero_de_red_tiene_red_local_y_nmap():
    from raphael_seguridad.spec import RED

    assert RED.tools == {"nmap_scan", "red_local"}
