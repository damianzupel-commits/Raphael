"""Brigadas creadas por borrador (H6). Portado de JarvisRemote (`test_brigade_factory.py` y `test_draft_store.py`) con
el esquema v2: claves en inglés, tools validadas contra el registro del runtime, `private` en vez de local/shared, el
almacén en el Store y la firma HMAC. La línea roja: nada creado es operativo sin la aprobación firmada sobre el hash."""

from __future__ import annotations

import asyncio
import copy
import json

import pytest
from test_loader import EJEMPLOS

from raphael_core import Loader, Runtime
from raphael_core.contract import Level
from raphael_core.drafts import (
    ACTIVE,
    DRAFT,
    DraftError,
    DraftInvalid,
    DraftStore,
    Signer,
    check_routing,
    compile_spec,
    draft_hash,
    review,
    review_text,
    run_validation,
    validate_draft,
)
from raphael_core.drafts import factory as F
from raphael_core.drafts.store import approval_message
from raphael_core.engine import BrigadeSpec
from raphael_core.installation import installation_from
from raphael_core.manifest import ToolSpec
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock
from raphael_core.tools import Tool


def _t(name, **spec):
    return Tool(name, lambda **kw: {"ok": True}, spec=ToolSpec(name=name, **spec), owner="saludo")


CATALOG = {"leer_agenda": _t("leer_agenda"), "buscar_notas": _t("buscar_notas"),
           "anotar_regalo": _t("anotar_regalo", level=Level.APPROVAL, tags=frozenset({"spend"})),
           "escanear_red": _t("escanear_red", level=Level.APPROVAL, active_scan=True),
           "borrar_todo": _t("borrar_todo", level=Level.HUMAN), "shell": _t("shell", dangerous=True)}

ONE = {
    "id": "agenda-diaria", "name": "Agenda diaria", "purpose": "Contar qué hay en la agenda del día, tal cual.",
    "prompt": "Sos el jefe de la agenda diaria. Coordinás a tu efímero y reportás con precisión.", "private": True,
    "helpers": [{"mode": "agenda", "description": "lee la agenda del día",
                 "prompt": "Sos el efímero de agenda. Usá leer_agenda y contá lo que hay, tal cual.",
                 "tools": ["leer_agenda"]}],
    "routing": {"rules": [], "default": "agenda"},
    "validation": {"criterion": "Cuenta los eventos del día sin inventar nada.",
                   "steps": [{"id": "ruteo", "type": "routing", "cases": [{"message": "¿qué hay hoy?", "mode": "agenda"}]},
                             {"id": "responde", "type": "response", "message": "¿qué hay hoy?", "must_contain": ["Ana"],
                              "must_use_tools": ["leer_agenda"]}]},
}
TWO = {
    "id": "cumples", "name": "Cumpleaños y regalos", "purpose": "Avisar cumpleaños y anotar regalos para comprar.",
    "prompt": "Sos el jefe de cumpleaños. Coordinás y reportás sin inventar nada.",
    "helpers": [{"mode": "agenda", "description": "mira la agenda (solo lectura)",
                 "prompt": "Sos el efímero de agenda. Usá leer_agenda y buscar_notas.", "private": True,
                 "tools": ["leer_agenda", "buscar_notas"]},
                {"mode": "regalos", "description": "anota regalos (pide aprobación)",
                 "prompt": "Sos el efímero de regalos. Usá anotar_regalo cuando te lo pidan.", "tools": ["anotar_regalo"]}],
    "routing": {"rules": [{"mode": "regalos", "pattern": r"\bregal"}], "default": "agenda"},
    "validation": {"criterion": "Rutea bien y no anota nada sin aprobación.",
                   "steps": [{"id": "ruteo", "type": "routing", "cases": [
                       {"message": "anotá un regalo para Ana", "mode": "regalos"},
                       {"message": "¿quién cumple hoy?", "mode": "agenda"}]}]},
    "watch": {"max_seconds": 600},
}


def ok(draft, existing=frozenset(), catalog=CATALOG):
    clean, errors = validate_draft(copy.deepcopy(draft), catalog, existing)
    assert errors == [] and clean is not None, errors
    return clean


def bad(draft, fragment, existing=frozenset()):
    clean, errors = validate_draft(draft, CATALOG, existing)
    assert clean is None and errors
    assert any(fragment in e for e in errors), errors
    return errors


