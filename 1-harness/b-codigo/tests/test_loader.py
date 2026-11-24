"""Cargador de manifiestos: descubrir, armar, montar y desmontar según la instalación (H5)."""

from __future__ import annotations

import json
import textwrap
import uuid
from pathlib import Path

import pytest
import yaml

from raphael_core import Loader, LoadError, Runtime
from raphael_core import loader as L
from raphael_core.installation import installation_from, load_installation
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"


def brigade(root: Path, bid: str, manifest: dict | None = None, code: str = "", pkg: str | None = None) -> str:
    """Una brigada de prueba en `root/<bid>/` con su paquete (nombre único para no chocar en sys.modules)."""
    pkg = pkg or f"brig_{bid.replace('-', '_')}_{uuid.uuid4().hex[:8]}"
    d = root / bid
    (d / pkg).mkdir(parents=True)
    base = {"id": bid, "name": bid.title(), "version": "1.0.0", "contract": ">=2.0,<3",
            "cooks": [{"id": "uno", "entry": f"{pkg}:One"}], "actions": {"hacer": {"level": "automatico"}}}
    base.update(manifest or {})
    (d / "manifest.yaml").write_text(yaml.safe_dump(json.loads(json.dumps(base).replace("PKG", pkg))), encoding="utf-8")
    (d / pkg / "__init__.py").write_text(textwrap.dedent(code or """
        from raphael_core import Cook, Reply
        class One(Cook):
            def interest(self, msg, ctx): return 0.5
            def handle(self, msg, ctx): return Reply("uno")
    """), encoding="utf-8")
    return pkg


def runtime(active=(), edition="personal", configs=None, models=None) -> Runtime:
    inst = installation_from({"id": "t", "edition": edition,
                              "brigades": {b: {"active": True, "config": (configs or {}).get(b, {})} for b in active}})
    return Runtime(inst, clock=Clock(), models=models)


# --- descubrir ----------------------------------------------------------------------------------------------------------
def test_descubre_las_brigadas_de_ejemplo_por_su_manifiesto():
    found, warnings = L.discover([EJEMPLOS], installed=False)
    assert sorted(found) == ["eco", "saludo"] and warnings == []
    assert found["saludo"].source == "folder" and found["saludo"].path.name == "manifest.yaml"


def test_no_entra_a_codigo_actual_ni_carpetas_ocultas_y_avisa_lo_roto(tmp_path):
    brigade(tmp_path / "codigo-actual", "vieja")
    brigade(tmp_path / ".oculta", "oculta")
    brigade(tmp_path / "piezas", "buena")
    (tmp_path / "rota").mkdir()
    (tmp_path / "rota" / "manifest.yaml").write_text("id: Rota!\n", encoding="utf-8")
    brigade(tmp_path / "otra-copia", "buena")
    found, warnings = L.discover([tmp_path], installed=False)
    assert list(found) == ["buena"]
    assert any("manifiesto inválido" in w for w in warnings) and any("aparece dos veces" in w for w in warnings)


def test_la_carpeta_de_desarrollo_puede_venir_de_RAPHAEL_DEV(monkeypatch, tmp_path):
    brigade(tmp_path, "por-env")
    monkeypatch.setenv("RAPHAEL_DEV", str(tmp_path))
    found, _ = L.discover(installed=False)
    assert "por-env" in found


