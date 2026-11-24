"""La Secretaria y la confirmación de acciones: puerta de O4.

Portados de Empresas `raphael-orquestador/tests/test_secretaria.py` (10) y `test_agente.py` (12). Lo del negocio (qué es
un encargo vencido, una seña, un turno, los textos de las opciones y los bonus por tipo) ya no lo sabe el orquestador: lo
hacen las brigadas de prueba de abajo con su comando `owner_tasks`, como lo va a hacer la brigada Empresas (pieza 15).
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime

import pytest
from raphael_core import Action, ActionError, Cook, Reply, Runtime
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_orchestrator import confirm
from raphael_orchestrator.orchestrator import RaphaelOrchestrator


def plata(n: int) -> str:
    return f"$ {n:,}".replace(",", ".")


# --- brigadas de prueba (lo que hará la 15) ------------------------------------------------------------------------------
class Encargos(Cook):
    commands = {"owner_tasks": "tareas del día", "estado": "cambiar el estado de un encargo"}

    def __init__(self, lista=None, num=9):
        self.lista, self.num = lista or [], num

    def interest(self, msg, ctx):
        return 1.0 if "vestido" in msg.text else 0.0

    def handle(self, msg, ctx):
        return Reply("ok", [Action("enviar_presupuesto", {"num": self.num, "precio": 90000},
                                   summary=f"Encargo #{self.num} de Lola: vestido — sugerido {plata(90000)}")])

    def execute(self, action, ctx):
        return f"Tu presupuesto es de ${action.data['precio']}"

    def command(self, name, data, ctx):
        if name == "estado":
            e = next((e for e in self.lista if e["num"] == data.get("num")), None)
            if e is None:
                raise ActionError("no existe ese encargo")
            e["estado"] = data["estado"]
            return e
        if name != "owner_tasks":
            raise ActionError(name)
        out, today = [], ctx.today()
        for p in data.get("pending", []):
            if (p.get("action") or {}).get("type") == "enviar_presupuesto":
                n = p["action"]["data"]["num"]
                e = next((x for x in self.lista if x["num"] == n), {})
                urgent = bool(e.get("urgente"))
                out.append({"pending": p["id"], "bonus": 10 + (10 if urgent else 0),
                            "reason": "hay un cliente esperando el precio" + (" y el pedido es urgente" if urgent else ""),
                            "options": [{"title": f"Aprobar el precio sugerido ({plata(p['action']['data']['precio'])})",
                                         "detail": "sale de tu tabla de precios.", "recommended": True},
                                        {"title": "Cambiar el precio", "detail": "corregí el monto antes de aprobar."},
                                        {"title": "Rechazar y hablar con el cliente", "detail": "si no te cierra."}]})
        for e in self.lista:
            if e["estado"] == "presupuesto":
                continue
            days = (date.fromisoformat(e["entrega"]) - today).days
            if days < 0:
                score, reason = 90, f"se pasó la fecha de entrega hace {-days} día{'s' if days < -1 else ''}"
            elif days <= 3:
                score = 55 + (3 - days) * 8
                reason = "se entrega hoy" if days == 0 else "se entrega mañana" if days == 1 else f"se entrega en {days} días"
            elif days <= 7:
                score, reason = 35, f"se entrega en {days} días"
            else:
                continue
            out.append({"kind": "encargo", "ref": str(e["num"]), "title": f"Encargo #{e['num']} de {e['cliente']}: saco",
                        "reason": reason, "score": score, "contact": e.get("contacto")})
        return out


class Agenda(Cook):
    commands = {"owner_tasks": "turnos"}

    def command(self, name, data, ctx):
        return [{"kind": "turno", "title": "Turno hoy a las 16:00: medidas con Sofi", "reason": "es hoy", "score": 62}]


class Atencion(Cook):
    commands = {"owner_tasks": "reclamos"}

    def interest(self, msg, ctx):
        return 0.1

    def handle(self, msg, ctx):
        return Reply("pasalo", [Action("derivar_humano", {"texto": msg.text}, summary=f"Reclamo de {msg.name}: «llegó roto»")])

    def execute(self, action, ctx):
        return action.data.get("reply")

    def command(self, name, data, ctx):
        return [{"pending": p["id"], "bonus": 15, "reason": "es un cliente que pidió hablar con una persona",
                 "options": [{"title": "Escribirle vos, con calma", "detail": "pedile disculpas.", "recommended": True},
                             {"title": "Pedir más datos", "detail": "pedí foto o número de pedido."},
                             {"title": "Dejarlo como resuelto", "detail": "si ya lo hablaron."}]}
                for p in data.get("pending", []) if (p.get("action") or {}).get("type") == "derivar_humano"]


def _m(bid, cook, actions=None, commands=None):
    return manifest_from({"id": bid, "name": bid.title(), "version": "1.0.0", "contract": ">=2.1,<3",
                          "description": f"brigada {bid}", "cooks": [{"id": cook, "entry": f"x:{cook}"}],
                          "actions": actions or {}, "commands": commands or {"owner_tasks": {"read": True}}})


def e(num, cliente, entrega, estado="en_confeccion", urgente=False):
    return {"num": num, "cliente": cliente, "entrega": entrega, "estado": estado, "urgente": urgente, "contacto": f"w:{num}"}


def model_answers(answers, seen=None):
    it = iter(answers)

    def transport(url, body, headers):
        if seen is not None:
            seen.append(body["messages"][0]["content"])
        a = next(it)
        if isinstance(a, Exception):
            raise a
        return {"choices": [{"message": {"content": a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}}
    return transport


def system(lista=None, *, agenda=True, transport=None, num=9):
    gw = None
    if transport is not None:   # sin pausas por error: cada pregunta al modelo usa la respuesta siguiente del guion
        gw = ModelGateway(models_from({"providers": {"x": {"base_url": "https://ia.example/v1", "model": "m"}},
                                       "tiers": {"pago": [], "gratis": ["x"], "local": []},
                                       "roles": {"mando": ["gratis"], "voz": ["gratis"], "ruteo": ["gratis"]},
                                       "error_cooldown_seconds": 0}),
                          Usage(Store().space("_uso"), 1000, Clock()), transport=transport)
    inst = installation_from({"id": "c", "edition": "cloud", "identity": {"user": "Ana"}})
    clock = Clock(datetime(2026, 11, 18, 9, 0))
    orch = RaphaelOrchestrator({"mode": "secretary", "routing": {"fallback_cook": "atencion/atencion", "classifier": False}})
    rt = Runtime(inst, clock=clock, models=gw, orchestrator=orch)
    enc = Encargos(lista, num)
    rt.run(rt.mount(_m("encargos", "encargos", {"enviar_presupuesto": {"level": "aprobacion"}},
                       {"owner_tasks": {"read": True},
                        "estado": {"read": False, "description": "cambiar el estado de un encargo"}}),
                    {"encargos": enc}))
    if agenda:
        rt.run(rt.mount(_m("agenda", "agenda"), {"agenda": Agenda()}))
    rt.run(rt.mount(_m("atencion", "atencion", {"derivar_humano": {"level": "humano"}}), {"atencion": Atencion()}))
    return rt, clock, enc


def say(rt, text, session="app"):
    return rt.run(rt.talk_to_owner(text, session=session))


def kinds(rt):
    return [(p["action"] or {}).get("type") for p in rt.approvals.list()]


def with_two_pendings(**kw):
    rt, clock, enc = system(**kw)
    rt.run(rt.receive("whatsapp", "l", "quiero un vestido", "Lola"))
    rt.run(rt.receive("whatsapp", "m", "llegó roto, quiero hablar con alguien", "Marta"))
    return rt, clock, enc


def task(r, kind):
    return next(t for t in r.tasks if t["kind"] == kind)


# --- secretaria (portados de test_secretaria.py) ---------------------------------------------------------------------------
def test_dia_tranquilo():
    rt, _, _ = system(agenda=False)
    r = say(rt, "buen día")
    assert "Buen día, Ana" in r.text and "nada pendiente" in r.text


def test_resumen_numerado_y_ordenado_por_urgencia():
    rt, _, _ = system([e(1, "Pía", "2026-11-30"), e(2, "Rita", "2026-11-18"), e(3, "Luz", "2026-11-10")])
    r = say(rt, "Buen día, ¿qué tareas tenemos hoy?")
    assert [t["ref"] for t in r.tasks if t["kind"] == "encargo"] == ["3", "2"]       # el de 12 días no entra
    assert r.text.index("1)") < r.text.index("2)") and "Encargo #3 de Luz" in r.text.split("2)")[0]
    assert "se pasó la fecha de entrega hace 8 días" in r.tasks[0]["reason"]


def test_recomienda_la_mas_urgente_y_explica_por_que():
    rt, _, _ = system([e(1, "Pía", "2026-11-19"), e(2, "Rita", "2026-11-17")])
    say(rt, "hola")
    r = say(rt, "perfecto, ¿cuál me recomendás hacer primero?")
    assert "Te recomiendo la 1)" in r.text and "Rita" in r.text and "Porque se pasó la fecha" in r.text
    assert "Después seguiría con la 2)" in r.text


def test_siguiente_recorre_la_lista_y_avisa_el_final():
    rt, _, _ = system([e(1, "Pía", "2026-11-19"), e(2, "Rita", "2026-11-17")])
    say(rt, "hola")
    n = len(say(rt, "tareas").tasks)
    say(rt, "¿cuál primero?")
    texts = [say(rt, "¿y después?").text for _ in range(n)]
    assert "la 2)" in texts[0] and "la última" in texts[-1]


def test_pendiente_humano_pasa_adelante_y_la_ficha_trae_contexto_y_opciones():
    rt, clock, _ = system([e(1, "Pía", "2026-11-25")])
    rt.run(rt.receive("whatsapp", "w9", "me llegó roto, quiero hablar con alguien", "Marta"))
    clock.now = datetime(2026, 11, 18, 14, 0)                                     # lleva horas esperando
    r = say(rt, "qué hay hoy")
    assert r.tasks[0]["kind"] == "derivar_humano" and "pidió hablar con una persona" in r.tasks[0]["reason"]
    assert "lo dejaste esperando hace 5 h" in r.tasks[0]["reason"]
    f = say(rt, "contame la 1")
    assert "Contexto:" in f.text and "Qué podés hacer" in f.text and "(lo que yo haría)" in f.text
    assert f.card["pending"]["id"] == r.tasks[0]["pending"]
    assert any("me llegó roto" in m["text"] for m in f.card["conversation"])
    assert f.card["options"][0]["recommended"] and len(f.card["options"]) == 3


def test_presupuesto_urgente_suma_prioridad_y_trae_sus_opciones():
    rt, _, _ = system([e(9, "Lola", "2026-11-20", estado="presupuesto", urgente=True)])
    rt.run(rt.receive("whatsapp", "w3", "quiero un vestido", "Lola"))
    ts = say(rt, "tareas").tasks
    pres = next(x for x in ts if x["kind"] == "enviar_presupuesto")
    assert "urgente" in pres["reason"] and pres["score"] == 60
    assert "Aprobar el precio sugerido ($ 90.000)" in say(rt, f"la {pres['id']}").text


def test_turno_de_hoy_figura():
    rt, _, _ = system()
    assert any(t["kind"] == "turno" and "16:00" in t["title"] for t in say(rt, "resumen").tasks)


def test_numero_inexistente_y_frase_que_no_entiende():
    rt, _, _ = system([e(1, "Pía", "2026-11-18")])
    say(rt, "hola")
    assert "No tengo una tarea 7" in say(rt, "contame la 7").text
    assert "No te entendí" in say(rt, "asdf qwerty").text


def test_sin_ia_no_inventa_resumen_y_con_ia_lo_usa():
    seen = []
    rt, _, _ = system(transport=model_answers(["Marta recibió algo roto y quiere solución.", "Podés tomártelo."], seen))
    rt.run(rt.receive("whatsapp", "w9", "me llegó roto, quiero hablar con alguien", "Marta"))
    say(rt, "hola")
    f = say(rt, "contame la 1")
    assert "Marta recibió algo roto" in f.text and seen
    free = say(rt, "che, ¿y si me tomo el viernes libre?")
    assert free.text and len(seen) >= 2
    rt2, _, _ = system()
    rt2.run(rt2.receive("whatsapp", "w9", "me llegó roto, quiero hablar con alguien", "Marta"))
    say(rt2, "hola")
    assert "lo último que dijo: «me llegó roto" in say(rt2, "contame la 1").text


def test_sin_orquestador_el_harness_responde_amable():
    rt = Runtime(installation_from({"id": "c", "edition": "cloud"}), clock=Clock())
    assert "Todavía no tengo un orquestador" in rt.run(rt.talk_to_owner("hola")).text


def test_una_brigada_que_manda_tareas_rotas_no_rompe_la_lista_y_queda_avisado():
    class Mala(Cook):
        commands = {"owner_tasks": "x"}

        def command(self, name, data, ctx):
            return [{"title": ""}, "texto suelto", {"pending": 999, "bonus": 30}, {"title": "Ok", "score": 20}]

    rt, _, _ = system()
    rt.run(rt.mount(_m("mala", "mala"), {"mala": Mala()}))
    r = say(rt, "tareas")
    assert any(t["title"] == "Ok" for t in r.tasks)
    assert any("Mala mandó 3 tarea(s)" in w for w in r.meta["warnings"])


# --- confirmación (portados de test_agente.py) ----------------------------------------------------------------------------
def test_aprobar_pide_confirmacion_y_recien_con_el_si_ejecuta():
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas"), "enviar_presupuesto")["id"]
    r = say(rt, f"aprobá la {n}")
    assert "¿Confirmo?" in r.text and "aprobar" in r.text and "enviar_presupuesto" in kinds(rt)   # todavía no se hizo
    ok = say(rt, "sí")
    assert "Aprobada" in ok.text and "enviar_presupuesto" not in kinds(rt)
    assert any("presupuesto es de $90000" in s["text"] for s in rt.outgoing("whatsapp:l"))


def test_decir_que_no_cancela_y_otra_frase_tambien():
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas"), "enviar_presupuesto")["id"]
    say(rt, f"aprobá la {n}")
    assert "no hago nada" in say(rt, "no").text and "enviar_presupuesto" in kinds(rt)
    say(rt, f"aprobá la {n}")
    say(rt, "¿qué tareas quedan?")                     # cambió de tema: la propuesta se descarta
    say(rt, "sí")
    assert "enviar_presupuesto" in kinds(rt)


def test_rechazar_y_responder_a_un_cliente():
    rt, _, _ = with_two_pendings()
    n_h = task(say(rt, "tareas"), "derivar_humano")["id"]
    say(rt, f"respondele a la {n_h}: Hola Marta, perdón por el problema, ¿me mandás una foto?")
    assert "dejé resuelta" in say(rt, "dale").text
    assert any("perdón por el problema" in s["text"] for s in rt.outgoing("whatsapp:m"))
    say(rt, f"rechazá la {task(say(rt, 'tareas'), 'enviar_presupuesto')['id']}")
    assert "Rechazada" in say(rt, "sí").text and "enviar_presupuesto" not in kinds(rt)


def test_no_se_puede_aprobar_lo_que_resuelve_una_persona():
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas"), "derivar_humano")["id"]
    r = say(rt, f"aprobá la {n}")
    assert "la tenés que resolver vos" in r.text and "¿Confirmo?" not in r.text


def test_aprobar_por_el_numero_real_del_pendiente():
    rt, _, _ = with_two_pendings()
    pid = next(p["id"] for p in rt.approvals.list() if p["action"]["type"] == "enviar_presupuesto")
    r = say(rt, f"aprobá el #{pid}")
    assert "¿Confirmo?" in r.text and f"#{pid}" in r.text
    assert "Aprobada" in say(rt, "ok").text and "enviar_presupuesto" not in kinds(rt)
    assert "ya no está pendiente" in say(rt, f"aprobá el #{pid}").text


def test_orden_sobre_una_tarea_que_no_existe():
    rt, _, _ = with_two_pendings()
    say(rt, "tareas")
    assert "No sé a qué tarea" in say(rt, "aprobá la 40").text


def test_si_el_pendiente_se_cerro_mientras_esperaba_el_si_no_se_hace_dos_veces():
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas"), "enviar_presupuesto")["id"]
    say(rt, f"aprobá la {n}")
    pid = next(p["id"] for p in rt.approvals.list() if p["action"]["type"] == "enviar_presupuesto")
    rt.run(rt.approve(pid, who="otra sesión"))
    assert "ya no está abierto" in say(rt, "sí").text
    assert len([s for s in rt.outgoing("whatsapp:l") if "presupuesto" in s["text"]]) == 1


# --- con IA (portados de test_agente.py) -----------------------------------------------------------------------------------
def test_la_ia_entiende_una_frase_libre_y_propone_pero_no_ejecuta_hasta_el_si():
    rt0, _, _ = with_two_pendings()
    n = task(say(rt0, "tareas"), "enviar_presupuesto")["id"]
    rt, _, _ = with_two_pendings(transport=model_answers(
        [{"decir": "Dale, apruebo el presupuesto de Lola.", "hacer": [{"accion": "aprobar", "tarea": n}]}]))
    r = say(rt, "che mirá, el vestido de Lola está bien de precio, mandáselo y listo")
    assert "Dale, apruebo" in r.text and "¿Confirmo?" in r.text and "enviar_presupuesto" in kinds(rt)
    assert "Aprobada" in say(rt, "sí").text and "enviar_presupuesto" not in kinds(rt)


def test_la_ia_puede_pedir_el_resumen_y_se_muestra_la_lista_real():
    rt, _, _ = with_two_pendings(transport=model_answers(
        [{"decir": "Buen día, mirá lo que hay:", "hacer": [{"accion": "resumen_dia"}]}]))
    r = say(rt, "arrancamos el día y contame bien todo lo que hay por favor")
    assert r.text.startswith("Buen día, mirá") and "1)" in r.text and r.tasks


@pytest.mark.parametrize("plan", [[{"accion": "aprobar", "tarea": 77}], [{"accion": "borrar_todo"}],
                                  [{"accion": "aprobar", "pending": 999}], [{"accion": "comando", "brigada": "encargos",
                                                                              "comando": "borrar_base"}],
                                  [{"accion": "escribir", "contacto": "whatsapp:desconocido", "texto": "hola"}]])
def test_lo_que_la_ia_inventa_no_se_propone_ni_se_ejecuta(plan):
    rt, _, _ = with_two_pendings(transport=model_answers([{"decir": "", "hacer": plan}]))
    before = list(rt.approvals.list())
    r = say(rt, "aprobá todo lo que quede por favor, dale, hacelo ya")
    assert "¿Confirmo?" not in r.text and rt.approvals.list() == before
    assert not any(s["contact"] == "whatsapp:desconocido" for s in rt.outgoing())


def test_la_ia_responde_en_prosa_o_con_json_en_bloque_o_se_cae():
    rt, _, _ = with_two_pendings(transport=model_answers([
        "Esta semana te conviene priorizar entregas.", '```json\n{"decir": "ok", "hacer": []}\n```',
        RuntimeError("sin red"), RuntimeError("sin red")]))
    assert "priorizar entregas" in say(rt, "che, ¿cómo ves la semana que viene para mí?").text
    assert say(rt, "contame cómo ves la semana que viene en general").text == "ok"
    assert "No te entendí" in say(rt, "che, ¿cómo ves la semana que viene para mí? contame todo").text


def test_la_ia_ve_las_tareas_reales_y_las_ordenes_quedan_auditadas():
    seen = []
    rt, _, _ = with_two_pendings(lista=[e(4, "Rita", "2026-11-18")],
                                 transport=model_answers([{"decir": "ok", "hacer": []}] * 5, seen))
    say(rt, "che, ¿qué opinás de cómo viene todo este mes en general?")
    assert "Encargo #4 de Rita" in seen[0] and "derivar_humano" in seen[0] and "Ana" in seen[0]
    assert "encargos: estado — cambiar el estado de un encargo" in seen[0]
    n = task(say(rt, "tareas"), "enviar_presupuesto")["id"]
    say(rt, f"aprobá la {n}")
    say(rt, "sí")
    assert any(a["what"] == "orden_confirmada" and a["orden"] == "approve" for a in rt.audit.entries())
    assert any(a["what"] == "aprobado" and a["who"] == "Ana" for a in rt.audit.entries())


def test_cambiar_estado_de_un_encargo_es_un_comando_declarado_con_confirmacion():
    rt, _, enc = with_two_pendings(lista=[e(4, "Rita", "2026-11-18")], transport=model_answers([
        {"decir": "", "hacer": [{"accion": "comando", "brigada": "encargos", "comando": "estado",
                                "datos": {"num": 4, "estado": "listo"}}]},
        {"decir": "", "hacer": [{"accion": "comando", "brigada": "encargos", "comando": "estado",
                                "datos": {"num": 99, "estado": "entregado"}}]}]))
    r = say(rt, "marcá el encargo 4 como listo que ya lo terminé")
    assert "¿Confirmo?" in r.text and enc.lista[0]["estado"] == "en_confeccion"   # todavía no
    assert "Hecho" in say(rt, "sí").text and enc.lista[0]["estado"] == "listo"
    say(rt, "pasá el encargo 99 a entregado que ya lo retiraron")
    assert "no existe ese encargo" in say(rt, "sí").text


# --- ninguna escritura sin "sí" -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("reply", ["sí, pero esperá", "dale que sí, mañana te aviso cómo sigue todo", "quizás",
                                   "¿qué tareas quedan?", "aprobá la 1", "SÍ!!! no, mentira, no", "si x"])
def test_solo_un_si_explicito_ejecuta(reply):
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas"), "enviar_presupuesto")["id"]
    say(rt, f"aprobá la {n}")
    out_before = len(rt.outgoing())
    say(rt, reply)
    assert "enviar_presupuesto" in kinds(rt) or reply == "aprobá la 1"
    assert not any(a["what"] == "aprobado" for a in rt.audit.entries()) or reply == "aprobá la 1"
    assert len(rt.outgoing()) == out_before


def test_las_frases_de_si_y_no():
    for yes in ("sí", "Si", "dale", "ok", "confirmo", "sí, confirmá", "de una", "hacelo"):
        assert confirm.is_yes(yes), yes
    for not_yes in ("sí, pero", "no", "si mañana", "dale con otra cosa", "", "sí sí sí sí sí"):
        assert not confirm.is_yes(not_yes), not_yes
    assert confirm.is_no("no") and confirm.is_no("cancelá") and not confirm.is_no("nos vemos mañana")


def test_las_sesiones_no_se_cruzan_un_si_en_otra_sesion_no_ejecuta():
    rt, _, _ = with_two_pendings()
    n = task(say(rt, "tareas", session="app"), "enviar_presupuesto")["id"]
    say(rt, f"aprobá la {n}", session="app")
    say(rt, "sí", session="whatsapp-ana")
    assert "enviar_presupuesto" in kinds(rt)
    assert "Aprobada" in say(rt, "sí", session="app").text


# --- mensajes de clientes en modo secretaria ---------------------------------------------------------------------------------
def test_los_clientes_los_rutea_el_orquestador_con_la_red_al_final():
    rt, _, _ = system()
    assert rt.run(rt.receive("whatsapp", "x", "quiero un vestido para la boda", "Eva")) == ["ok"]
    assert rt.run(rt.receive("whatsapp", "y", "llegó todo mal", "Ola")) == ["pasalo"]
    assert asyncio.iscoroutinefunction(RaphaelOrchestrator.route)