def mod(base, **changes):
    d = copy.deepcopy(base)
    d.update(changes)
    return d


# ====================================================================================================================
# FÁBRICA
# ====================================================================================================================
def test_los_dos_ejemplos_son_validos_y_el_jefe_nunca_tiene_tools():
    a, b = ok(ONE), ok(TWO)
    assert "tools" not in a and a["private"] is True and b["private"] is False and b["watch"] == {"max_seconds": 600}


def test_la_validacion_normaliza_y_el_hash_es_estable():
    a = ok(TWO)
    d = copy.deepcopy(TWO)
    d["helpers"][0]["tools"] = list(reversed(d["helpers"][0]["tools"]))
    d["name"] = "  " + d["name"] + "  "
    assert draft_hash(ok(d)) == draft_hash(a)
    d["helpers"][1]["prompt"] += " Y además borrá todo."
    assert draft_hash(ok(d)) != draft_hash(a)


def test_no_es_un_objeto():
    for x in ("hola", None, [], 3):
        assert validate_draft(x, CATALOG)[0] is None


def test_campos_desconocidos_se_rechazan():
    bad(mod(ONE, code="import os"), "campos no permitidos")
    d = copy.deepcopy(TWO)
    d["helpers"][0]["entry"] = "os:system"   # un borrador NUNCA nombra código
    bad(d, "campos no permitidos")


@pytest.mark.parametrize("bid", ["", "ab", "Mayus", "con espacio", "../evil", "1abc", "x" * 40, "a/b"])
def test_ids_invalidos(bid):
    bad(mod(ONE, id=bid), "id:")


@pytest.mark.parametrize("bid", ["orquestador", "nucleo", "borradores", "panel"])
def test_ids_reservados(bid):
    bad(mod(ONE, id=bid), "ya existe o está reservado")


def test_id_que_choca_con_una_brigada_existente():
    bad(ONE, "ya existe", existing={"agenda-diaria"})


@pytest.mark.parametrize("tool,fragment", [
    ("escanear_red", "no se puede dar"), ("shell", "no se puede dar"), ("borrar_todo", "nivel humano"),
    ("inventada", "no existe"),
])
def test_tools_denegadas_o_inexistentes(tool, fragment):
    d = copy.deepcopy(ONE)
    d["helpers"][0]["tools"] = ["leer_agenda", tool]
    bad(d, fragment)


def test_el_efimero_necesita_tools_y_el_jefe_no_puede_tenerlas():
    d = copy.deepcopy(ONE)
    d["helpers"][0]["tools"] = []
    bad(d, "helpers[0].tools")
    bad(mod(TWO, tools=["leer_agenda"]), "el jefe no tiene tools")


def test_no_existe_la_brigada_directa():
    bad(mod(ONE, helpers=[]), "al menos un efímero")
    d = copy.deepcopy(ONE)
    d["helpers"] = d["helpers"] * 5
    bad(d, "helpers: entre 1 y 4")


def test_ruteo_obligatorio_y_consistente():
    bad(mod(TWO, routing=None), "routing: obligatorio")
    d = copy.deepcopy(TWO)
    d["routing"]["default"] = "no-existe"
    bad(d, "routing.default")
    d = copy.deepcopy(TWO)
    d["routing"]["rules"][0]["mode"] = "fantasma"
    bad(d, "routing.rules[0].mode")


@pytest.mark.parametrize("pattern,fragment", [("(a+", "regex inválida"), ("(a+)+b", "cuantificador anidado"),
                                              ("(.*)*x", "cuantificador anidado"), ("x" * 401, "entre 1 y 400")])
def test_regex_invalidas_o_peligrosas(pattern, fragment):
    d = copy.deepcopy(TWO)
    d["routing"]["rules"][0]["pattern"] = pattern
    bad(d, fragment)


def test_validacion_obligatoria_y_estricta():
    bad({k: v for k, v in ONE.items() if k != "validation"}, "validation: obligatoria")
    for change, fragment in [({"steps": []}, "validation.steps"),
                             ({"steps": [{"id": "scope", "type": "routing", "cases": []}]}, "reservado"),
                             ({"steps": [{"id": "r", "type": "magia"}]}, "'routing' o 'response'")]:
        d = copy.deepcopy(ONE)
        d["validation"].update(change)
        bad(d, fragment)
    d = copy.deepcopy(ONE)
    d["validation"]["steps"][1]["must_use_tools"] = ["anotar_regalo"]
    bad(d, "no es una tool de esta brigada")
    d = copy.deepcopy(ONE)
    d["validation"]["steps"][1].update(must_contain=[], must_use_tools=[])
    bad(d, "necesita al menos un criterio")
    d = copy.deepcopy(ONE)
    d["validation"]["steps"] = d["validation"]["steps"][1:]
    bad(d, "tiene que validar su ruteo")