def test_las_brigadas_instaladas_se_encuentran_por_entry_point_y_ganan_a_la_carpeta(monkeypatch, tmp_path):
    pkg = brigade(tmp_path / "inst", "instalada")
    (tmp_path / "inst" / "instalada" / pkg / "manifest.yaml").write_text(
        (tmp_path / "inst" / "instalada" / "manifest.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "inst" / "instalada"))

    class EP:
        name, value = "instalada", pkg

    class Broken:
        name, value = "rota", "no_existe_este_paquete"

    monkeypatch.setattr(L.metadata, "entry_points", lambda group: [EP, Broken] if group == L.GROUP else [])
    brigade(tmp_path / "dev", "instalada")
    found, warnings = L.discover([tmp_path / "dev"])
    assert found["instalada"].source == "installed"
    assert any("rota" in w for w in warnings) and any("aparece dos veces" in w for w in warnings)


# --- armar --------------------------------------------------------------------------------------------------------------
def _found(tmp_path, **kw):
    brigade(tmp_path, "b", **kw)
    return L.discover([tmp_path], installed=False)[0]["b"]


@pytest.mark.parametrize("manifest,code,fragment", [
    ({"contract": ">=3.0"}, "", "pide el contrato"),
    ({"editions": ["cloud"]}, "", "no corre en la edición"),
    ({"config_schema": {"type": "object", "required": ["token"]}}, "", "config inválida"),
    ({"cooks": [{"id": "uno", "entry": "no_existe:Nada"}]}, "", "no se pudo importar"),
    ({"cooks": [{"id": "uno", "entry": "PKG:Falta"}]}, "", "no tiene 'Falta'"),
    ({}, "One = 5\n", "no es una clase Cook"),
    ({}, "from raphael_core import Cook\nclass One(Cook):\n    def __init__(self): raise RuntimeError('x')\n",
     "no se pudo crear"),
    ({"chief": "PKG:SPEC"}, "from raphael_core import Cook\nclass One(Cook): pass\nSPEC = 3\n", "no es un BrigadeSpec"),
    ({"tools": [{"name": "t", "entry": "PKG:T"}]}, "from raphael_core import Cook\nclass One(Cook): pass\nT = 3\n",
     "no es una función"),
])
def test_armar_rechaza_con_el_motivo(tmp_path, manifest, code, fragment):
    f = _found(tmp_path, manifest=manifest, code=code)
    with pytest.raises(LoadError, match=fragment):
        L.build(f, edition="personal")


def test_armar_resuelve_jefe_como_funcion_y_tools_con_esquema_desde_la_firma(tmp_path):
    code = """
        from raphael_core import Cook
        from raphael_core.engine import BrigadeSpec, HelperSpec, RouteRule, Routing
        class One(Cook): pass
        def make_spec():
            return BrigadeSpec(id="b", name="B", purpose="p", prompt="p",
                               helpers=(HelperSpec(mode="m", id="b-m", description="d", tools=frozenset({"buscar"})),),
                               routing=Routing(rules=(), default="m"))
        def buscar(query: str, limit: int = 5, exact: bool = False):
            '''Busca cosas.

            Más detalle.'''
            return {"query": query}
        def scan(target: str): return {}
    """
    f = _found(tmp_path, code=code, manifest={"chief": "PKG:make_spec",
                                              "tools": [{"name": "buscar", "entry": "PKG:buscar"},
                                                        {"name": "scan", "entry": "PKG:scan", "active_scan": True}]})
    b = L.build(f, edition="cloud")
    assert b.chief.id == "b" and [t.name for t in b.tools] == ["buscar"] and "no se carga" in b.warnings[0]
    t = b.tools[0]
    assert t.description == "Busca cosas." and t.parameters == {
        "type": "object", "required": ["query"],
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}, "exact": {"type": "boolean"}}}


@pytest.mark.parametrize("schema,data,ok", [
    ({}, {"lo": "que sea"}, True),
    ({"type": "object", "properties": {"n": {"type": "integer", "minimum": 1}}}, {"n": 0}, False),
    ({"type": "object", "properties": {"n": {"type": "integer"}}}, {"n": True}, False),
    ({"type": "object", "additionalProperties": False, "properties": {}}, {"x": 1}, False),
    ({"type": "object", "properties": {"modo": {"enum": ["a", "b"]}}}, {"modo": "a"}, True),
    ({"type": "object", "properties": {"l": {"type": "array", "items": {"type": "string"}}}}, {"l": ["a", 2]}, False),
    ({"type": ["string", "null"]}, None, True),
])
def test_validar_config(schema, data, ok):
    assert (L.validate_config(schema, data) == []) is ok


# --- montar según la instalación ----------------------------------------------------------------------------------------
def test_apply_monta_lo_activo_y_una_brigada_rota_no_frena_a_las_otras(tmp_path):
    brigade(tmp_path, "buena")
    brigade(tmp_path, "rota", manifest={"cooks": [{"id": "uno", "entry": "no_existe:X"}]})
    rt = runtime(active=["buena", "rota", "fantasma"])
    ld = Loader(rt, [tmp_path], installed=False)
    rep = rt.run(ld.apply())
    assert rep["mounted"] == ["buena"] and set(rep["errors"]) == {"rota", "fantasma"}
    assert "no encontré" in rep["errors"]["fantasma"] and list(rt.brigades) == ["buena"]
    assert [c["error"] is not None for c in ld.catalog() if c["id"] == "rota"] == [True]
    assert rt.audit.entries("brigada_no_montada")


