"""API del harness para el orquestador (contrato 2.1, 22 nov 2026): lo que la pieza 02 necesitaba y no existía.

H-1 modelos de sus roles · H-2 privacidad · H-3 catálogo · H-4 ids reales en las propuestas · H-5 espacio propio ·
H-6 charla con sesión, canal y feed · H-7 ganchos tick/on_event y avisos · H-8 entorno · H-9 consultas con motivo ·
H-10 ruteo en el manifiesto · H-12 orquestador por config. (La H-11, jefe a medida, quedó afuera: decisión de Damián.)
"""

from __future__ import annotations

import textwrap
import uuid

import pytest
from pydantic import ValidationError
from test_engine_runtime import MANIFEST, SPEC, Script, _call, _msg, armar
from test_loader import EJEMPLOS, runtime

from raphael_core import Action, ActionError, Cook, Loader, Orchestrator, OwnerReply, Reply, Runtime
from raphael_core.context import ORCHESTRATOR_SPACE, OrchestratorContext, OwnerContext, QueryResult
from raphael_core.engine import reports as R
from raphael_core.installation import installation_from, load_installation, save_installation
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

# --- ayudas ----------------------------------------------------------------------------------------------------------------
ROLES_MODELS = {
    "providers": {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"}},
    "tiers": {"pago": [], "gratis": ["nube"], "local": []},
    "roles": {"mando": ["gratis"], "voz": ["gratis"], "ruteo": ["gratis"], "jefe": ["gratis"]},
    "private": ["cerebro"],
}


def gateway(transport, edition="personal"):
    return ModelGateway(models_from(ROLES_MODELS), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"},
                        edition=edition, transport=transport)


class Shop(Cook):
    commands = {"stock": "cuánto hay", "borrar": "borra"}

    def interest(self, msg, ctx):
        return 0.5

    def handle(self, msg, ctx):
        return Reply("hola", [Action("regalar", {"a": 1}, summary="regalar algo")])

    def execute(self, action, ctx):
        return "listo"

    def command(self, name, data, ctx):
        if name == "stock":
            return {"remeras": 3}
        if name == "roto":
            raise RuntimeError("se rompió")
        return "borrado"


SHOP = {"id": "tienda", "name": "Tienda", "version": "1.0.0", "contract": ">=2.1,<3", "description": "vende ropa",
        "cooks": [{"id": "vendedor", "entry": "x:Shop"}],
        "actions": {"regalar": {"level": "aprobacion", "tags": ["spend"], "description": "regala algo"}},
        "commands": {"stock": {"read": True, "description": "cuánto hay"}, "borrar": {"read": False}},
        "routing": {"signals": [{"pattern": r"\bremeras?\b", "weight": 2}], "safe_default": False}}


def shop_runtime(orchestrator=None, models=None, user="Lola", plan="pro"):
    inst = installation_from({"id": "c", "edition": "cloud", "plan": plan, "identity": {"user": user}})
    rt = Runtime(inst, clock=Clock(), orchestrator=orchestrator, models=models)
    rt.run(rt.mount(manifest_from(SHOP), {"vendedor": Shop()}))
    return rt


class Recorder(Orchestrator):
    name, version = "grabador", "0.1.0"
    consumes = ("pendiente.creado", "orquestador.aviso", "brigada.reporte")

    def __init__(self):
        self.events, self.ticks, self.owner_ctx = [], [], None

    def route(self, msg, ctx, cooks):
        return cooks

    def on_event(self, event, data, ctx):
        self.events.append((event, data))
        if event == "pendiente.creado":
            ctx.notify(f"Hay un pendiente nuevo: #{data['id']}", pending=data["id"])

    def tick(self, now, ctx):
        self.ticks.append(now)

    async def talk_to_owner(self, text, ctx):
        self.owner_ctx = ctx
        await ctx.emit({"type": "route", "to": "tienda"})
        ctx.data.put("sessions", ctx.session, {"last": text})
        return OwnerReply(f"te escuché: {text}", meta={"via": "reglas", "session": ctx.session})


# --- H-1 · modelos de sus roles ------------------------------------------------------------------------------------------
def test_el_orquestador_usa_sus_roles_con_su_propio_target_y_nada_mas():
    bodies = []

    def transport(url, body, headers):
        bodies.append(body)
        return _msg("tienda")

    rt = shop_runtime(models=gateway(transport))
    ctx = OrchestratorContext(rt)
    assert ctx.has_ai("ruteo") and ctx.ai_label("voz") != "sin modelo"
    assert ctx.ai("ruteo", [{"role": "user", "content": "¿remeras?"}]) == "tienda"
    assert rt.run(ctx.aai("mando", [{"role": "user", "content": "x"}])) == "tienda" and len(bodies) == 2
    with pytest.raises(ActionError, match="solo usa los roles"):
        ctx.ai("jefe", [{"role": "user", "content": "x"}])
    with pytest.raises(ActionError):
        ctx.has_ai("efimero")


def test_sin_pasarela_o_con_privado_sin_modelo_local_vuelve_none_y_sigue_con_reglas():
    rt = shop_runtime()
    ctx = OrchestratorContext(rt)
    assert ctx.ai("voz", [{"role": "user", "content": "x"}]) is None and not ctx.has_ai("voz")
    assert ctx.ai_label("mando") == "sin modelo"
    rt2 = shop_runtime(models=gateway(lambda u, b, h: _msg("no debería salir")))
    ctx2 = OrchestratorContext(rt2)
    assert ctx2.ai("voz", [{"role": "user", "content": "nota privada"}], private=True) is None   # la nube no es local
    assert not ctx2.has_ai("voz", private=True)


# --- H-2 · qué es privado -------------------------------------------------------------------------------------------------
def test_es_privada_si_su_jefe_lo_es_o_si_la_nombra_modelos_yaml():
    rt, _ = armar(models=False)
    assert OrchestratorContext(rt).is_private("osint") is False
    priv_spec = SPEC.__class__(**{**SPEC.__dict__, "private": True})
    rt2, _ = armar(models=False, spec=priv_spec)
    assert OrchestratorContext(rt2).is_private("osint") is True
    rt3 = shop_runtime(models=gateway(lambda u, b, h: _msg("x")))
    rt3.run(rt3.mount(manifest_from({**SHOP, "id": "cerebro", "routing": {}}), {"vendedor": Shop()}))
    ctx3 = OrchestratorContext(rt3)
    assert ctx3.is_private("cerebro") and not ctx3.is_private("tienda")


# --- H-3 · catálogo -------------------------------------------------------------------------------------------------------
def test_el_catalogo_trae_acciones_comandos_de_lectura_ruteo_y_caidas_sin_datos_de_clientes():
    rt = shop_runtime()
    rt.run(rt.receive("whatsapp", "549341", "quiero una remera, soy Juana"))
    [b] = OrchestratorContext(rt).catalog()
    assert b["id"] == "tienda" and b["mounted"] and b["description"] == "vende ropa" and b["chief"] is False
    assert b["actions"] == {"regalar": {"level": "aprobacion", "tags": ["spend"], "description": "regala algo"}}
    assert b["read_commands"] == {"stock": "cuánto hay"}                       # "borrar" no es de lectura
    assert b["routing"]["signals"][0] == {"pattern": r"\bremeras?\b", "weight": 2}
    assert b["down"] is False and b["down_reason"] is None and b["private"] is False
    assert "Juana" not in str(b) and "549341" not in str(b)
    rt.guard.mark_down("tienda/vendedor", "probando")
    [b] = OrchestratorContext(rt).catalog()
    assert b["down"] and "cocineros están caídos" in b["down_reason"] and b["cooks"] == {"vendedor": "caído"}


def test_el_catalogo_suma_lo_que_se_puede_montar_si_hay_cargador():
    rt = runtime(active=("eco",))
    loader = Loader(rt, [EJEMPLOS], installed=False)
    rt.run(loader.apply())
    cat = {b["id"]: b for b in OrchestratorContext(rt).catalog()}
    assert cat["eco"]["mounted"] is True and cat["saludo"]["mounted"] is False
    assert cat["saludo"]["chief"] is True and cat["saludo"]["active"] is False and "actions" not in cat["saludo"]


def test_el_jefe_caido_figura_en_el_catalogo_con_su_motivo():
    rt, _ = armar(models=False)
    rt.brigades["osint"].chief_down = "5 errores seguidos"
    [b] = OrchestratorContext(rt).catalog()
    assert b["down"] and "jefe está caído" in b["down_reason"] and b["chief_purpose"] == "buscar"


# --- H-4 · ids reales en las propuestas ------------------------------------------------------------------------------------
def test_la_propuesta_de_una_tool_pendiente_lleva_el_numero_real_del_pendiente():
    t = Script(helper=[_msg(calls=[_call("send_mail", {"to": "x@y.z", "body": "hola"})]), _msg("Dejé el mail pendiente.")],
               chief=[{"summary": "Quedó un mail pendiente de aprobación.", "confidence": "medium"}])
    rt, _ = armar(t)
    rep = rt.run(rt.ask("osint", "mandá por la web un mail"))
    [p] = rt.approvals.list()
    [prop] = rep.pending_proposals
    assert prop.pending_id == p["id"] and prop.id == str(p["id"]) and "send_mail" in prop.description
    assert rep.to_dict()["pending_proposals"][0]["pending_id"] == p["id"]


def test_una_propuesta_inventada_por_el_modelo_queda_sin_numero_y_con_aviso():
    t = Script(helper=[_msg(calls=[_call("send_mail", {"to": "a@b.c", "body": "x"})]), _msg("listo")],
               chief=[{"summary": "Hay propuestas.", "confidence": "low",
                       "pending_proposals": [{"type": "fix", "id": "ARREGLO-9", "description": "aplicar el arreglo",
                                              "pending_id": 999},
                                             {"type": "other", "id": "#1", "description": "mandar el mail"}]}])
    rt, _ = armar(t)
    rep = rt.run(rt.ask("osint", "mandá por la web un mail"))
    by_id = {p.id: p for p in rep.pending_proposals}
    assert by_id["ARREGLO-9"].pending_id is None            # el 999 del modelo se descarta: no lo puede poner él
    assert by_id["#1"].pending_id == 1 and len(rep.pending_proposals) == 2   # el pendiente real no se duplica
    assert any("no tienen un pendiente real" in w for w in rep.warnings)


def test_un_jefe_que_revienta_igual_reporta_los_pendientes_que_alcanzo_a_abrir():
    rt, _ = armar(models=False)

    async def boom(request, on_event=None, context=""):
        await rt._tool_gate("osint")(rt.tools.get("send_mail"), {"to": "a", "body": "b"})
        raise RuntimeError("chau")

    rt.brigades["osint"].chief.run = boom
    rep = rt.run(rt.ask("osint", "x"))
    [p] = rt.approvals.list()
    assert rep.degraded and rep.pending_proposals[0].pending_id == p["id"]


def test_attach_pending_valida_y_recorta_sin_perder_los_numeros_reales():
    base = R.InternalReport.validate({"version": R.REPORT_VERSION, "brigade": "b", "summary": "s", "confidence": "low"})
    many = [{"id": i, "summary": f"p{i}"} for i in range(1, 16)]
    rep = R.attach_pending(base, many)
    assert len(rep.pending_proposals) == R.MAX_LIST and all(p.pending_id for p in rep.pending_proposals)
    assert any("recortadas" in w for w in rep.warnings)
    with pytest.raises(R.ContractInvalid):
        R.InternalReport.validate({**base.to_dict(), "pending_proposals": [
            {"type": "other", "id": "1", "description": "d", "pending_id": "uno"}]})
    assert R.InternalReport.validate(rep.to_dict()) == rep   # ida y vuelta


# --- H-5 · espacio propio --------------------------------------------------------------------------------------------------
def test_el_orquestador_tiene_su_espacio_y_ningun_cocinero_lo_ve():
    rt = shop_runtime()
    ctx = OrchestratorContext(rt)
    ctx.data.put("proposals", "app", {"actions": [{"type": "aprobar", "pending": 1}]})
    assert OrchestratorContext(rt).data.get("proposals", "app")["actions"][0]["pending"] == 1
    cook_ctx = rt.context("tienda", "vendedor")
    assert ORCHESTRATOR_SPACE not in (cook_ctx.data.name, cook_ctx.shared.name)
    assert cook_ctx.data.get("proposals", "app") is None and cook_ctx.shared.get("proposals", "app") is None


# --- H-6 · charla con sesión, canal y feed --------------------------------------------------------------------------------
def test_talk_to_owner_pasa_sesion_canal_y_feed_y_devuelve_meta():
    orch = Recorder()
    rt = shop_runtime(orch)
    feed = []
    r = rt.run(rt.talk_to_owner("¿qué hay hoy?", session="app-1", channel="app", on_event=feed.append))
    assert r.text == "te escuché: ¿qué hay hoy?" and r.to_dict()["meta"] == {"via": "reglas", "session": "app-1"}
    assert feed == [{"type": "route", "to": "tienda"}]
    assert isinstance(orch.owner_ctx, OwnerContext) and orch.owner_ctx.channel == "app"
    assert OrchestratorContext(rt).data.get("sessions", "app-1") == {"last": "¿qué hay hoy?"}
    assert any(e.get("sesion") == "app-1" for e in rt.audit.entries("duena"))


def test_sin_sesion_usa_default_y_un_feed_roto_no_corta_la_charla():
    orch = Recorder()
    rt = shop_runtime(orch)

    def broken(ev):
        raise RuntimeError("la app se cayó")

    r = rt.run(rt.talk_to_owner("hola", on_event=broken))
    assert r.text.startswith("te escuché") and orch.owner_ctx.session == "default"
    assert rt.audit.entries("feed_fallido") and OwnerReply("x").to_dict()["meta"] == {}
    assert rt.run(rt.talk_to_owner("hola")).text.startswith("te escuché")   # firma vieja sigue andando


# --- H-7 · ganchos y avisos -----------------------------------------------------------------------------------------------
def test_el_orquestador_escucha_lo_que_declara_avisa_y_no_se_escucha_a_si_mismo():
    orch = Recorder()
    rt = shop_runtime(orch)
    rt.run(rt.receive("whatsapp", "1", "quiero un regalo"))   # el cocinero pide regalar -> pendiente
    names = [e for e, _ in orch.events]
    assert names == ["pendiente.creado"]                     # su propio orquestador.aviso no le llega
    [n] = rt.notices()
    assert n["text"].startswith("Hay un pendiente nuevo") and n["data"]["pending"] == 1 and not n["seen"]
    assert rt.status()["notices"] == 1 and any(ev == "orquestador.aviso" for ev, _ in rt.bus.history)


def test_el_tick_llama_al_orquestador_y_uno_roto_no_tumba_el_harness():
    orch = Recorder()
    rt = shop_runtime(orch)
    rt.run(rt.tick())
    assert len(orch.ticks) == 1

    class Broken(Recorder):
        def tick(self, now, ctx):
            raise RuntimeError("tick roto")

        def on_event(self, event, data, ctx):
            raise RuntimeError("evento roto")

    rt2 = shop_runtime(Broken())
    rt2.run(rt2.tick())
    rt2.run(rt2.receive("whatsapp", "1", "regalo"))
    fails = rt2.audit.entries("orquestador_fallido")
    assert {e.get("metodo") for e in fails} == {"tick", "on_event"}
    assert rt2.approvals.list()                              # el mensaje igual se procesó


def test_en_tick_y_on_event_el_orquestador_no_puede_ejecutar():
    seen = {}

    class Peek(Recorder):
        def tick(self, now, ctx):
            seen["ctx"] = ctx

    rt = shop_runtime(Peek())
    rt.run(rt.tick())
    ctx = seen["ctx"]
    assert type(ctx) is OrchestratorContext
    assert not any(hasattr(ctx, m) for m in ("approve", "reject", "resolve", "order", "act", "write"))


def test_cambiar_o_sacar_el_orquestador_saca_sus_suscripciones():
    orch = Recorder()
    rt = shop_runtime(orch)
    assert "orquestador" in rt.bus.owners("pendiente.creado")
    rt.set_orchestrator(None)
    assert "orquestador" not in rt.bus.owners() and rt.orchestrator is None
    rt.set_orchestrator(orch, {"mode": "secretary"})
    assert orch.config == {"mode": "secretary"} and "orquestador" in rt.bus.owners("brigada.reporte")


# --- H-8 · entorno ---------------------------------------------------------------------------------------------------------
def test_el_orquestador_ve_edicion_plan_identidad_y_uso():
    rt = shop_runtime(user="Lola", plan="pro")
    ctx = OrchestratorContext(rt)
    assert (ctx.edition, ctx.plan, ctx.identity.user) == ("cloud", "pro", "Lola")
    rt.run(rt.receive("whatsapp", "1", "hola"))
    u = ctx.usage()
    assert u["messages"] == 1 and u["exceeded"] is False


# --- H-9 · consultas con motivo --------------------------------------------------------------------------------------------
def test_query_detail_dice_por_que_no_pudo_y_query_sigue_igual():
    rt = shop_runtime()
    ctx = OrchestratorContext(rt)
    assert rt.run(ctx.query_detail("tienda", "vendedor", "stock")) == QueryResult(True, {"remeras": 3})
    r = rt.run(ctx.query_detail("tienda", "vendedor", "borrar"))
    assert not r.ok and "no es de lectura" in r.error
    r = rt.run(ctx.query_detail("tienda", "vendedor", "inventado"))
    assert not r.ok and "no está declarado" in r.error
    r = rt.run(ctx.query_detail("nada", "x", "stock"))
    assert not r.ok and "no está montado" in r.error
    assert rt.run(ctx.query("tienda", "vendedor", "borrar")) is None
    rt.guard.mark_down("tienda/vendedor", "probando")
    r = rt.run(ctx.query_detail("tienda", "vendedor", "stock"))
    assert not r.ok and "está caída" in r.error


# --- H-10 · ruteo en el manifiesto -----------------------------------------------------------------------------------------
def test_el_manifiesto_valida_las_senales_de_ruteo():
    m = manifest_from(SHOP)
    assert m.routing.signals[0].weight == 2 and m.routing.direct_only is False
    assert manifest_from({k: v for k, v in SHOP.items() if k != "routing"}).routing.signals == ()
    for bad in ({"signals": [{"pattern": "(sin cerrar", "weight": 1}]}, {"signals": [{"pattern": "x", "weight": 3}]},
                {"signals": [{"pattern": ""}]}, {"otra_cosa": True}):
        with pytest.raises(ValidationError):
            manifest_from({**SHOP, "routing": bad})
    with pytest.raises(ValidationError):
        manifest_from({**SHOP, "routing": {"signals": [{"pattern": f"p{i}"} for i in range(41)]}})


# --- H-12 · orquestador por config -----------------------------------------------------------------------------------------
ORCH_CODE = """
from raphael_core import Orchestrator, OwnerReply

class Mine(Orchestrator):
    name, version = "mio", "0.0.1"
    consumes = ("pendiente.creado",)

    def route(self, msg, ctx, cooks):
        return list(reversed(cooks))

    def talk_to_owner(self, text, ctx):
        return OwnerReply("modo " + self.config.get("mode", "?"))
"""


def _orch_module(tmp_path, code=ORCH_CODE) -> str:
    name = f"orq_{uuid.uuid4().hex[:8]}"
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(code), encoding="utf-8")
    return name


