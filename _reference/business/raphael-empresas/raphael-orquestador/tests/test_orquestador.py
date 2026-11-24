from raphael_harness import Brigada, Mensaje, Respuesta
from raphael_harness.testing import armar
from raphael_orquestador import OrquestadorRaphael


class B(Brigada):
    def __init__(self, nombre, interes=0.0, abierta=False):
        self.nombre, self._i, self._a = nombre, interes, abierta
        self.version = "1"

    def interes(self, msg, ctx):
        return self._i

    def en_curso(self, msg, ctx):
        return self._a

    def atender(self, msg, ctx):
        return Respuesta(self.nombre)


def orden(*brigadas, texto="hola"):
    h = armar(*brigadas, orquestador=OrquestadorRaphael())
    return [b.nombre for b in h.orquestador.elegir(Mensaje("whatsapp", "1", texto), h._ctx("orquestador"),
                                                   list(h.brigadas.values()))]


def test_reclamo_va_primero_a_atencion():
    assert orden(B("encargos", 0.9, abierta=True), B("atencion"), texto="me llegó roto el pedido")[0] == "atencion"


def test_conversacion_abierta_antes_que_interes():
    assert orden(B("agenda", 0.9), B("encargos", 0.1, abierta=True), B("atencion"))[:2] == ["encargos", "agenda"]


def test_atencion_siempre_al_final_como_red():
    assert orden(B("atencion", 0.99), B("cobros", 0.2), B("agenda", 0.0)) == ["cobros", "atencion"]


def test_funciona_sin_atencion_instalada():
    assert orden(B("cobros", 0.5)) == ["cobros"]


# ---------------------------------------------------------------- router con IA
def _con_ia(respuesta):
    from raphael_harness import Brigada, Mensaje, Respuesta
    from raphael_harness.testing import armar

    class Lisa(Brigada):
        def __init__(self, nombre, desc):
            self.nombre, self.descripcion, self.version = nombre, desc, "1"
            self.vio = []

        def interes(self, msg, ctx):
            return 0.0

        def atender(self, msg, ctx):
            self.vio.append(msg.texto)
            return Respuesta(f"{self.nombre} acá")

    enc, atn = Lisa("encargos", "pedidos a medida"), Lisa("atencion", "dudas y reclamos")
    cfg = {"planes": {"basico": {"intencion": "x"}}, "proveedores": {"x": {"base_url": "http://ia", "model": "m"}}}
    h = armar(enc, atn, orquestador=OrquestadorRaphael(), config_modelos=cfg,
              transporte_ia=lambda u, c, hd: {"choices": [{"message": {"content": respuesta}}]})
    return h, enc, atn


def test_el_router_con_ia_elige_la_brigada_cuando_las_reglas_no_ven_nada():
    h, enc, atn = _con_ia('{"brigada": "encargos"}')
    h.recibir("whatsapp", "w:1", "buenas! me haría una campera igual a la de la foto?", "Eva")
    assert enc.vio and not atn.vio


def test_si_la_ia_dice_ninguna_o_inventa_va_a_atencion():
    for r in ('{"brigada": "ninguna"}', '{"brigada": "cocina"}', "no sé"):
        h, enc, atn = _con_ia(r)
        h.recibir("whatsapp", "w:1", "buenas! me haría una campera igual a la de la foto?", "Eva")
        assert atn.vio and not enc.vio
