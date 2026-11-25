"""Puerta de la brigada: contrato del harness, ningún import ajeno y NINGUNA acción con efecto sin su nivel.

(a) todo `Action("x")` del código está declarado con nivel en el manifiesto (y todo lo declarado se usa);
(b) cada acción no automática queda pendiente y no tiene efecto hasta que la persona decide;
(c) los comandos de escritura los rechaza el harness si los pide el orquestador;
(d) lo `irreversible` nunca baja solo a automático por confianza progresiva;
(e) los dos manifiestos (el del paquete y el de desarrollo) son idénticos;
(f) ninguna brigada importa a otra.
"""

from __future__ import annotations

import ast
import sys

import pytest
from kit import BRIGADE_DIR, System
from raphael_core import Action, ActionError
from raphael_core.manifest import load_manifest
from raphael_core.testing import find_cross_imports
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_memoria"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED_IMPORTS = {"raphael_core", "raphael_memoria", "pydantic", "httpx", "yaml", "__future__"}


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), \
        "copiar src/raphael_memoria/manifest.yaml a b-codigo/manifest.yaml"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition, tmp_path):
    cfg = {"vault": {"path": str(tmp_path / "vault")}, "embeddings": {"provider": "mock"}}
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config=cfg)
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


def test_ninguna_brigada_hermana_se_importa():
    assert find_cross_imports(SRC, ["empresas", "raphael_empresas", "raphael_orchestrator", "raphael_seguridad",
                                               "raphael_investigacion"]) == []


def _action_literals() -> set[str]:
    found = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "request" and len(node.args) >= 2 \
                    and isinstance(node.args[1], ast.Constant):
                found.add(node.args[1].value)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "t":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_toda_accion_del_codigo_esta_declarada_con_nivel_y_viceversa():
    used = _action_literals()
    assert used - set(MANIFEST.actions) == set(), "acciones sin declarar en el manifiesto"
    assert set(MANIFEST.actions) - used == set(), "acciones declaradas que el código no usa"
    for name, spec in MANIFEST.actions.items():
        assert spec.level is not None and spec.description, name


def test_lo_que_borra_o_exporta_o_escribe_con_modelo_pide_aprobacion():
    lv = {a: s.level.value for a, s in MANIFEST.actions.items()}
    assert lv["olvidar"] == lv["consolidar"] == lv["exportar_vault"] == "aprobacion"
    assert "irreversible" in {t.value if hasattr(t, "value") else t for t in MANIFEST.actions["olvidar"].tags}


def test_los_comandos_de_escritura_no_son_de_lectura():
    reads = {n: c.read for n, c in MANIFEST.commands.items()}
    for w in ("guardar", "consolidar", "reindexar", "olvidar", "exportar", "feedback", "pasada"):
        assert reads[w] is False, w
    for r in ("recordar", "buscar", "asociar", "analogias", "componer", "curiosidad", "consolidar_vista", "episodios"):
        assert reads[r] is True, r


def test_todo_comando_declarado_existe_en_algun_cocinero(tmp_path):
    x = System(tmp_path)
    ofrecidos = {n for c in x.rt.brigades["memoria"].cooks.values() for n in c.commands}
    assert set(MANIFEST.commands) <= ofrecidos, set(MANIFEST.commands) - ofrecidos


def test_el_orquestador_no_puede_correr_comandos_de_escritura(tmp_path):
    x = System(tmp_path)
    with pytest.raises(ActionError, match="solo corre comandos declarados de lectura"):
        x.cmd("consolidador", "guardar", {"title": "a", "content": "b"}, who="orquestador")
    assert x.cmd("recuperador", "notas", who="orquestador") == []


def test_lo_que_no_es_automatico_queda_pendiente_y_no_tiene_efecto(tmp_path):
    x = System(tmp_path)
    x.save("Nota uno", "contenido uno")
    r = x.cmd("consolidador", "olvidar", {"kind": "nota", "id": "jarvis/nota-uno"})
    assert r["estado"] == "pending"
    assert (x.vault / "jarvis" / "nota-uno.md").exists()           # sigue ahí hasta que decida la persona
    [p] = x.pending("olvidar")
    assert p["level"] == "aprobacion"
    x.approve(p["id"])
    assert not (x.vault / "jarvis" / "nota-uno.md").exists()


def test_rechazar_deja_todo_como_estaba(tmp_path):
    x = System(tmp_path)
    x.save("Nota uno", "contenido uno")
    x.cmd("consolidador", "olvidar", {"kind": "nota", "id": "jarvis/nota-uno"})
    x.reject(x.pending("olvidar")[0]["id"], "mejor no")
    assert (x.vault / "jarvis" / "nota-uno.md").exists()


def test_lo_irreversible_no_baja_solo_a_automatico(tmp_path):
    x = System(tmp_path, autonomy={"memoria.olvidar": "automatico"})
    assert x.rt.policy.decide("memoria", "olvidar").level.value == "aprobacion"
    assert any("olvidar" in w and "se ignora" in w for w in x.rt.warnings)


def test_una_accion_no_declarada_se_rechaza(tmp_path):
    x = System(tmp_path)
    r = x.rt.run(x.rt.action("memoria", "consolidador", Action("borrar_todo", {})))
    assert r["state"] != "executed"