def _inst(entry=None, config=None):
    data = {"id": "t", "edition": "personal", "brigades": {"eco": {"active": True}}}
    if entry:
        data["orchestrator"] = {"entry": entry, "config": config or {}}
    return installation_from(data)


def test_la_instalacion_monta_su_orquestador_con_su_config(tmp_path):
    mod = _orch_module(tmp_path)
    rt = Runtime(_inst(f"{mod}:Mine", {"mode": "master"}), clock=Clock())
    rep = rt.run(Loader(rt, [EJEMPLOS, tmp_path], installed=False).apply())
    assert rep["errors"] == {} and rep["mounted"] == ["eco"]
    assert rt.orchestrator.name == "mio" and rt.status()["orchestrator"] == "mio 0.0.1"
    assert rt.run(rt.talk_to_owner("hola")).text == "modo master"
    assert "orquestador" in rt.bus.owners("pendiente.creado")
    assert any(e["what"] == "orquestador_montado" for e in rt.audit.entries())


def test_un_orquestador_que_no_carga_deja_el_orden_simple_y_el_error_en_el_reporte(tmp_path):
    for entry in ("no_existe_mod:Nada", "nombre-sin-entry-point"):
        rt = Runtime(_inst(entry), clock=Clock())
        rep = rt.run(Loader(rt, [EJEMPLOS, tmp_path], installed=False).apply())
        assert "_orchestrator" in rep["errors"] and rt.orchestrator is None and rep["mounted"] == ["eco"]
        assert rt.run(rt.receive("prueba", "1", "hola"))   # el orden simple atiende igual
    mod = _orch_module(tmp_path, "class NoEs:\n    pass\n")
    rt = Runtime(_inst(f"{mod}:NoEs"), clock=Clock())
    rep = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert "no es una clase Orchestrator" in rep["errors"]["_orchestrator"]


