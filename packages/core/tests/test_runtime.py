"""Runtime del harness v2 con una brigada de juguete. Varios portados de raphael-harness 0.4 (Empresas)."""

from __future__ import annotations

import asyncio

import pytest

from raphael_core import CONTRACT_VERSION, Action, ActionError, Cook, Level, MountError, OwnerReply, Reply, Runtime, Trust
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.store import Store
from raphael_core.testing import Clock

MANIFEST = {
    "id": "eco", "name": "Eco", "version": "9.9.9", "contract": "^2.0",
    "cooks": [{"id": "eco", "entry": "x:Eco"}, {"id": "respaldo", "entry": "x:Respaldo"}],
    "actions": {"saludar": {"level": "automatico"}, "regalar": {"level": "aprobacion"},
                "pagar": {"level": "aprobacion", "tags": ["spend"]}},
    "events": {"publishes": ["eco.hecho"], "consumes": ["ping", "pendiente.rechazado"]},
    "uninstall": {"export": ["notas"], "delete": ["*"]},
}


class Eco(Cook):
    name = "eco"

    def __init__(self) -> None:
        self.seen: list[tuple[str, dict]] = []

    def interest(self, msg, ctx):
        return 0.5 if "eco" in msg.text else 0.0

    def handle(self, msg, ctx):
        if "eco" not in msg.text:
            return None
        actions = [Action("saludar", {"a": msg.name})]
        if "regalo" in msg.text:
            actions.append(Action("regalar", {"cosa": "flor"}, "Regalar una flor"))
        if "pago" in msg.text:
            actions.append(Action("pagar", {"monto": 100}, "Pagar 100"))
        if "inventada" in msg.text:
            actions.append(Action("teletransportar", {}, "Algo que nadie declaró"))
        return Reply("eco: " + msg.text, actions)

    def execute(self, action, ctx):
        if action.type == "saludar":
            return "¡saludos!"
        if action.type == "regalar":
            if not action.data.get("cosa"):
                raise ActionError("falta la cosa")
            return f"te regalo una {action.data['cosa']}"
        if action.type == "pagar":
            return "pagado"
        raise ActionError("no")

    def on_event(self, event, data, ctx):
        self.seen.append((event, data))
        if event == "ping" and data.get("pedir"):
            ctx.request(Action("saludar", {}, target="prueba:9"))

    def command(self, name, data, ctx):
        if name == "anotar":
            ctx.data.put("notas", data["n"], {"n": data["n"]})
            return "ok"
        if name == "publicar":
            ctx.publish(data["evento"], {})
            return "ok"
        if name == "otra":
            return ctx.mounted("otra-brigada")
        raise ActionError(f"no tengo el comando '{name}'")


class Respaldo(Cook):
    name = "respaldo"

    def interest(self, msg, ctx):
        return 0.1

    async def handle(self, msg, ctx):                      # un cocinero async
        if "respaldo" in msg.text:
            return Reply("respaldo al habla")
        return None


class Roto(Cook):
    name = "roto"

    def interest(self, msg, ctx):
        return 1.0

    def handle(self, msg, ctx):
        raise RuntimeError("se rompió")


def armar(autonomy=None, trust=None, edition="personal", cooks=None, manifest=None, **kw):
    inst = installation_from({"id": "prueba", "edition": edition, "identity": {"user": "Ana"},
                              "autonomy": autonomy or {}, "trust": trust or {}})
    rt = Runtime(inst, clock=kw.pop("clock", Clock()), **kw)
    eco = Eco()
    m = manifest_from(manifest or MANIFEST)
    rt.run(rt.mount(m, cooks or {"eco": eco, "respaldo": Respaldo()}))
    return rt, eco


# --- portados de Empresas -----------------------------------------------------------------------------------------------
def test_responde_y_ejecuta_lo_automatico():
    rt, _ = armar()
    out = rt.run(rt.receive("prueba", "1", "eco hola", name="Cami"))
    assert out == ["eco: eco hola", "¡saludos!"]


