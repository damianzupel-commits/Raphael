"""Puerta: contrato del harness, ningún import ajeno, ninguna acción sin su nivel y ninguna clave en el código."""

import ast
import re

from kit import BRIGADE_DIR, System
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

SRC = BRIGADE_DIR / "src" / "raphael_geolocalizacion"
MANIFEST = load_manifest(SRC / "manifest.yaml")
PERMITIDOS = {"raphael_core", "raphael_geolocalizacion", "__future__", "websockets"}
STDLIB = {"asyncio", "builtins", "collections", "ipaddress", "json", "os", "re", "time", "urllib", "uuid"}


def _py():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), "correr scripts/sync_manifest.py"


def test_suite_de_contrato():
    r = run_contract_suite(BRIGADE_DIR, edition="personal", config={"modo": "simulado"})
    assert r.ok, r.text()


def test_matriz_con_las_otras_brigadas_no_aplica_pero_ningun_import_ajeno():
    malos = []
    for f in _py():
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                mods = [n.module or ""]
            for m in mods:
                if m.split(".")[0] not in PERMITIDOS | STDLIB:
                    malos.append(f"{f.name}: {m}")
    assert not malos, malos


def test_toda_accion_declarada_se_usa_y_toda_usada_esta_declarada():
    usadas = set()
    for f in _py():
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            es_action = isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Action"
            if es_action and n.args and isinstance(n.args[0], ast.Constant):
                usadas.add(n.args[0].value)
    assert usadas == set(MANIFEST.actions)
    assert all(MANIFEST.actions[a].level.value == "aprobacion" for a in usadas)


def test_ningun_comando_de_escritura_y_los_de_lectura_existen():
    cocineros = System().rt.brigades["geolocalizacion"].cooks
    ofrecidos = {c for k in cocineros.values() for c in k.commands}
    assert ofrecidos == set(MANIFEST.commands) and all(c.read for c in MANIFEST.commands.values())


def test_no_hay_claves_escritas_en_el_codigo_ni_en_la_plantilla():
    patron = re.compile(r"(?:KEY|TOKEN)\s*=\s*['\"]?[A-Za-z0-9_\-]{16,}")
    for f in [*_py(), BRIGADE_DIR / "geolocalizacion.env.plantilla"]:
        assert not patron.search(f.read_text(encoding="utf-8")), f.name
    for linea in (BRIGADE_DIR / "geolocalizacion.env.plantilla").read_text(encoding="utf-8").splitlines():
        if re.match(r"^[A-Z_]+=", linea):
            assert linea.split("=", 1)[1].strip() == "", linea


def test_la_plantilla_lista_todas_las_variables_que_lee_el_codigo():
    from raphael_geolocalizacion.claves import CLAVES
    plantilla = (BRIGADE_DIR / "geolocalizacion.env.plantilla").read_text(encoding="utf-8")
    for var, _d in CLAVES.values():
        assert f"\n{var}=" in plantilla
    assert "OPENCELLID_BBOX=" in plantilla and "RAPHAEL_GEO_MODO" in plantilla