def test_sacar_el_orquestador_de_la_instalacion_vuelve_al_orden_simple(tmp_path):
    mod = _orch_module(tmp_path)
    inst = _inst(f"{mod}:Mine")
    rt = Runtime(inst, clock=Clock())
    loader = Loader(rt, [EJEMPLOS, tmp_path], installed=False)
    rt.run(loader.apply())
    first = rt.orchestrator
    rt.run(loader.apply())
    assert rt.orchestrator is first                    # mismo entry: no se rearma
    inst.orchestrator = None
    rt.run(loader.apply())
    assert rt.orchestrator is None and "orquestador" not in rt.bus.owners()


def test_la_instalacion_con_orquestador_se_guarda_y_se_vuelve_a_leer(tmp_path):
    inst = _inst("paquete.modulo:Clase", {"mode": "secretary", "joint": False})
    path = tmp_path / "installation.yaml"
    save_installation(inst, path)
    back = load_installation(path)
    assert back.orchestrator.entry == "paquete.modulo:Clase" and back.orchestrator.config["mode"] == "secretary"
    assert installation_from({"id": "x", "edition": "cloud"}).orchestrator is None
    with pytest.raises(ValidationError):
        installation_from({"id": "x", "edition": "cloud", "orchestrator": {"entry": ""}})


