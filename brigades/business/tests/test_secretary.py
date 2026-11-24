"""La Secretaria del orquestador (rol genérico, modo `secretary`) con las tareas reales de esta brigada.

Portados de `raphael-orquestador/tests/test_secretaria.py` (10) y `test_agente.py` (12). Lo del negocio (qué es un
encargo vencido, una seña, un turno, los bonus por tipo y los textos de las opciones) lo da el cocinero `tareas` con su
comando `owner_tasks`; el orquestador ordena, explica y ejecuta con confirmación."""

from datetime import datetime

import pytest
from kit import System, answers
from raphael_core.testing import Clock

SHORT = {"orders": {"required_steps": ["prenda", "nombre"]}}


def seed_order(x, num, client, due, status="en_confeccion", urgent=False):
    x.ctx("encargos").shared.put("orders", num, {
        "number": num, "client": client, "description": "saco", "due": due, "status": status, "urgent": urgent,
        "contact": f"whatsapp:{num}", "channel": "whatsapp", "price": None, "deposit": None, "paid": 0})


def system(orders=(), **kw):
    x = System(kw.pop("config", SHORT), clock=Clock(datetime(2026, 11, 18, 9, 0)), **kw)
    for o in orders:
        seed_order(x, *o)
    return x


def with_two_pendings(orders=(), **kw):
    x = system(orders, **kw)
    x.chat("quiero un vestido a medida", "Lola", sender="l")                         # -> presupuesto por aprobar
    x.receive("llegó roto, quiero hablar con alguien", sender="m", name="Marta")      # -> pendiente humano
    return x


def task(r, kind):
    return next(t for t in r.tasks if t["kind"] == kind)


def kinds(x):
    return [(p["action"] or {}).get("type") for p in x.pending()]


# --- secretaria (test_secretaria.py) ------------------------------------------------------------------------------------
def test_dia_tranquilo():
    r = system().say("buen día")
    assert "Buen día, Ana" in r.text and "nada pendiente" in r.text


def test_resumen_numerado_y_ordenado_por_urgencia():
    x = system([(1, "Pía", "2026-11-30"), (2, "Rita", "2026-11-18"), (3, "Luz", "2026-11-10")])
    r = x.say("Buen día, ¿qué tareas tenemos hoy?")
    assert [t["ref"] for t in r.tasks if t["kind"].startswith("encargo_")] == ["3", "2"]   # el de 12 días no entra
    assert r.text.index("1)") < r.text.index("2)") and "Encargo #3 de Luz" in r.text.split("2)")[0]
    assert "se pasó la fecha de entrega hace 8 días" in r.tasks[0]["reason"]


def test_recomienda_la_mas_urgente_y_explica_por_que():
    x = system([(1, "Pía", "2026-11-19"), (2, "Rita", "2026-11-17")])
    x.say("hola")
    r = x.say("perfecto, ¿cuál me recomendás hacer primero?")
    assert "Te recomiendo la 1)" in r.text and "Rita" in r.text and "Porque se pasó la fecha" in r.text
    assert "Después seguiría con la 2)" in r.text


def test_siguiente_recorre_la_lista_y_avisa_el_final():
    x = system([(1, "Pía", "2026-11-19"), (2, "Rita", "2026-11-17")])
    x.say("hola")
    n = len(x.say("tareas").tasks)
    x.say("¿cuál primero?")
    texts = [x.say("¿y después?").text for _ in range(n)]
    assert "la 2)" in texts[0] and "la última" in texts[-1]


def test_pendiente_humano_pasa_adelante_y_la_ficha_trae_contexto_y_opciones():
    x = system([(1, "Pía", "2026-11-25")])
    x.receive("me llegó roto, quiero hablar con alguien", sender="w9", name="Marta")
    x.clock.now = datetime(2026, 11, 18, 14, 0)                                     # lleva horas esperando
    r = x.say("qué hay hoy")
    assert r.tasks[0]["kind"] == "derivar_humano" and "pidió hablar con una persona" in r.tasks[0]["reason"]
    f = x.say("contame la 1")
    assert "Contexto:" in f.text and "Qué podés hacer" in f.text and "(lo que yo haría)" in f.text
    assert f.card["pending"]["id"] == r.tasks[0]["pending"]
    assert any("me llegó roto" in m["text"] for m in f.card["conversation"])
    assert f.card["options"][0]["recommended"] and len(f.card["options"]) == 3
    assert f.card["options"][0]["title"] == "Escribirle vos, con calma"


