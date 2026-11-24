"""El secretario ejecuta lo que la dueña ordena (siempre con confirmación), con reglas o con IA."""

import json
from datetime import datetime

from raphael_harness import Accion, Brigada, ErrorDeAccion, Mensaje, Nivel, Respuesta
from raphael_harness.testing import Reloj, armar
from raphael_orquestador import OrquestadorRaphael


class Encargos(Brigada):
    nombre = "encargos"
    version = "1"
    acciones = {"enviar_presupuesto": Nivel.APROBACION}

    def __init__(self):
        self.lista = [{"num": 4, "cliente": "Rita", "descripcion": "saco", "entrega": "2026-11-18", "estado": "en_confeccion",
                       "urgente": False, "contacto": "whatsapp:r"}]

    def interes(self, msg, ctx):
        return 1.0 if "vestido" in msg.texto else 0.0

    def comando(self, nombre, datos, ctx):
        if nombre == "listar":
            return self.lista
        if nombre == "ver":
            return next(e for e in self.lista if e["num"] == datos["num"])
        if nombre == "estado":
            e = next((e for e in self.lista if e["num"] == datos["num"]), None)
            if e is None:
                raise ErrorDeAccion("no existe ese encargo")
            e["estado"] = datos["estado"]
            return e
        return super().comando(nombre, datos, ctx)

    def atender(self, msg, ctx):
        return Respuesta("ok", [Accion("enviar_presupuesto", {"num": 9, "precio": 90000}, "Encargo #9 de Lola: vestido", destino=msg.contacto)])

    def ejecutar(self, accion, ctx):
        return f"Tu presupuesto es de ${accion.datos['precio']}"


class Atencion(Brigada):
    nombre = "atencion"
    version = "1"
    acciones = {"derivar_humano": Nivel.HUMANO}

    def interes(self, msg, ctx):
        return 0.1

    def atender(self, msg, ctx):
        return Respuesta("pasalo", [Accion("derivar_humano", {"texto": msg.texto}, "Reclamo de Marta", destino=msg.contacto)])

    def ejecutar(self, accion, ctx):
        return accion.datos.get("respuesta")


def sistema(ia=None):
    kw = {}
    if ia is not None:
        kw = {"config_modelos": {"planes": {"basico": {"secretaria": "x"}}, "proveedores": {"x": {"base_url": "http://ia", "model": "m"}}},
              "transporte_ia": ia}
    enc = Encargos()
    h = armar(enc, Atencion(), orquestador=OrquestadorRaphael(), reloj=Reloj(datetime(2026, 11, 18, 9, 0)), **kw)
    h.recibir("whatsapp", "l", "quiero un vestido", "Lola")      # → pendiente de aprobar (presupuesto)
    h.recibir("whatsapp", "m", "llegó roto, quiero hablar con alguien", "Marta")   # → pendiente humano
    return h, enc


def lista(h):
    return h.hablar_con_duena("tareas")


def tarea(r, tipo):
    return next(t for t in r.tareas if t["tipo"] == tipo)


def hablar_ia(contenido_por_turno):
    turnos = iter(contenido_por_turno)

    def ia(url, cuerpo, headers):
        c = next(turnos)
        if isinstance(c, Exception):
            raise c
        return {"choices": [{"message": {"content": c if isinstance(c, str) else json.dumps(c)}}], "usage": {"prompt_tokens": 9, "completion_tokens": 9}}
    return ia


# ---------------------------------------------------------------- por reglas (sin IA)
def test_aprobar_pide_confirmacion_y_recien_con_el_si_ejecuta():
    h, _ = sistema()
    n = tarea(lista(h), "enviar_presupuesto")["id"]
    r = h.hablar_con_duena(f"aprobá la {n}")
    assert "¿Confirmo?" in r.texto and "aprobar" in r.texto
    assert any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())      # todavía no se hizo
    ok = h.hablar_con_duena("sí")
    assert "Aprobada" in ok.texto
    assert not any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())
    assert any("presupuesto es de $90000" in s["texto"] for s in h.salientes("whatsapp:l"))


def test_decir_que_no_cancela_y_otra_frase_tambien():
    h, _ = sistema()
    n = tarea(lista(h), "enviar_presupuesto")["id"]
    h.hablar_con_duena(f"aprobá la {n}")
    assert "no hago nada" in h.hablar_con_duena("no").texto
    assert any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())
    h.hablar_con_duena(f"aprobá la {n}")
    h.hablar_con_duena("¿qué tareas quedan?")                     # cambió de tema: la propuesta se descarta
    h.hablar_con_duena("sí")
    assert any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())


def test_rechazar_y_responder_a_un_cliente():
    h, _ = sistema()
    r = lista(h)
    n_h, n_p = tarea(r, "derivar_humano")["id"], tarea(r, "enviar_presupuesto")["id"]
    h.hablar_con_duena(f"respondele a la {n_h}: Hola Marta, perdón por el problema, ¿me mandás una foto?")
    ok = h.hablar_con_duena("dale")
    assert "dejé resuelta" in ok.texto
    assert any("perdón por el problema" in s["texto"] for s in h.salientes("whatsapp:m"))
    r = lista(h)
    h.hablar_con_duena(f"rechazá la {tarea(r, 'enviar_presupuesto')['id']}")
    assert "Rechazada" in h.hablar_con_duena("sí").texto
    assert not [p for p in h.pendientes() if p["accion"]["tipo"] == "enviar_presupuesto"]