def test_un_manifiesto_2_1_no_monta_en_un_nucleo_que_no_lo_soporta():
    assert manifest_from(SHOP).supports_contract("2.1.0") and not manifest_from(SHOP).supports_contract("2.0.0")
    assert manifest_from(MANIFEST).supports_contract("2.1.0")   # las de >=2.0 siguen montando


# --- H-13 · lo que necesita el watchdog del orquestador (O2) ---------------------------------------------------------------
def test_el_catalogo_trae_la_vigilancia_del_jefe_y_el_orquestador_audita_y_marca_cortes():
    from raphael_core.engine import WatchSpec

    spec = SPEC.__class__(**{**SPEC.__dict__, "watch": WatchSpec(stall_seconds=12, max_repeats=2), "helper_timeout": 50})
    rt, _ = armar(models=False, spec=spec)
    ctx = OrchestratorContext(rt)
    [b] = ctx.catalog()
    assert b["watch"] == {"helper_timeout": 50.0, "max_seconds": None, "stall_seconds": 12, "max_repeats": 2,
                          "max_errors": None}
    rt2, _ = armar(models=False)
    assert OrchestratorContext(rt2).catalog()[0]["watch"]["helper_timeout"] == 900.0
    assert shop_runtime().catalog()[0]["watch"] is None          # sin jefe no hay nada que vigilar
    ctx.record("ruteo", destino="osint")
    ctx.mark_cut("osint", "loop: la misma llamada 3 veces")
    assert [e["what"] for e in rt.audit.entries(who="orquestador")][-2:] == ["ruteo", "corte_orquestador"]