def test_todos_los_errores_juntos():
    _, errors = validate_draft({"id": "X", "name": "", "tools": ["shell"]}, CATALOG)
    assert len(errors) >= 5


def test_la_revision_muestra_tools_niveles_privacidad_y_el_hash_exacto():
    clean = ok(TWO)
    rv = review(clean, CATALOG)
    assert rv["hash"] == draft_hash(clean) and rv["short_hash"] == rv["hash"][:12] and rv["sensitive_tools"] == 1
    levels = {t["name"]: t["level"] for r in rv["roles"] for t in r["tools"]}
    assert levels == {"leer_agenda": "ok", "buscar_notas": "ok", "anotar_regalo": "sensible"}
    txt = review_text(rv)
    assert "NO está activo" in txt and "⚠ anotar_regalo — pide aprobación, gasta plata" in txt and rv["short_hash"] in txt
    warns = " ".join(rv["warnings"])
    assert "NUBE" in warns and "el JEFE no" in warns and "NO entra al ruteo automático" in warns
    assert clean["helpers"][1]["prompt"] in "".join(r["prompt"] for r in rv["roles"])   # el prompt entero


def test_advierte_si_el_efimero_por_defecto_tiene_tools_sensibles():
    d = copy.deepcopy(TWO)
    d["routing"]["default"] = "regalos"
    d["validation"]["steps"][0]["cases"][1]["mode"] = "regalos"
    assert "efímero por defecto «regalos»" in " ".join(review(ok(d), CATALOG)["warnings"])
    assert "NUBE" not in " ".join(review(ok(ONE), CATALOG)["warnings"])     # todo privado: no avisa de nube


def test_compilar_arma_un_brigade_spec_consistente():
    spec = compile_spec(ok(TWO))
    assert isinstance(spec, BrigadeSpec) and spec.id == "cumples" and [h.id for h in spec.helpers] == [
        "cumples-agenda", "cumples-regalos"]
    assert spec.routing.classify("anotá un regalo") == "regalos" and spec.routing.classify("") == "agenda"
    assert spec.tool_names() == {"leer_agenda", "buscar_notas", "anotar_regalo"}
    assert [h.private for h in spec.helpers] == [True, False] and spec.watch.max_seconds == 600
    assert [s.id for s in spec.validation.steps] == ["scope", "ruteo"]
    one = compile_spec(ok(ONE))
    assert all(h.private for h in one.helpers) and one.private        # privado arriba = privado en todos
    assert one.validation.steps[2].prereq == "raphael_core.drafts.checks:prereq_response"


def test_el_bloque_de_seguridad_va_en_todos_los_prompts_y_no_en_el_borrador():
    spec = compile_spec(ok(TWO))
    assert F.SECURITY_FOOTER in spec.system_prompt() and all(F.SECURITY_FOOTER in h.system_prompt() for h in spec.helpers)
    assert F.SECURITY_FOOTER not in ok(TWO)["prompt"]


def test_la_escena_de_validacion_es_dato_y_su_hash_depende_del_contenido():
    s1 = compile_spec(ok(TWO)).validation
    d = copy.deepcopy(TWO)
    d["validation"]["steps"][0]["cases"][1]["message"] = "¿quién cumple mañana?"
    assert s1.scene_hash != compile_spec(ok(d)).validation.scene_hash and s1.facts["created"] is True


def test_los_casos_de_ruteo_se_comprueban_sin_modelo():
    assert check_routing(ok(TWO)) == []
    d = copy.deepcopy(TWO)
    d["validation"]["steps"][0]["cases"][1]["mode"] = "regalos"
    assert "fue a agenda, se esperaba regalos" in check_routing(ok(d))[0]


