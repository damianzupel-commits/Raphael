"""Ruteo de mensajes de clientes con el orquestador real (modo `secretary`) y los cocineros reales.

Portados de `raphael-orquestador/tests/test_orquestador.py` (6). Cambio de semántica: en el v2 Atención es el cocinero
de red (siempre al final), así que "el reclamo va primero a Atención" se prueba por el resultado: aunque haya un
encargo abierto, el reclamo lo atiende Atención (Encargos se lo pasa) y nadie más contesta."""

from kit import System, answers
from raphael_core import Message

E, AT = ("empresas", "encargos"), ("empresas", "atencion")


def route(x, text, sender="549341"):
    return x.rt.run(x.rt._route(Message("whatsapp", sender, text)))


def test_reclamo_con_un_encargo_abierto_lo_atiende_atencion():
    x = System()
    x.receive("quiero un vestido a medida para un casamiento")
    out = x.receive("me llegó roto el pedido anterior, quiero hablar con alguien")
    assert len(out) == 1 and "Ana" in out[0] and "fecha" not in out[0]
    assert [p["action"]["type"] for p in x.pending()] == ["derivar_humano"]
    assert x.ctx("encargos").data.get("chats", "whatsapp:549341") is None       # Encargos soltó el chat


def test_conversacion_abierta_antes_que_interes():
    x = System()
    x.receive("quiero un vestido a medida para un casamiento")
    order = route(x, "el jueves puedo pasar")                 # a Agenda le interesa, pero Encargos tiene el chat abierto
    assert order[:2] == [E, ("empresas", "agenda")]


def test_atencion_siempre_al_final_como_red():
    x = System()
    assert route(x, "me llegó roto, quiero hablar con alguien")[-1] == AT
    assert route(x, "¿qué horario tienen?")[-1] == AT


def test_funciona_sin_atencion():
    x = System()
    x.rt.guard.mark_down("empresas/atencion", "caída para la prueba")
    assert AT not in route(x, "hola")
    x.publish("encargo.presupuesto_enviado", {"number": 1, "contact": "whatsapp:549341", "client": "Lu", "price": 1000,
                                              "deposit": 500})
    assert "confirme la transferencia" in x.receive("ya te transferí la seña")[0]


def test_el_router_con_ia_elige_cuando_las_reglas_no_ven_nada():
    x = System(transport=answers(["empresas/encargos"]), classifier=True)
    assert route(x, "buenas! me haría una campera igual a la de la foto?", "w1")[:2] == [E, AT]


def test_si_la_ia_dice_ninguna_o_inventa_va_a_atencion():
    for r in ("ninguna", "empresas/cocina", "no sé"):
        x = System(transport=answers([r]), classifier=True)
        assert route(x, "buenas! me haría una campera igual a la de la foto?", "w1") == [AT]