def test_presupuesto_urgente_suma_prioridad_y_trae_sus_opciones():
    x = system(config={"orders": {"required_steps": ["prenda", "fecha", "nombre"]}})
    x.chat("quiero un vestido a medida", "el 25 de noviembre", "Lola", sender="w3")
    pres = task(x.say("tareas"), "enviar_presupuesto")
    assert "urgente" in pres["reason"] and pres["score"] == 60          # 40 aprobación + 10 precio + 10 urgente
    assert "Aprobar el precio sugerido ($ 150.000)" in x.say(f"la {pres['id']}").text


def test_turno_de_hoy_figura():
    x = system()
    x.ctx("agenda").shared.put("appointments", "2026-11-18 16:00", {
        "date": "2026-11-18", "time": "16:00", "reason": "medidas", "name": "Sofi", "contact": "w:1", "reminded": True})
    assert any(t["kind"] == "turno" and "16:00" in t["title"] for t in x.say("resumen").tasks)


def test_numero_inexistente_y_frase_que_no_entiende():
    x = system([(1, "Pía", "2026-11-18")])
    x.say("hola")
    assert "No tengo una tarea 7" in x.say("contame la 7").text
    assert "No te entendí" in x.say("asdf qwerty").text


def test_sin_ia_no_inventa_resumen_y_con_ia_lo_usa():
    seen = []
    x = system(transport=answers(["Marta recibió algo roto y quiere solución.", "Podés tomártelo."], seen))
    x.receive("me llegó roto, quiero hablar con alguien", sender="w9", name="Marta")
    x.say("hola")
    f = x.say("contame la 1")
    assert "Marta recibió algo roto" in f.text and seen
    assert x.say("che, ¿y si me tomo el viernes libre?").text and len(seen) >= 2
    y = system()
    y.receive("me llegó roto, quiero hablar con alguien", sender="w9", name="Marta")
    y.say("hola")
    assert "lo último que dijo: «me llegó roto" in y.say("contame la 1").text


def test_sin_orquestador_el_harness_responde_amable():
    assert "Todavía no tengo un orquestador" in System(orchestrator=False).say("hola").text


# --- confirmación por reglas (test_agente.py) ---------------------------------------------------------------------------
def test_aprobar_pide_confirmacion_y_recien_con_el_si_ejecuta():
    x = with_two_pendings()
    n = task(x.say("tareas"), "enviar_presupuesto")["id"]
    r = x.say(f"aprobá la {n}")
    assert "¿Confirmo?" in r.text and "aprobar" in r.text and "enviar_presupuesto" in kinds(x)   # todavía no
    assert "Aprobada" in x.say("sí").text and "enviar_presupuesto" not in kinds(x)
    assert any("$ 150.000" in t and "seña" in t for t in x.out("whatsapp:l"))


def test_decir_que_no_cancela_y_otra_frase_tambien():
    x = with_two_pendings()
    n = task(x.say("tareas"), "enviar_presupuesto")["id"]
    x.say(f"aprobá la {n}")
    assert "no hago nada" in x.say("no").text and "enviar_presupuesto" in kinds(x)
    x.say(f"aprobá la {n}")
    x.say("¿qué tareas quedan?")                     # cambió de tema: la propuesta se descarta
    x.say("sí")
    assert "enviar_presupuesto" in kinds(x)


def test_rechazar_y_responder_a_un_cliente():
    x = with_two_pendings()
    n_h = task(x.say("tareas"), "derivar_humano")["id"]
    x.say(f"respondele a la {n_h}: Hola Marta, perdón por el problema, ¿me mandás una foto?")
    assert "dejé resuelta" in x.say("dale").text
    assert any("perdón por el problema" in t for t in x.out("whatsapp:m"))
    x.say(f"rechazá la {task(x.say('tareas'), 'enviar_presupuesto')['id']}")
    assert "Rechazada" in x.say("sí").text and "enviar_presupuesto" not in kinds(x)


def test_no_se_puede_aprobar_lo_que_resuelve_una_persona():
    x = with_two_pendings()
    n = task(x.say("tareas"), "derivar_humano")["id"]
    r = x.say(f"aprobá la {n}")
    assert "la tenés que resolver vos" in r.text and "¿Confirmo?" not in r.text