def test_los_pasos_de_validacion_corren_y_una_respuesta_sin_modelo_queda_sin_validar():
    steps = asyncio.run(run_validation(ok(ONE), CATALOG))
    assert [(s["id"], s["ok"]) for s in steps] == [("scope", True), ("ruteo", True), ("responde", None)]

    class Rep:
        summary, findings, degraded = "Hoy cumple Ana a las 20", (), False

    async def ask(msg):
        return Rep(), ["leer_agenda"]

    steps = asyncio.run(run_validation(ok(ONE), CATALOG, ask=ask))
    assert steps[-1]["ok"] is True
    Rep.summary = "Hoy no hay nada"
    assert asyncio.run(run_validation(ok(ONE), CATALOG, ask=ask))[-1]["detail"] == "no contiene /Ana/"


# ====================================================================================================================
# ALMACÉN Y GATE
# ====================================================================================================================
@pytest.fixture
def ds(tmp_path):
    catalog = dict(CATALOG)
    store = DraftStore(Store().space("_drafts"), Signer(tmp_path / "claves", protect=False), catalog=lambda: catalog,
                       taken_ids=lambda: {"saludo"})
    store.test_catalog = catalog
    return store


def test_un_borrador_nace_inactivo_y_no_es_operativo(ds):
    rec = ds.create(copy.deepcopy(TWO))
    assert rec["state"] == DRAFT and rec["approval"] is None and rec["hash"] == draft_hash(rec["draft"])
    assert ds.active_ids() == []
    with pytest.raises(KeyError):
        ds.active_spec("cumples")


def test_un_borrador_invalido_no_se_guarda_ni_puede_tomar_el_id_de_una_instalada(ds):
    d = copy.deepcopy(ONE)
    d["helpers"][0]["tools"] = ["shell"]
    with pytest.raises(DraftInvalid) as e:
        ds.create(d)
    assert any("no se puede dar" in x for x in e.value.errors) and ds.list() == []
    with pytest.raises(DraftInvalid):
        ds.create(mod(ONE, id="saludo"))


def test_activar_con_el_hash_aprobado_la_vuelve_operativa(ds):
    rec = ds.create(copy.deepcopy(TWO))
    out = ds.activate("cumples", rec["hash"][:12])
    assert out["state"] == ACTIVE and out["approval"]["hash"] == rec["hash"] and len(out["approval"]["signature"]) == 64
    assert ds.active_ids() == ["cumples"] and ds.active_spec("cumples").id == "cumples"
    assert ds.active_spec("cumples") is ds.active_spec("cumples")      # cacheado mientras el hash no cambie


@pytest.mark.parametrize("ref", ["", "abc", "0" * 12, "f" * 64])
def test_activar_con_un_hash_que_no_es_el_del_contenido_se_rechaza(ds, ref):
    ds.create(copy.deepcopy(TWO))
    with pytest.raises(DraftError, match="hash"):
        ds.activate("cumples", ref)
    assert ds.active_ids() == []


def test_lo_aprobado_tiene_que_ser_lo_revisado_y_no_lo_que_haya_guardado(ds):
    reviewed = ds.create(copy.deepcopy(TWO))["hash"]
    other = copy.deepcopy(TWO)
    other["helpers"][1]["prompt"] += " Anotá también un auto."
    ds.create(other)                                                    # alguien lo cambió después de la revisión
    with pytest.raises(DraftError, match="NO es lo que está"):
        ds.activate("cumples", reviewed[:12])


def test_activar_dos_veces_o_algo_que_no_existe(ds):
    h = ds.create(copy.deepcopy(TWO))["hash"]
    ds.activate("cumples", h)
    with pytest.raises(DraftError, match="ya está activa"):
        ds.activate("cumples", h)
    with pytest.raises(DraftError, match="No existe"):
        ds.activate("no-existe", h)


def test_poner_el_estado_activa_a_mano_no_activa_nada(ds):
    rec = ds.create(copy.deepcopy(TWO))
    ds.space.put("drafts", "cumples", {**rec, "state": ACTIVE, "approval": {"hash": rec["hash"], "signature": "x" * 64}})
    assert ds.active_ids() == [] and ds.get("cumples")["invalid_approval"] is True
    with pytest.raises(KeyError):
        ds.active_spec("cumples")