# --- H-14 · comandos en el catálogo (para la Secretaria, O4) -------------------------------------------------------------
def test_el_catalogo_trae_todos_los_comandos_declarados_y_que_cocinero_los_atiende():
    [b] = shop_runtime().catalog()
    assert b["commands"] == {"borrar": {"read": False, "description": "", "cooks": ["vendedor"]},
                             "stock": {"read": True, "description": "cuánto hay", "cooks": ["vendedor"]}}

    class Two(Cook):
        commands = {"agenda_hoy": "turnos de hoy"}

    inst = installation_from({"id": "c", "edition": "cloud"})
    rt = Runtime(inst, clock=Clock())
    rt.run(rt.mount(manifest_from({**SHOP, "id": "doble", "cooks": [{"id": "vendedor", "entry": "x:Shop"},
                                                                     {"id": "agenda", "entry": "x:Two"}],
                                   "commands": {"agenda_hoy": {"read": True}, "stock": {"read": True}}}),
                    {"vendedor": Shop(), "agenda": Two()}))
    cmds = rt.catalog()[0]["commands"]
    assert cmds["agenda_hoy"]["cooks"] == ["agenda"] and cmds["stock"]["cooks"] == ["vendedor"]


# --- H-15 · borradores solo cuando habla la persona -----------------------------------------------------------------------
def test_los_borradores_solo_se_ven_desde_el_contexto_de_la_persona(tmp_path):
    from raphael_core.drafts import DraftStore
    from raphael_core.drafts.signing import Signer

    rt = shop_runtime()
    assert OwnerContext(rt, "Lola").drafts is None                     # sin cargador, no hay borradores
    store = DraftStore(rt.store.space("_drafts"), Signer(tmp_path / "k"), catalog=rt.tools.list)
    Loader(rt, [], installed=False, drafts=store)
    assert OwnerContext(rt, "Lola").drafts is store
    assert not hasattr(OrchestratorContext(rt), "drafts")              # ni en ruteo, ni en tick, ni en eventos