def test_cambiar_estado_de_un_encargo_es_un_comando_declarado_con_confirmacion():
    x = with_two_pendings([(4, "Rita", "2026-11-18")], transport=answers([
        {"decir": "", "hacer": [{"accion": "comando", "brigada": "empresas", "comando": "estado",
                                "datos": {"number": 4, "status": "listo"}}]},
        {"decir": "", "hacer": [{"accion": "comando", "brigada": "empresas", "comando": "estado",
                                "datos": {"number": 99, "status": "entregado"}}]}]))
    r = x.say("marcá el encargo 4 como listo que ya lo terminé")
    assert "¿Confirmo?" in r.text and x.cmd("encargos", "ver", {"number": 4})["status"] == "en_confeccion"   # todavía no
    assert "Hecho" in x.say("sí").text and x.cmd("encargos", "ver", {"number": 4})["status"] == "listo"
    assert any("está listo" in t for t in x.out("whatsapp:4"))                       # Avisos le escribió solo
    x.say("pasá el encargo 99 a entregado que ya lo retiraron")
    assert "no existe el encargo #99" in x.say("sí").text


def test_orden_sobre_una_tarea_que_no_existe():
    x = with_two_pendings()
    x.say("tareas")
    assert "No sé a qué tarea" in x.say("aprobá la 40").text


# --- con IA (test_agente.py) --------------------------------------------------------------------------------------------
def test_la_ia_entiende_una_frase_libre_y_propone_pero_no_ejecuta_hasta_el_si():
    n = task(with_two_pendings().say("tareas"), "enviar_presupuesto")["id"]
    x = with_two_pendings(transport=answers(
        [{"decir": "Dale, apruebo el presupuesto de Lola.", "hacer": [{"accion": "aprobar", "tarea": n}]}]))
    r = x.say("che mirá, el vestido de Lola está bien de precio, mandáselo y listo")
    assert "Dale, apruebo" in r.text and "¿Confirmo?" in r.text and "enviar_presupuesto" in kinds(x)
    assert "Aprobada" in x.say("sí").text and "enviar_presupuesto" not in kinds(x)


def test_la_ia_puede_pedir_el_resumen_y_se_muestra_la_lista_real():
    x = with_two_pendings(transport=answers([{"decir": "Buen día, mirá lo que hay:", "hacer": [{"accion": "resumen_dia"}]}]))
    r = x.say("arrancamos el día y contame bien todo lo que hay por favor")
    assert r.text.startswith("Buen día, mirá") and "1)" in r.text and r.tasks


def test_la_ia_inventa_una_tarea_y_no_pasa_nada():
    x = with_two_pendings(transport=answers([{"decir": "", "hacer": [{"accion": "aprobar", "tarea": 77}]}]))
    before = x.pending()
    r = x.say("aprobá todo lo que quede por favor, dale")
    assert "¿Confirmo?" not in r.text and x.pending() == before


@pytest.mark.parametrize("plan", [[{"accion": "borrar_todo"}],
                                  [{"accion": "comando", "brigada": "empresas", "comando": "borrar_base"}]])
def test_la_ia_no_puede_ejecutar_acciones_que_no_existen(plan):
    x = with_two_pendings(transport=answers([{"decir": "Listo, borré todo.", "hacer": plan}]))
    r = x.say("borrá todos los pendientes de la base de datos ahora")
    assert "¿Confirmo?" not in r.text and len(x.pending()) == 2


def test_la_ia_responde_en_prosa_o_con_json_en_bloque_o_se_cae():
    x = with_two_pendings(transport=answers(["Esta semana te conviene priorizar entregas.",
                                             '```json\n{"decir": "ok", "hacer": []}\n```',
                                             RuntimeError("sin red"), RuntimeError("sin red")]))
    assert "priorizar entregas" in x.say("che, ¿cómo ves la semana que viene para mí?").text
    assert x.say("contame cómo ves la semana que viene en general").text == "ok"
    assert "No te entendí" in x.say("che, ¿cómo ves la semana que viene para mí? contame todo").text


def test_la_ia_ve_las_tareas_reales_y_las_ordenes_quedan_auditadas():
    seen = []
    x = with_two_pendings([(4, "Rita", "2026-11-18")], transport=answers([{"decir": "ok", "hacer": []}] * 5, seen))
    x.say("che, ¿qué opinás de cómo viene todo este mes en general?")
    assert "Encargo #4 de Rita" in seen[0] and "derivar_humano" in seen[0] and "Ana" in seen[0]
    assert "estado" in seen[0]                                           # el comando de escritura se ofrece, con su OK
    n = task(x.say("tareas"), "enviar_presupuesto")["id"]
    x.say(f"aprobá la {n}")
    x.say("sí")
    assert any(a["what"] == "orden_confirmada" and a["orden"] == "approve" for a in x.rt.audit.entries())
    assert any(a["what"] == "aprobado" and a["who"] == "Ana" for a in x.rt.audit.entries())