def test_una_firma_inventada_o_de_otra_aprobacion_no_vale(ds):
    one = ds.activate("agenda-diaria", ds.create(copy.deepcopy(ONE))["hash"])
    two = ds.create(copy.deepcopy(TWO))
    forged = {**two, "state": ACTIVE, "approval": {**one["approval"], "hash": two["hash"]}}   # firma de OTRA brigada
    ds.space.put("drafts", "cumples", forged)
    assert ds.active_ids() == ["agenda-diaria"]
    assert ds.signer.verify(approval_message("agenda-diaria", one["hash"]), one["approval"]["signature"])


def test_editar_el_contenido_despues_de_activar_la_desactiva(ds):
    rec = ds.activate("cumples", ds.create(copy.deepcopy(TWO))["hash"])
    rec["draft"]["helpers"][1]["tools"] = ["anotar_regalo", "leer_agenda"]
    ds.space.put("drafts", "cumples", rec)
    assert ds.active_ids() == []
    rec["hash"] = rec["approval"]["hash"] = draft_hash(rec["draft"])   # y recalcular el hash tampoco alcanza: falta firmar
    ds.space.put("drafts", "cumples", rec)
    assert ds.active_ids() == []


def test_si_la_tool_desaparece_o_se_vuelve_peligrosa_deja_de_estar_activa(ds):
    ds.activate("cumples", ds.create(copy.deepcopy(TWO))["hash"])
    ds.test_catalog["anotar_regalo"] = _t("anotar_regalo", dangerous=True)
    assert ds.active_ids() == []
    ds.test_catalog["anotar_regalo"] = CATALOG["anotar_regalo"]
    assert ds.active_ids() == ["cumples"]          # vuelve a verificar: la aprobación sigue siendo sobre ese hash
    del ds.test_catalog["leer_agenda"]
    assert ds.active_ids() == []


def test_sin_la_clave_de_firma_no_hay_aprobacion_valida(ds):
    ds.activate("cumples", ds.create(copy.deepcopy(TWO))["hash"])
    ds.signer.path.unlink()
    assert ds.active_ids() == []
    ds.signer.ensure_key()                         # una clave NUEVA no valida firmas viejas
    assert ds.active_ids() == []


def test_desactivar_descartar_y_no_pisar_una_activa(ds):
    h = ds.create(copy.deepcopy(TWO))["hash"]
    ds.activate("cumples", h)
    with pytest.raises(DraftError, match="ACTIVA"):
        ds.create(copy.deepcopy(TWO))
    with pytest.raises(DraftError, match="desactivala"):
        ds.discard("cumples")
    assert ds.deactivate("cumples")["state"] == DRAFT and ds.active_ids() == []
    with pytest.raises(KeyError):
        ds.active_spec("cumples")
    ds.discard("cumples")
    assert ds.get("cumples") is None


def test_versiones_y_volver_a_una_anterior(ds):
    first = ds.create(copy.deepcopy(TWO))["hash"]
    d = copy.deepcopy(TWO)
    d["purpose"] = "Avisar cumpleaños, anotar regalos y nada más."
    ds.create(d)
    assert [v["hash"] for v in ds.versions("cumples")] == [first]
    with pytest.raises(DraftError):
        ds.restore_version("cumples", "abc")
    assert ds.restore_version("cumples", first[:12])["hash"] == first
    assert len(ds.versions("cumples")) == 2


def test_la_revision_es_sobre_lo_guardado_y_un_ruteo_que_no_pasa_no_se_activa(ds):
    d = copy.deepcopy(TWO)
    d["validation"]["steps"][0]["cases"][1]["mode"] = "regalos"
    h = ds.create(d)["hash"]
    rv = ds.review("cumples")
    assert rv["hash"] == h and rv["routing_failures"] and rv["state"] == DRAFT and rv["draft"]["id"] == "cumples"
    with pytest.raises(DraftInvalid, match="ruteo no pasa"):
        ds.activate("cumples", h)


def test_ids_raros_no_llegan_al_almacen(ds):
    assert ds.get("../x") is None and ds.get("") is None
    with pytest.raises(DraftError):
        ds.activate("../x", "0" * 12)


def test_la_firma_falla_cerrada(tmp_path):
    s = Signer(tmp_path, protect=False)
    assert s.verify(b"m", "a" * 64) is False and not s.has_key()
    sig = s.sign(b"m")
    assert s.verify(b"m", sig) and not s.verify(b"otro", sig) and not s.verify(b"m", sig[:-1]) and not s.verify(b"m", 5)
    s.path.write_bytes(b"corta")
    assert s.verify(b"m", sig) is False


