from raphael_avisos import Avisos
from raphael_harness.testing import armar


def cambio(x, estado, origen="whatsapp", num=3):
    x._ctx("encargos").publicar("encargo.estado_cambiado", {"num": num, "estado": estado, "contacto": "whatsapp:1",
                                                            "cliente": "Camila Pérez", "descripcion": "vestido",
                                                            "origen": origen})


def test_avisa_solo_y_una_vez_por_estado():
    x = armar(Avisos())
    cambio(x, "listo")
    cambio(x, "listo")
    textos = [s["texto"] for s in x.salientes("whatsapp:1")]
    assert textos == ["¡Hola Camila! Tu vestido está listo 🎀 ¿Cuándo lo retirás o coordinamos el envío?"]
    assert x.pendientes() == []                      # automático: no pide aprobación


def test_no_avisa_a_pedidos_cargados_a_mano_ni_estados_sin_texto():
    x = armar(Avisos())
    cambio(x, "listo", origen="manual")
    cambio(x, "presupuesto")
    assert x.salientes() == []
