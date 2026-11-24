from datetime import timedelta

from raphael_agenda import Agenda
from raphael_harness.testing import Reloj, armar


def test_pide_dia_y_deja_el_turno_para_confirmar():
    x = armar(Agenda())
    out = x.recibir("whatsapp", "1", "¿Puedo ir a probarme el vestido?", nombre="Cami")
    assert "jueves 16 a 19" in out[0]
    out = x.recibir("whatsapp", "1", "el jueves a las 17")
    assert "te confirmamos" in out[0]
    [p] = x.pendientes()
    assert p["accion"]["datos"]["fecha"] == "2026-11-19" and p["accion"]["datos"]["hora"] == "17:00"
    x.aprobar(p["id"])
    assert "jueves 19 de noviembre a las 17:00" in x.salientes("whatsapp:1")[-1]["texto"]


def test_no_hay_dos_turnos_en_la_misma_franja():
    x = armar(Agenda())
    for q in ("1", "2"):
        x.recibir("whatsapp", q, "quiero un turno para probarme el jueves a las 17")
    a, b = x.pendientes()
    assert x.aprobar(a["id"])["estado"] == "ejecutada"
    assert "ya hay un turno" in x.aprobar(b["id"])["error"]
    assert x.aprobar(b["id"], {"hora": "18:00"})["estado"] == "ejecutada"


def test_sin_hora_la_pone_la_duena():
    x = armar(Agenda())
    x.recibir("whatsapp", "1", "puedo pasar a retirarlo el sábado?")
    pid = x.pendientes()[0]["id"]
    assert x.aprobar(pid)["estado"] == "error"
    assert x.aprobar(pid, {"hora": "11:00"})["estado"] == "ejecutada"


def test_recordatorio_n_dias_antes_una_sola_vez():
    r = Reloj()
    x = armar(Agenda(), reloj=r)
    x.recibir("whatsapp", "1", "turno para probarme el 30/11 a las 10")
    x.aprobar(x.pendientes()[0]["id"])
    x.tick()
    assert "Te recordamos" not in x.salientes("whatsapp:1")[-1]["texto"]
    r.ahora += timedelta(days=9)                  # 27/11: faltan 3 días
    x.tick()
    x.tick()
    textos = [s["texto"] for s in x.salientes("whatsapp:1")]
    assert sum("Te recordamos" in t for t in textos) == 1


def test_turno_pedido_por_encargos():
    x = armar(Agenda())
    x._ctx("encargos").publicar("turno.pedido", {"contacto": "whatsapp:9", "nombre": "Lu", "motivo": "medidas",
                                                 "preferencia": "el jueves a la tarde"})
    [p] = x.pendientes()
    assert p["accion"]["destino"] == "whatsapp:9" and p["accion"]["datos"]["fecha"] == "2026-11-19"
