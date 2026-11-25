"""Agenda. Portados de `raphael-agenda/tests/test_agenda.py` (5)."""

from datetime import timedelta

from kit import System


def test_pide_dia_y_deja_el_turno_para_confirmar():
    x = System()
    out = x.receive("¿Puedo ir a probarme el vestido?", sender="1", name="Cami")
    assert "jueves 16 a 19" in out[0]
    out = x.receive("el jueves a las 17", sender="1")
    assert "te confirmamos" in out[0]
    [p] = x.pending()
    assert p["action"]["data"]["date"] == "2026-11-19" and p["action"]["data"]["time"] == "17:00"
    x.approve(p["id"])
    assert "jueves 19 de noviembre a las 17:00" in x.out("whatsapp:1")[-1]


def test_no_hay_dos_turnos_en_la_misma_franja():
    x = System()
    for q in ("1", "2"):
        x.receive("quiero un turno para probarme el jueves a las 17", sender=q)
    a, b = x.pending()
    assert x.approve(a["id"])["state"] == "executed"
    assert "ya hay un turno" in x.approve(b["id"])["error"]
    assert x.approve(b["id"], {"time": "18:00"})["state"] == "executed"


def test_sin_hora_la_pone_la_duena():
    x = System()
    x.receive("puedo pasar a retirarlo el sábado?", sender="1")
    pid = x.pending()[0]["id"]
    assert x.approve(pid)["state"] == "error"
    assert x.approve(pid, {"time": "11:00"})["state"] == "executed"


def test_recordatorio_n_dias_antes_una_sola_vez():
    x = System()
    x.receive("turno para probarme el 30/11 a las 10", sender="1")
    x.approve(x.pending()[0]["id"])
    x.tick()
    assert "Te recordamos" not in x.out("whatsapp:1")[-1]
    x.clock.now += timedelta(days=9)                  # 27/11: faltan 3 días
    x.tick()
    x.tick()
    assert sum("Te recordamos" in t for t in x.out("whatsapp:1")) == 0   # pide aprobación: todavía no salió
    [p] = x.pending("enviar_recordatorio")                              # una sola vez, aunque corran dos ticks
    x.approve(p["id"])
    x.tick()
    assert sum("Te recordamos" in t for t in x.out("whatsapp:1")) == 1 and x.pending("enviar_recordatorio") == []


def test_turno_pedido_por_encargos():
    x = System()
    x.publish("turno.pedido", {"contact": "whatsapp:9", "name": "Lu", "reason": "medidas",
                               "preference": "el jueves a la tarde"})
    [p] = x.pending()
    assert p["action"]["target"] == "whatsapp:9" and p["action"]["data"]["date"] == "2026-11-19"
