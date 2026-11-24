"""Cobros. Portados de `raphael-cobros/tests/test_cobros.py` (4)."""

from kit import System
from raphael_core import Message


def ready():
    x = System()
    x.publish("encargo.presupuesto_enviado", {"number": 7, "contact": "whatsapp:1", "client": "Lu", "price": 200000,
                                              "deposit": 100000})
    return x


def test_aviso_de_transferencia_queda_para_que_la_duena_confirme():
    x = ready()
    out = x.receive("listo, ya te transferí la seña", sender="1")
    assert "confirme la transferencia" in out[0]
    [p] = x.pending()
    assert p["action"]["type"] == "confirmar_pago" and p["level"] == "aprobacion"
    assert "$ 100.000" in p["summary"]
    x.approve(p["id"])
    [(_, data)] = x.events("pago.confirmado")
    assert {k: data[k] for k in ("number", "amount", "contact")} == {"number": 7, "amount": 100000.0, "contact": "whatsapp:1"}
    assert data["_from"] == "empresas/cobros"


def test_comprobante_por_foto_tambien_cuenta_y_no_duplica():
    x = ready()
    x.receive("[foto]", sender="1", attachment=True)
    out = x.receive("te mandé el comprobante", sender="1")
    assert "Ya le avisé" in out[0]
    assert len(x.pending()) == 1


def test_si_la_duena_rechaza_vuelve_a_esperar():
    x = ready()
    x.receive("ya te pagué", sender="1")
    x.reject(x.pending()[0]["id"], "no llegó")
    assert x.cmd("cobros", "esperando")[0]["number"] == 7


def test_sin_sena_esperando_no_toma_el_mensaje():
    x = System()
    assert x.cook("cobros").interest(Message("whatsapp", "1", "ya te transferí"), x.ctx("cobros")) == 0
