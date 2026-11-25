"""Puerta de la brigada: contrato del harness, ningún import ajeno y NINGUNA acción con efecto sin su nivel.

(a) todo `Action("x")` del código está declarado en el manifiesto (y todo lo declarado se usa);
(b) publicar, subir y activar anuncios y grabar pantalla NUNCA son automáticos, y los que gastan o no tienen vuelta atrás llevan su etiqueta;
(c) los dos manifiestos (paquete y desarrollo) son idénticos;
(d) la plantilla de claves lista todas las variables de entorno que la brigada lee.
"""

from __future__ import annotations

import ast

import pytest
from kit import BRIGADE_DIR
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_contenido"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED = {"raphael_core", "raphael_contenido", "pydantic", "yaml", "httpx", "__future__"}
STDLIB = set(__import__("sys").stdlib_module_names)


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), "correr scripts/sync_manifest.py"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition):
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config={"mode": "mock"})
    assert r.ok, r.text()


def test_solo_importa_el_nucleo_y_la_stdlib():
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for m in mods:
                root = m.split(".")[0]
                assert root in ALLOWED or root in STDLIB or root == "imageio_ffmpeg" or root == "faster_whisper", f"{f.name} importa {m}"


def _action_names():
    names = set()
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                names.add(node.args[0].value)
    return names


def test_toda_accion_pedida_esta_declarada():
    assert _action_names() <= set(MANIFEST.actions)


def test_todo_lo_declarado_tiene_quien_lo_ejecute():
    texto = "".join(f.read_text(encoding="utf-8") for f in (SRC / "cooks").glob("*.py"))
    for a in MANIFEST.actions:
        assert f'"{a}"' in texto, f"{a} está declarada pero ningún cocinero la ejecuta"


def test_lo_que_sale_al_mundo_o_gasta_nunca_es_automatico():
    a = MANIFEST.actions
    for name in ("publicar_instagram", "subir_campana_pausada", "activar_campana", "grabar_pantalla"):
        assert a[name].level.value == "aprobacion", name
    assert {"external", "irreversible"} <= set(a["publicar_instagram"].tags)
    assert {"spend"} <= set(a["activar_campana"].tags)
    # lo que SÍ es automático no toca el mundo: nada con etiqueta external/spend/irreversible
    for name, spec in a.items():
        if spec.level.value == "automatico":
            assert not spec.tags, f"{name} es automática pero tiene etiquetas de riesgo"


def test_la_plantilla_de_claves_lista_todas_las_variables():
    from raphael_contenido.entorno import VARIABLES
    tpl = (BRIGADE_DIR / ".env.plantilla").read_text(encoding="utf-8")
    for var in VARIABLES:
        assert f"\n{var}=" in "\n" + tpl, f"falta {var} en .env.plantilla"
    assert not [ln for ln in tpl.splitlines() if "=" in ln and not ln.startswith("#") and ln.split("=", 1)[1].strip()], "la plantilla no lleva valores"