def test_activar_y_desactivar_monta_desmonta_y_guarda_la_instalacion(tmp_path):
    brigade(tmp_path / "b", "uno")
    brigade(tmp_path / "b", "rota", manifest={"cooks": [{"id": "uno", "entry": "no_existe:X"}]})
    path = tmp_path / "installation.yaml"
    rt = runtime()
    ld = Loader(rt, [tmp_path / "b"], installed=False, installation_path=path)
    rt.run(ld.set_active("uno", True))
    assert "uno" in rt.brigades and load_installation(path).brigades["uno"].active is True
    rt.run(ld.set_active("rota", True))
    assert "rota" not in rt.brigades and load_installation(path).brigades["rota"].active is False   # vuelve a inactiva
    rt.run(ld.set_active("uno", False))
    assert rt.brigades == {} and load_installation(path).brigades["uno"].active is False
    with pytest.raises(LoadError):
        rt.run(ld.set_active("no-existe", True))
    assert [e["what"] for e in rt.audit.entries() if e["what"].startswith("brigada_")].count("brigada_activada") == 2


def test_la_config_de_la_instalacion_se_valida_al_montar():
    rt = runtime(active=["saludo"], configs={"saludo": {"max_regalos": 99}})
    rep = rt.run(Loader(rt, [EJEMPLOS], installed=False).apply())
    assert "máximo 10" in rep["errors"]["saludo"]


# --- la brigada de ejemplo, de punta a punta -----------------------------------------------------------------------------
def test_ejemplo_saludo_contesta_pide_aprobacion_para_regalar_y_ejecuta_al_aprobar():
    rt = runtime(active=["saludo", "eco"], configs={"saludo": {"saludo": "¡Buenas"}})
    ld = Loader(rt, [EJEMPLOS], installed=False)
    assert rt.run(ld.apply())["mounted"] == ["saludo", "eco"]
    rt.run(rt.receive("prueba", "ana", "hola", name="Ana"))
    rt.run(rt.receive("prueba", "ana", "hola, quiero un regalo", name="Ana"))
    out = [m["text"] for m in rt.outgoing()]
    assert out[:2] == ["¡Buenas, Ana!", "¡Buenas, Ana! Qué bueno verte de nuevo."]
    [p] = [p for p in rt.approvals.list() if p["action"]["type"] == "regalar"]
    rt.run(rt.approve(p["id"]))
    assert "regalo" in rt.outgoing()[-1]["text"]
    assert rt.store.space("eco/repetidor").name and rt.run(rt.command("saludo", "saludador", "visitas", {})) == {
        "prueba:ana": 2}
    rt.run(rt.receive("prueba", "bob", "eco repetí esto"))
    assert rt.outgoing()[-1]["text"] == "repetí esto"


def test_ejemplo_saludo_con_modelo_la_tool_con_costo_queda_pendiente():
    calls = []

    def transport(url, body, headers):
        calls.append(body)
        if "tools" in body:
            if not any(m.get("role") == "tool" for m in body["messages"]):
                return {"choices": [{"message": {"content": "", "tool_calls": [
                    {"id": "1", "type": "function",
                     "function": {"name": "anotar_regalo", "arguments": '{"person": "Ana", "idea": "un libro"}'}}]}}]}
            return {"choices": [{"message": {"content": "Quedó pendiente anotar el libro para Ana."}}]}
        return {"choices": [{"message": {"content": json.dumps({"summary": "Quedó pendiente anotar un libro para Ana.",
                                                                "confidence": "medium"})}}]}

    cfg = {"providers": {"nube": {"base_url": "https://n.example/v1", "model": "m", "api_key_env": "K"}},
           "tiers": {"pago": [], "gratis": ["nube"], "local": []}, "roles": {"jefe": ["gratis"], "efimero": ["gratis"]}}
    gw = ModelGateway(models_from(cfg), Usage(Store().space("_u"), 100, Clock()), env={"K": "k"}, transport=transport)
    rt = runtime(active=["saludo"], models=gw)
    rt.run(Loader(rt, [EJEMPLOS], installed=False).apply())
    rep = rt.run(rt.ask("saludo", "anotá un regalo para Ana"))
    assert rep.degraded is False and rep.helpers[0].id == "saludo-regalos"
    [p] = [p for p in rt.approvals.list() if p["kind"] == "tool"]
    assert p["data"]["tool"] == "anotar_regalo"
    from ejemplo_saludo import tools as saludo_tools
    before = len(saludo_tools.NOTED)
    rt.run(rt.approve(p["id"]))
    assert len(saludo_tools.NOTED) == before + 1