def test_lo_que_requiere_aprobacion_queda_pendiente_y_se_aprueba_con_cambios():
    rt, _ = armar()
    out = rt.run(rt.receive("prueba", "1", "eco regalo"))
    assert out == ["eco: eco regalo", "¡saludos!"]                 # el regalo NO se ejecutó
    [p] = rt.approvals.list()
    assert p["level"] == "aprobacion" and p["summary"] == "Regalar una flor"
    res = rt.run(rt.approve(p["id"], {"cosa": "rosa"}))
    assert res == {"state": "executed", "text": "te regalo una rosa"}
    assert rt.outgoing("prueba:1")[-1]["text"] == "te regalo una rosa" and rt.approvals.list() == []


def test_un_error_al_aprobar_deja_el_pendiente_abierto():
    rt, _ = armar()
    rt.run(rt.receive("prueba", "1", "eco regalo"))
    pid = rt.approvals.list()[0]["id"]
    assert rt.run(rt.approve(pid, {"cosa": ""}))["state"] == "error"
    assert [p["id"] for p in rt.approvals.list()] == [pid]


def test_accion_no_declarada_pide_aprobacion():
    rt, _ = armar()
    rt.run(rt.receive("prueba", "1", "eco inventada"))
    [p] = rt.approvals.list()
    assert p["level"] == "aprobacion" and "no declarada" in p["reason"]


def test_nadie_entiende_queda_para_una_persona():
    rt, _ = armar()
    out = rt.run(rt.receive("prueba", "1", "hola, ¿hacen envíos?"))
    assert out == ["¡Gracias por escribir! 😊 En un rato te responde Ana."]
    [p] = rt.approvals.list()
    assert p["level"] == "humano" and p["action"]["type"] == "responder_duda"
    with pytest.raises(ActionError):
        rt.run(rt.approve(p["id"]))                               # humano: no se aprueba, se resuelve
    rt.run(rt.resolve(p["id"], "Sí, a todo el país"))
    assert rt.outgoing("prueba:1")[-1]["text"] == "Sí, a todo el país" and rt.approvals.list() == []


def test_eventos_llegan_a_quien_los_escucha():
    rt, eco = armar()
    rt.bus.publish("ping", {"x": 1}, source="otra")
    assert eco.seen == [("ping", {"x": 1, "_from": "otra"})]


def test_registro_y_estado_sin_datos_de_clientes():
    rt, _ = armar()
    rt.run(rt.receive("prueba", "1", "eco hola secreta"))
    st = rt.status()
    assert st["brigades"] == {"eco": {"version": "9.9.9", "cooks": {"eco": "ok", "respaldo": "ok"}, "chief": None,
                                      "chief_down": None, "chief_failures": 0, "health": None}}
    assert "secreta" not in str(st) and st["contract"] == CONTRACT_VERSION
    assert any(e["what"] == "accion_ejecutada" for e in rt.audit.entries())


def test_conversacion_y_contactos():
    rt, _ = armar()
    rt.run(rt.receive("whatsapp", "1", "eco hola", name="Cami"))
    assert [m["from"] for m in rt.conversation("whatsapp:1")] == ["contact", "raphael", "raphael"]
    rt.run(rt.receive("whatsapp", "1", "eco chau"))
    assert [m["text"][:7] for m in rt.conversation("whatsapp:1")][3:] == ["eco cha", "eco: ec", "¡saludo"]
    assert rt.contacts()[0]["name"] == "Cami"


def test_reloj_controlable():
    c = Clock()
    rt, _ = armar(clock=c)
    assert rt.context("eco", "eco").today() == c.now.date()


# --- sin pisos y confianza progresiva ------------------------------------------------------------------------------------
def test_sin_pisos_la_instalacion_puede_bajar_a_automatico():
    rt, _ = armar(autonomy={"eco.regalar": "automatico"})
    out = rt.run(rt.receive("prueba", "1", "eco regalo"))
    assert out[-1] == "te regalo una flor" and rt.approvals.list() == []


