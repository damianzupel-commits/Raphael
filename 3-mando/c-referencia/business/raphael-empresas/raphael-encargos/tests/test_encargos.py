from raphael_encargos import Encargos
from raphael_encargos.brigada import quiere_encargo
from raphael_harness.testing import Reloj, armar

C = ("whatsapp", "549341")


def h(**perfil):
    return armar(Encargos(), perfil=perfil or None, reloj=Reloj())


def charla(x, *mensajes):
    out = []
    for m in mensajes:
        out = x.recibir(*C, m)
    return out


def test_flujo_completo_deja_presupuesto_pendiente_con_precio_sugerido():
    x = h()
    out = x.recibir(*C, "Hola! quiero un vestido largo a medida para el casamiento de mi hermana")
    assert "fecha" in out[0]
    out = charla(x, "el 20 de marzo", "de gasa, color verde", "no", "busto 90 cintura 70 cadera 98 largo 150", "Camila Pérez")
    assert "Camila" in out[0] and "#1" in out[0]
    [p] = x.pendientes()
    assert p["accion"]["tipo"] == "enviar_presupuesto" and p["nivel"] == "aprobacion"
    assert p["accion"]["datos"]["precio"] == 180000                # 150.000 + 20% por largo
    e = x.comando("encargos", "ver", {"num": 1})
    assert e["estado"] == "presupuesto" and e["descripcion"] == "vestido largo para casamiento"


def test_aprobar_manda_presupuesto_con_sena_y_alias():
    x = h()
    charla(x, "quiero un vestido a medida para una fiesta", "el 20 de marzo", "rojo", "no", "prefiero que me midan",
           "el jueves a la tarde", "Lu")
    pid = x.pendientes()[0]["id"]
    x.aprobar(pid, {"precio": 200000})
    msg = x.salientes("whatsapp:549341")[-1]["texto"]
    assert "$ 200.000" in msg and "$ 100.000" in msg and "taller.ejemplo" in msg
    assert ("encargo.presupuesto_enviado" in [e for e, _ in x.bus.historial])
    assert ("turno.pedido" in [e for e, _ in x.bus.historial])


def test_sin_precio_en_la_tabla_hay_que_ponerlo_al_aprobar():
    x = h()
    charla(x, "quiero un kimono a medida", "para usar en casa", "sin apuro", "de seda", "no", "no las sé", "martes", "Ro")
    pid = x.pendientes()[0]["id"]
    assert x.aprobar(pid)["estado"] == "error"
    assert x.aprobar(pid, {"precio": 90000})["estado"] == "ejecutada"


def test_fecha_en_numeros_se_confirma_en_palabras():
    x = h()
    out = charla(x, "quiero un traje a medida para mi casamiento", "12/12")
    assert "¿lo necesitás para el sábado 12 de diciembre?" in out[0]
    assert "imaginás" in charla(x, "sí")[0]


def test_urgente_se_marca_y_no_se_promete():
    x = h()
    out = charla(x, "quiero un vestido a medida para una fiesta", "el 25 de noviembre", "negro", "no",
                 "busto 90 cintura 70", "Sol")
    assert "confirmar si se llega" in out[0]
    assert "URGENTE" in x.pendientes()[0]["accion"]["resumen"]


def test_pregunta_en_el_medio_sin_atencion_retoma_el_paso():
    x = h()
    charla(x, "quiero un vestido a medida para un casamiento")
    out = x.recibir(*C, "¿hacen envíos?")
    assert out[-1].endswith("¿Para qué fecha lo necesitás? 📅")


def test_cancelar_y_compra_de_stock():
    x = h()
    charla(x, "quiero un vestido a medida")
    assert "sin problema" in x.recibir(*C, "no, dejalo")[0]
    assert not quiere_encargo("quiero 2 remeras talle M")


def test_estado_publica_evento_y_pago_confirmado_avanza():
    x = h()
    charla(x, "quiero un vestido a medida para una fiesta", "el 20 de marzo", "rojo", "no", "busto 90 cintura 70", "Lu")
    x.aprobar(x.pendientes()[0]["id"])
    x._ctx("cobros").publicar("pago.confirmado", {"num": 1, "monto": 75000})
    assert x.comando("encargos", "ver", {"num": 1})["estado"] == "confirmado"
    x.comando("encargos", "estado", {"num": 1, "estado": "listo"})
    eventos = [d for e, d in x.bus.historial if e == "encargo.estado_cambiado"]
    assert [d["estado"] for d in eventos] == ["confirmado", "listo"]


def test_la_conversacion_vence_a_los_3_dias():
    r = Reloj()
    x = armar(Encargos(), reloj=r)
    x.recibir(*C, "quiero un vestido a medida")
    from datetime import timedelta
    r.ahora += timedelta(days=4)
    assert x.recibir(*C, "rojo")[0].startswith("¡Gracias por escribir")   # ya no hay chat abierto
