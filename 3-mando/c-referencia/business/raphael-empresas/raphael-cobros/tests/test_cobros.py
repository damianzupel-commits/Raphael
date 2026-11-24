from raphael_cobros import Cobros
from raphael_harness.testing import armar


def preparado():
    x = armar(Cobros())
    x._ctx("encargos").publicar("encargo.presupuesto_enviado",
                                {"num": 7, "contacto": "whatsapp:1", "cliente": "Lu", "precio": 200000, "sena": 100000})
    return x


def test_aviso_de_transferencia_queda_para_que_la_duena_confirme():
    x = preparado()
    out = x.recibir("whatsapp", "1", "listo, ya te transferí la seña")
    assert "confirme la transferencia" in out[0]
    [p] = x.pendientes()
    assert p["accion"]["tipo"] == "confirmar_pago" and p["nivel"] == "aprobacion"
    assert "$ 100.000" in p["accion"]["resumen"]
    x.aprobar(p["id"])
    assert ("pago.confirmado", {"num": 7, "monto": 100000.0, "contacto": "whatsapp:1", "_de": "cobros"}) in x.bus.historial


def test_comprobante_por_foto_tambien_cuenta_y_no_duplica():
    x = preparado()
    x.recibir("whatsapp", "1", "[foto]", adjunto=True)
    out = x.recibir("whatsapp", "1", "te mandé el comprobante")
    assert "Ya le avisé" in out[0]
    assert len(x.pendientes()) == 1


def test_si_la_duena_rechaza_vuelve_a_esperar():
    x = preparado()
    x.recibir("whatsapp", "1", "ya te pagué")
    x.rechazar(x.pendientes()[0]["id"], "no llegó")
    assert x.comando("cobros", "esperando", {})[0]["num"] == 7


def test_sin_sena_esperando_no_toma_el_mensaje():
    x = armar(Cobros())
    assert x.brigadas["cobros"].interes(__import__("raphael_harness").Mensaje("whatsapp", "1", "ya te transferí"),
                                        x._ctx("cobros")) == 0