def test_automatico_sin_confirmar_en_algo_que_gasta_se_ignora():
    rt, _ = armar(autonomy={"pagar": "automatico"})
    assert any("sin confirmar" in w for w in rt.warnings)
    rt.run(rt.receive("prueba", "1", "eco pago"))
    assert [p["action"]["type"] for p in rt.approvals.list()] == ["pagar"]
    rt2, _ = armar(autonomy={"pagar": {"level": "automatico", "confirmed_by": "Ana"}})
    assert rt2.run(rt2.receive("prueba", "1", "eco pago"))[-1] == "pagado"


def _aprobar_n(rt, texto, n, cambios=None):
    for _ in range(n):
        rt.run(rt.receive("prueba", "1", texto))
        p = [x for x in rt.approvals.list() if x["kind"] == "action"][-1]
        rt.run(rt.approve(p["id"], cambios))


def test_confianza_baja_tras_n_aprobaciones_sin_cambios():
    rt, _ = armar(trust={"approvals_to_step_down": 3})
    _aprobar_n(rt, "eco regalo", 2)
    assert rt.policy.level("eco", "regalar") is Level.APPROVAL
    _aprobar_n(rt, "eco regalo", 1)
    assert rt.policy.level("eco", "regalar") is Level.AUTO
    out = rt.run(rt.receive("prueba", "1", "eco regalo"))
    assert out[-1] == "te regalo una flor"                        # ahora sale sola
    assert any(e["what"] == "confianza_baja" for e in rt.audit.entries())


def test_rechazo_o_cambios_suben_y_reinician():
    rt, _ = armar(trust={"approvals_to_step_down": 3})
    _aprobar_n(rt, "eco regalo", 2)
    _aprobar_n(rt, "eco regalo", 1, cambios={"cosa": "rosa"})     # con cambios: sube y reinicia
    assert rt.policy.level("eco", "regalar") is Level.HUMAN
    rt.policy.reset("eco", "regalar", who="Ana")
    rt.run(rt.receive("prueba", "1", "eco regalo"))
    rt.run(rt.reject(rt.approvals.list()[0]["id"], "no"))
    assert rt.policy.level("eco", "regalar") is Level.HUMAN


def test_corregir_una_automatica_la_sube():
    rt, _ = armar()
    assert rt.correct("eco", "saludar", why="saludó mal") == "raised"
    assert rt.policy.level("eco", "saludar") is Level.APPROVAL


def test_lo_que_gasta_nunca_baja_solo_a_automatico_se_propone():
    rt, _ = armar(trust={"approvals_to_step_down": 2})
    _aprobar_n(rt, "eco pago", 2)
    assert rt.policy.level("eco", "pagar") is Level.APPROVAL      # no bajó sola
    [prop] = [p for p in rt.approvals.list() if p["kind"] == "trust"]
    assert "¿La dejo en automático?" in prop["summary"]
    _aprobar_n(rt, "eco pago", 2)                                 # no se repite la propuesta
    assert len([p for p in rt.approvals.list() if p["kind"] == "trust"]) == 1
    assert rt.run(rt.approve(prop["id"])) == {"state": "trust", "level": "automatico"}
    assert rt.run(rt.receive("prueba", "1", "eco pago"))[-1] == "pagado"


def test_propuesta_rechazada_no_baja():
    rt, _ = armar(trust={"approvals_to_step_down": 1})
    _aprobar_n(rt, "eco pago", 1)
    [prop] = [p for p in rt.approvals.list() if p["kind"] == "trust"]
    rt.run(rt.reject(prop["id"]))
    assert rt.policy.level("eco", "pagar") is Level.APPROVAL


def test_confianza_apagada():
    rt, _ = armar(trust={"enabled": False, "approvals_to_step_down": 1})
    _aprobar_n(rt, "eco regalo", 3)
    assert rt.policy.level("eco", "regalar") is Level.APPROVAL


