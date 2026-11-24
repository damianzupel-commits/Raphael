from raphael_atencion import Atencion
from raphael_harness.testing import armar

PERFIL = {"informacion": {"horarios": "Lunes a sábado de 10 a 19", "envios": "Enviamos a todo el país por correo",
                          "medios_pago": ["transferencia"], "faq": [
                              {"pregunta": "¿Trabajan con tela de la clienta?", "respuesta": "Sí, podés traer tu tela.",
                               "palabras": ["mi tela"]}]}}


def h():
    return armar(Atencion(), perfil=PERFIL)


def test_responde_con_lo_cargado():
    assert h().recibir("whatsapp", "1", "¿Qué horario tienen?") == ["Lunes a sábado de 10 a 19."]
    assert "todo el país" in h().recibir("whatsapp", "1", "hacen envíos a Córdoba?")[0]
    assert h().recibir("whatsapp", "1", "puedo llevar mi tela?") == ["Sí, podés traer tu tela."]


def test_no_inventa_anota_la_duda_para_la_duena():
    x = h()
    out = x.recibir("whatsapp", "1", "¿Hacen arreglos de ruedos?")
    assert out == ["Eso te lo confirma Ana personalmente, ya se lo anoto 😊"]
    [p] = x.pendientes()
    assert p["nivel"] == "humano" and p["accion"]["tipo"] == "responder_duda"
    x.resolver(p["id"], "Sí, hacemos ruedos desde $ 8.000")
    assert x.salientes("whatsapp:1")[-1]["texto"] == "Sí, hacemos ruedos desde $ 8.000"
    assert x.comando("atencion", "dudas", {})[0]["estado"] == "respondida"


def test_reclamo_se_deriva_y_publica():
    x = h()
    out = x.recibir("whatsapp", "1", "Me llegó mal el pedido, quiero hablar con alguien")
    assert "Ana" in out[0]
    assert x.pendientes()[0]["accion"]["tipo"] == "derivar_humano"
    assert ("conversacion.derivada" in [e for e, _ in x.bus.historial])


def test_saludo():
    assert "Taller Ejemplo" in h().recibir("whatsapp", "1", "hola")[0]


def test_lo_que_no_es_pregunta_ni_tema_no_lo_toma():
    x = h()
    assert x.brigadas["atencion"].atender(
        __import__("raphael_harness").Mensaje("whatsapp", "1", "ok perfecto"), x._ctx("atencion")) is None
