"""Avisos. Portados de `raphael-avisos/tests/test_avisos.py` (2)."""

from kit import System


def change(x, status, channel="whatsapp", num=3):
    x.publish("encargo.estado_cambiado", {"number": num, "status": status, "contact": "whatsapp:1",
                                          "client": "Camila Pérez", "description": "vestido", "channel": channel})


def test_avisa_solo_y_una_vez_por_estado():
    x = System()
    change(x, "listo")
    change(x, "listo")
    assert x.out("whatsapp:1") == []                              # sale al mundo: espera la aprobación de la dueña
    [p] = x.pending("avisar_estado")                              # y se pide una sola vez por estado
    assert x.approve(p["id"])["state"] == "executed"
    assert x.out("whatsapp:1") == ["¡Hola Camila! Tu vestido está listo 🎀 ¿Cuándo lo retirás o coordinamos el envío?"]
    assert x.pending() == []


def test_no_avisa_a_pedidos_cargados_a_mano_ni_estados_sin_texto():
    x = System()
    change(x, "listo", channel="manual")
    change(x, "presupuesto")
    assert x.out() == []
