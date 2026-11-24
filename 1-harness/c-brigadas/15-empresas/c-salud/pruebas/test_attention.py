"""Atención. Portados de `raphael-atencion/tests/test_atencion.py` (5), sobre la instalación de verdad."""

from kit import System
from raphael_core import Message

INFO = {"info": {"hours": "Lunes a sábado de 10 a 19", "shipping": "Enviamos a todo el país por correo",
                 "payment_methods": ["transferencia"],
                 "faq": [{"question": "¿Trabajan con tela de la clienta?", "answer": "Sí, podés traer tu tela.",
                          "keywords": ["mi tela"]}]}}


def h():
    return System(INFO)


def test_responde_con_lo_cargado():
    assert h().receive("¿Qué horario tienen?", sender="1") == ["Lunes a sábado de 10 a 19."]
    assert "todo el país" in h().receive("hacen envíos a Córdoba?", sender="1")[0]
    assert h().receive("puedo llevar mi tela?", sender="1") == ["Sí, podés traer tu tela."]


def test_no_inventa_anota_la_duda_para_la_duena():
    x = h()
    out = x.receive("¿Hacen arreglos de ruedos?", sender="1")
    assert out == ["Eso te lo confirma Ana personalmente, ya se lo anoto 😊"]
    [p] = x.pending()
    assert p["level"] == "humano" and p["action"]["type"] == "responder_duda" and p["brigade"] == "empresas"
    x.resolve(p["id"], "Sí, hacemos ruedos desde $ 8.000")
    assert x.out("whatsapp:1")[-1] == "Sí, hacemos ruedos desde $ 8.000"
    assert x.cmd("atencion", "dudas")[0]["status"] == "respondida"


def test_reclamo_se_deriva_y_publica():
    x = h()
    out = x.receive("Me llegó mal el pedido, quiero hablar con alguien", sender="1")
    assert "Ana" in out[0] and len(out) == 1
    assert x.pending()[0]["action"]["type"] == "derivar_humano"
    assert x.events("conversacion.derivada")


def test_saludo():
    assert "Taller Ejemplo" in h().receive("hola", sender="1")[0]


def test_lo_que_no_es_pregunta_ni_tema_no_lo_toma():
    x = h()
    assert x.cook("atencion").handle(Message("whatsapp", "1", "ok perfecto"), x.ctx("atencion")) is None
