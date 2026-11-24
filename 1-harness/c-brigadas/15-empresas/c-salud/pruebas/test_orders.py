"""Encargos. Portados de `raphael-encargos/tests/test_encargos.py` (9), sobre la instalación de verdad.

Cambio: `test_pregunta_en_el_medio_sin_atencion_retoma_el_paso` se prueba con Atención caída (en el v2 los cocineros
de una brigada se montan juntos; lo que puede pasar es que uno se caiga)."""

from datetime import timedelta

from kit import System

from raphael_empresas.cooks.orders import wants_order

C = "whatsapp:549341"


def test_flujo_completo_deja_presupuesto_pendiente_con_precio_sugerido():
    x = System()
    out = x.receive("Hola! quiero un vestido largo a medida para el casamiento de mi hermana")
    assert "fecha" in out[0]
    out = x.chat("el 20 de marzo", "de gasa, color verde", "no", "busto 90 cintura 70 cadera 98 largo 150", "Camila Pérez")
    assert "Camila" in out[0] and "#1" in out[0]
    [p] = x.pending()
    assert p["action"]["type"] == "enviar_presupuesto" and p["level"] == "aprobacion"
    assert p["action"]["data"]["price"] == 180000                # 150.000 + 20% por largo
    o = x.cmd("encargos", "ver", {"number": 1})
    assert o["status"] == "presupuesto" and o["description"] == "vestido largo para casamiento"


def test_aprobar_manda_presupuesto_con_sena_y_alias():
    x = System()
    x.chat("quiero un vestido a medida para una fiesta", "el 20 de marzo", "rojo", "no", "prefiero que me midan",
           "el jueves a la tarde", "Lu")
    pid = x.pending("enviar_presupuesto")[0]["id"]
    x.approve(pid, {"price": 200000})
    msg = x.out(C)[-1]
    assert "$ 200.000" in msg and "$ 100.000" in msg and "taller.ejemplo" in msg
    assert x.events("encargo.presupuesto_enviado") and x.events("turno.pedido")


def test_sin_precio_en_la_tabla_hay_que_ponerlo_al_aprobar():
    x = System()
    x.chat("quiero un kimono a medida", "para usar en casa", "sin apuro", "de seda", "no", "no las sé", "martes", "Ro")
    pid = x.pending("enviar_presupuesto")[0]["id"]
    assert x.approve(pid)["state"] == "error"
    assert x.approve(pid, {"price": 90000})["state"] == "executed"


def test_fecha_en_numeros_se_confirma_en_palabras():
    x = System()
    out = x.chat("quiero un traje a medida para mi casamiento", "12/12")
    assert "¿lo necesitás para el sábado 12 de diciembre?" in out[0]
    assert "imaginás" in x.chat("sí")[0]


def test_urgente_se_marca_y_no_se_promete():
    x = System()
    out = x.chat("quiero un vestido a medida para una fiesta", "el 25 de noviembre", "negro", "no", "busto 90 cintura 70", "Sol")
    assert "confirmar si se llega" in out[0]
    assert "URGENTE" in x.pending()[0]["summary"]


def test_pregunta_en_el_medio_sin_atencion_retoma_el_paso():
    x = System()
    x.rt.guard.mark_down("empresas/atencion", "caída para la prueba")
    x.chat("quiero un vestido a medida para un casamiento")
    out = x.receive("¿hacen envíos?")
    assert out[-1].endswith("¿Para qué fecha lo necesitás? 📅")


def test_cancelar_y_compra_de_stock():
    x = System()
    x.chat("quiero un vestido a medida")
    assert "sin problema" in x.receive("no, dejalo")[0]
    assert not wants_order("quiero 2 remeras talle M")


def test_estado_publica_evento_y_pago_confirmado_avanza():
    x = System()
    x.chat("quiero un vestido a medida para una fiesta", "el 20 de marzo", "rojo", "no", "busto 90 cintura 70", "Lu")
    x.approve(x.pending()[0]["id"])
    x.publish("pago.confirmado", {"number": 1, "amount": 75000})
    assert x.cmd("encargos", "ver", {"number": 1})["status"] == "confirmado"
    x.cmd("encargos", "estado", {"number": 1, "status": "listo"})
    assert [d["status"] for _, d in x.events("encargo.estado_cambiado")] == ["confirmado", "listo"]


def test_la_conversacion_vence_a_los_3_dias():
    x = System()
    x.receive("quiero un vestido a medida")
    x.clock.now += timedelta(days=4)
    assert x.receive("rojo")[0].startswith("¡Gracias por escribir")   # ya no hay chat abierto: pasa a una persona