def test_terceros_suben_un_escalon_solo_si_se_configura():
    rt, _ = armar(trust={"third_party_step_up": True})
    rt.run(rt.receive("prueba", "1", "eco hola"))                 # saludar es automático, pero lo pidió un tercero
    assert [p["action"]["type"] for p in rt.approvals.list()] == ["saludar"]
    rt2, _ = armar()
    rt2.run(rt2.receive("prueba", "1", "eco hola", trust=Trust.TRUSTED))
    assert rt2.approvals.list() == []


# --- cero ejecuciones sin OK e ids inventados ------------------------------------------------------------------------------
@pytest.mark.parametrize("pid", [999, "abc", None, -1])
def test_ids_inventados_se_rechazan(pid):
    rt, _ = armar()
    for fn in (rt.approve, rt.reject, rt.resolve):
        with pytest.raises(ActionError):
            rt.run(fn(pid))


def test_ninguna_accion_con_aprobacion_se_ejecuta_sin_ok():
    rt, _ = armar()
    rt.run(rt.receive("prueba", "1", "eco regalo pago inventada"))
    ejecutadas = [e["tipo"] for e in rt.audit.entries(what="accion_ejecutada")]
    assert ejecutadas == ["saludar"]
    assert {p["action"]["type"] for p in rt.approvals.list()} == {"regalar", "pagar", "teletransportar"}


def test_un_pendiente_cerrado_no_se_aprueba_dos_veces():
    rt, _ = armar()
    rt.run(rt.receive("prueba", "1", "eco regalo"))
    pid = rt.approvals.list()[0]["id"]
    rt.run(rt.approve(pid))
    with pytest.raises(ActionError):
        rt.run(rt.approve(pid))


# --- aislamiento ---------------------------------------------------------------------------------------------------------
def test_un_cocinero_roto_no_tumba_el_mensaje_y_cae_a_la_tercera():
    m = {**MANIFEST, "cooks": [*MANIFEST["cooks"], {"id": "roto", "entry": "x:Roto"}]}
    rt, _ = armar(manifest=m, cooks={"eco": Eco(), "respaldo": Respaldo(), "roto": Roto()})
    for _ in range(3):
        assert rt.run(rt.receive("prueba", "1", "eco hola"))[0] == "eco: eco hola"
    assert rt.status()["brigades"]["eco"]["cooks"]["roto"] == "caído"
    assert any(e["what"] == "pieza_caida" for e in rt.audit.entries())


def test_cocinero_async_responde():
    rt, _ = armar()
    assert rt.run(rt.receive("prueba", "1", "respaldo?")) == ["respaldo al habla"]


def test_accion_pedida_desde_un_evento_sync_se_procesa():
    rt, _ = armar()

    async def go():
        await rt.bus.apublish("ping", {"pedir": True}, source="otra")
        await rt._settle()

    rt.run(go())
    assert rt.outgoing("prueba:9")[-1]["text"] == "¡saludos!"


def test_rechazo_avisa_por_el_bus():
    rt, eco = armar()
    rt.run(rt.receive("prueba", "1", "eco regalo"))
    rt.run(rt.reject(rt.approvals.list()[0]["id"], "no hay flores"))
    ev = [d for e, d in eco.seen if e == "pendiente.rechazado"]
    assert ev and ev[0]["reason"] == "no hay flores" and ev[0]["type"] == "regalar"


# --- contexto, eventos declarados y comandos -----------------------------------------------------------------------------
def test_solo_publica_lo_declarado_y_no_ve_otras_brigadas():
    rt, _ = armar()
    assert rt.run(rt.command("eco", "eco", "publicar", {"evento": "eco.hecho"})) == "ok"
    with pytest.raises(ActionError):
        rt.run(rt.command("eco", "eco", "publicar", {"evento": "otro.evento"}))
    assert rt.run(rt.command("eco", "eco", "otra")) is False
    with pytest.raises(ActionError):
        rt.run(rt.command("eco", "eco", "inexistente"))
    with pytest.raises(ActionError):
        rt.run(rt.command("nadie", "eco", "anotar", {"n": 1}))
    assert not hasattr(rt.context("eco", "eco"), "para")