def test_no_se_puede_aprobar_lo_que_resuelve_una_persona():
    h, _ = sistema()
    n = tarea(lista(h), "derivar_humano")["id"]
    r = h.hablar_con_duena(f"aprobá la {n}")
    assert "la tenés que resolver vos" in r.texto and "¿Confirmo?" not in r.texto


def test_cambiar_estado_de_un_encargo():
    h, enc = sistema()
    h.hablar_con_duena("marcá el encargo 4 como listo")
    assert enc.lista[0]["estado"] == "en_confeccion"              # todavía no
    assert "listo" in h.hablar_con_duena("sí").texto
    assert enc.lista[0]["estado"] == "listo"
    assert "no existe ese encargo" in (h.hablar_con_duena("pasá el encargo 99 a entregado").texto + h.hablar_con_duena("sí").texto)


def test_orden_sobre_una_tarea_que_no_existe():
    h, _ = sistema()
    lista(h)
    assert "No sé a qué tarea" in h.hablar_con_duena("aprobá la 40").texto


# ---------------------------------------------------------------- con IA
def test_la_ia_entiende_una_frase_libre_y_propone_pero_no_ejecuta_hasta_el_si():
    h0, _ = sistema()
    n = tarea(lista(h0), "enviar_presupuesto")["id"]               # el id depende del orden del día: se calcula con el mismo escenario
    h, _ = sistema(ia=hablar_ia([{"decir": "Dale, apruebo el presupuesto de Lola.", "hacer": [{"accion": "aprobar", "tarea": n}]}]))
    r = h.hablar_con_duena("che mirá, el vestido de Lola está bien de precio, mandáselo y listo")
    assert "Dale, apruebo" in r.texto and "¿Confirmo?" in r.texto
    assert any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())
    assert "Aprobada" in h.hablar_con_duena("sí").texto
    assert not any(p["accion"]["tipo"] == "enviar_presupuesto" for p in h.pendientes())


def test_la_ia_puede_pedir_el_resumen_y_se_muestra_la_lista_real():
    h, _ = sistema(ia=hablar_ia([{"decir": "Buen día, mirá lo que hay:", "hacer": [{"accion": "resumen_dia"}]}]))
    r = h.hablar_con_duena("arrancamos el día y contame bien todo lo que hay por favor")
    assert r.texto.startswith("Buen día, mirá") and "1)" in r.texto and r.tareas


def test_la_ia_inventa_una_tarea_y_no_pasa_nada():
    h, _ = sistema(ia=hablar_ia([{"decir": "", "hacer": [{"accion": "aprobar", "tarea": 77}]}]))
    antes = len(h.pendientes())
    r = h.hablar_con_duena("aprobá todo lo que quede por favor, dale")
    assert "¿Confirmo?" not in r.texto and len(h.pendientes()) == antes


def test_la_ia_no_puede_ejecutar_acciones_que_no_existen():
    h, _ = sistema(ia=hablar_ia([{"decir": "Listo, borré todo.", "hacer": [{"accion": "borrar_todo"}]}]))
    r = h.hablar_con_duena("borrá todos los pendientes de la base de datos ahora")
    assert "¿Confirmo?" not in r.texto and len(h.pendientes()) == 2


def test_la_ia_responde_en_prosa_o_con_json_en_bloque_o_se_cae():
    h, _ = sistema(ia=hablar_ia(["Esta semana te conviene priorizar entregas.",
                                  '```json\n{"decir": "ok", "hacer": []}\n```',
                                  RuntimeError("sin red")]))
    assert "priorizar entregas" in h.hablar_con_duena("che, ¿cómo ves la semana que viene para mí?").texto
    assert h.hablar_con_duena("contame cómo ves la semana que viene en general").texto == "ok"
    r = h.hablar_con_duena("che, ¿cómo ves la semana que viene para mí? contame todo")      # el modelo falla → reglas
    assert "No te entendí" in r.texto


def test_la_ia_ve_las_tareas_reales_y_las_ordenes_quedan_auditadas():
    vistos = []

    def ia(url, cuerpo, headers):
        vistos.append(cuerpo["messages"][0]["content"])
        return {"choices": [{"message": {"content": json.dumps({"decir": "ok", "hacer": []})}}]}

    h, _ = sistema(ia=ia)
    h.hablar_con_duena("che, ¿qué opinás de cómo viene todo este mes en general?")
    assert "Encargo #4 de Rita" in vistos[0] and "derivar_humano" in vistos[0] and "Ana" in vistos[0]
    n = tarea(lista(h), "enviar_presupuesto")["id"]
    h.hablar_con_duena(f"aprobá la {n}")
    h.hablar_con_duena("sí")
    assert any(a["que"] == "orden_duena" and a["orden"] == "aprobar" for a in h.registro())