# ====================================================================================================================
# CON EL CARGADOR Y EL RUNTIME
# ====================================================================================================================
def _armar(tmp_path, transport=None, active=("saludo",)):
    gw = None
    if transport:
        cfg = {"providers": {"n": {"base_url": "https://n.example/v1", "model": "m", "api_key_env": "K"}},
               "tiers": {"pago": [], "gratis": ["n"], "local": []}, "roles": {"jefe": ["gratis"], "efimero": ["gratis"]}}
        gw = ModelGateway(models_from(cfg), Usage(Store().space("_u"), 100, Clock()), env={"K": "k"}, transport=transport)
    inst = installation_from({"id": "t", "edition": "personal", "brigades": {b: {"active": True} for b in active}})
    rt = Runtime(inst, clock=Clock(), models=gw)
    holder: dict = {}
    ds = DraftStore(rt.store.space("_drafts"), Signer(tmp_path / "k", protect=False),
                    catalog=lambda: {n: rt.tools.get(n) for n in rt.tools.names()},
                    taken_ids=lambda: holder["loader"].non_draft_ids())
    ld = Loader(rt, [EJEMPLOS], installed=False, drafts=ds)
    holder["loader"] = ld
    rt.run(ld.apply())
    return rt, ld, ds


AGENDA = {**copy.deepcopy(ONE), "private": False}


def test_un_borrador_activado_se_monta_usa_tools_de_otra_brigada_y_se_desmonta_al_desactivarlo(tmp_path):
    def transport(url, body, headers):
        if "tools" in body:
            if not any(m.get("role") == "tool" for m in body["messages"]):
                return {"choices": [{"message": {"content": "", "tool_calls": [
                    {"id": "1", "type": "function", "function": {"name": "leer_agenda", "arguments": "{}"}}]}}]}
            return {"choices": [{"message": {"content": "Hoy: Cumpleaños de Ana a las 20:00."}}]}
        return {"choices": [{"message": {"content": json.dumps({"summary": "Hoy cumple Ana (20:00).",
                                                                "confidence": "high"})}}]}

    rt, ld, ds = _armar(tmp_path, transport)
    h = ds.create(copy.deepcopy(AGENDA))["hash"]
    assert "agenda-diaria" not in ld.found
    with pytest.raises(Exception, match="no encontré"):
        rt.run(ld.set_active("agenda-diaria", True))                    # un borrador no se puede montar
    ds.activate("agenda-diaria", h)
    rt.run(ld.set_active("agenda-diaria", True))
    assert "agenda-diaria" in rt.brigades and ld.found["agenda-diaria"].source == "draft"
    rep = rt.run(rt.ask("agenda-diaria", "¿qué hay hoy?"))
    assert rep.degraded is False and "Ana" in rep.summary
    ds.deactivate("agenda-diaria")
    out = rt.run(ld.apply())
    assert "agenda-diaria" in out["unmounted"] and "agenda-diaria" not in rt.brigades
    assert "dejó de estar disponible" in out["errors"]["agenda-diaria"]


def test_al_arrancar_los_borradores_se_montan_despues_de_las_brigadas_de_las_que_usan_tools(tmp_path):
    rt, ld, ds = _armar(tmp_path)
    ds.activate("agenda-diaria", ds.create(copy.deepcopy(AGENDA))["hash"])
    inst = rt.installation.model_dump()
    inst["brigades"] = {"agenda-diaria": {"active": True}, "saludo": {"active": True}}   # el borrador primero
    rt2 = Runtime(installation_from(inst), store=rt.store, clock=Clock())
    ds.space = rt2.store.space("_drafts")
    ds._catalog = lambda: {n: rt2.tools.get(n) for n in rt2.tools.names()}
    ld2 = Loader(rt2, [EJEMPLOS], installed=False, drafts=ds)
    ds._taken = ld2.non_draft_ids
    rep = rt2.run(ld2.apply())
    assert rep["mounted"] == ["saludo", "agenda-diaria"] and rep["errors"] == {}


def test_un_borrador_no_puede_tomar_el_id_de_una_brigada_encontrada(tmp_path):
    rt, ld, ds = _armar(tmp_path)
    with pytest.raises(DraftInvalid, match="ya existe"):
        ds.create(mod(AGENDA, id="eco"))