def test_datos_del_cocinero_y_de_la_brigada_separados():
    rt, _ = armar()
    rt.run(rt.command("eco", "eco", "anotar", {"n": 1}))
    ctx = rt.context("eco", "eco")
    assert ctx.data.get("notas", 1) == {"n": 1} and ctx.shared.get("notas", 1) is None
    assert rt.context("eco", "respaldo").data.get("notas", 1) is None


# --- montar y desmontar --------------------------------------------------------------------------------------------------
def test_desmontar_exporta_purga_y_saca_suscripciones():
    store = Store()
    rt, eco = armar(store=store)
    rt.run(rt.command("eco", "eco", "anotar", {"n": 7}))
    exported = rt.run(rt.unmount("eco"))
    assert exported == {"eco/eco": {"notas": {"7": {"n": 7}}}}
    assert store.space("eco").export() == {} and "eco" not in rt.brigades
    rt.bus.publish("ping", {})
    assert eco.seen == []                                         # ya no escucha
    assert rt.run(rt.receive("prueba", "1", "eco hola"))[0].startswith("¡Gracias")
    rt.run(rt.mount(manifest_from(MANIFEST), {"eco": Eco(), "respaldo": Respaldo()}))   # se vuelve a montar
    assert rt.run(rt.receive("prueba", "1", "eco hola"))[0] == "eco: eco hola"


@pytest.mark.parametrize("cambio,cooks", [
    ({"contract": ">=3.0"}, None),
    ({"editions": ["personal"]}, None),
    ({}, {"eco": Eco()}),
])
def test_no_se_monta_lo_que_no_cumple(cambio, cooks):
    inst = installation_from({"id": "x", "edition": "cloud"})
    rt = Runtime(inst)
    with pytest.raises(MountError):
        rt.run(rt.mount(manifest_from({**MANIFEST, **cambio}), cooks or {"eco": Eco(), "respaldo": Respaldo()}))
    assert rt.brigades == {}


def test_no_se_monta_dos_veces():
    rt, _ = armar()
    with pytest.raises(MountError):
        rt.run(rt.mount(manifest_from(MANIFEST), {"eco": Eco(), "respaldo": Respaldo()}))


# --- orquestador y persona -----------------------------------------------------------------------------------------------
class Secretaria:
    name, version = "secretaria", "0.1"

    def route(self, msg, ctx, cooks):
        return sorted(cooks, key=lambda c: c.name != "respaldo")   # respaldo primero

    async def talk_to_owner(self, text, ctx):
        pend = ctx.pending()
        if text == "aprobá todo":
            for p in pend:
                await ctx.approve(p["id"])
            return OwnerReply(f"Aprobé {len(pend)}.")
        return OwnerReply(f"Tenés {len(pend)} pendientes.")


class OrquestadorRoto:
    name, version = "roto", "0"

    def route(self, msg, ctx, cooks):
        raise RuntimeError("roto")


def test_orquestador_ordena_y_la_persona_aprueba_hablando():
    rt, _ = armar(orchestrator=Secretaria())
    assert rt.run(rt.receive("prueba", "1", "eco respaldo")) == ["respaldo al habla"]
    rt.run(rt.receive("prueba", "1", "eco regalo"))
    assert rt.run(rt.talk_to_owner("¿qué hay?")).text == "Tenés 1 pendientes."
    assert rt.run(rt.talk_to_owner("aprobá todo")).text == "Aprobé 1."
    assert rt.approvals.list() == [] and rt.audit.entries(what="aprobado")[0]["who"] == "Ana"


def test_orquestador_roto_cae_al_orden_simple():
    rt, _ = armar(orchestrator=OrquestadorRoto())
    assert rt.run(rt.receive("prueba", "1", "eco hola"))[0] == "eco: eco hola"
    assert rt.audit.entries(what="orquestador_fallido")
    assert "orquestador" in rt.run(rt.talk_to_owner("hola")).text


def test_run_no_se_usa_dentro_de_un_loop():
    rt, _ = armar()

    async def adentro():
        with pytest.raises(RuntimeError):
            rt.run(rt.receive("prueba", "1", "eco"))

    asyncio.run(adentro())
