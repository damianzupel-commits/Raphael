import asyncio
from datetime import date, timedelta

from raphael_core import ActionError
from raphael_core.audit import REDACTED, AuditLog, redact
from raphael_core.isolation import Guard
from raphael_core.store import Store
from raphael_core.testing import Clock
from raphael_core.text_es import date_in_words, money, normalize, parse_date, parse_time


# --- auditoría ---------------------------------------------------------------------------------------------------------
def test_auditoria_registra_quien_que_cuando_y_por_que():
    clock = Clock()
    log = AuditLog(Store().space("_audit"), clock)
    log.record("aprobado", who="Ana", why="lo pidió la clienta", id=3)
    clock.advance(minutes=1)
    log.record("accion", who="agenda", tipo="confirmar_turno")
    assert [e["n"] for e in log.entries()] == [1, 2]
    e = log.entries(what="aprobado")[0]
    assert e["who"] == "Ana" and e["why"] == "lo pidió la clienta" and e["when"] == "2026-11-18T10:00:00"
    assert log.entries(last=1)[0]["what"] == "accion"


def test_auditoria_nunca_guarda_secretos():
    datos = {"api_key": "algo", "headers": {"Authorization": "x"}, "nota": "usé sk-abcdefghijklmnop y listo",
             "lista": ["nvapi-1234567890abc"], "ok": 3}
    r = redact(datos)
    assert r["api_key"] == REDACTED and r["headers"]["Authorization"] == REDACTED
    assert "sk-abcdefghijklmnop" not in r["nota"] and r["lista"] == [REDACTED] and r["ok"] == 3
    log = AuditLog(Store().space("_audit"))
    log.record("x", token="abc", detalle="Bearer abcdefghijkl")
    assert "abc" not in str(log.entries()[0]["token"]) and "abcdefghijkl" not in log.entries()[0]["detalle"]


def test_un_dato_no_pisa_los_campos_del_registro():
    log = AuditLog(Store().space("_audit"))
    log.record("a")
    e = log.record("b", n=99, when="ayer")
    assert e["n"] == 2 and e["data_n"] == 99 and e["data_when"] == "ayer" and e["when"] != "ayer"


# --- aislamiento -------------------------------------------------------------------------------------------------------
def test_tres_fallas_seguidas_y_la_pieza_queda_caida():
    caidas = []
    g = Guard(max_failures=3, on_down=lambda p, r: caidas.append(p))

    def roto():
        raise ValueError("x")

    assert not g.call_sync("a", roto).ok
    assert g.call_sync("a", lambda: 1).value == 1          # una buena pone el contador en cero
    for _ in range(3):
        g.call_sync("a", roto)
    assert g.is_down("a") and caidas == ["a"] and "3 fallas" in g.down_reason("a")
    assert g.call_sync("a", lambda: 1).skipped
    g.revive("a")
    assert g.call_sync("a", lambda: 1).ok


def test_errores_del_contrato_no_cuentan_como_falla():
    g = Guard(max_failures=1, passthrough=(ActionError,))

    def no_se():
        raise ActionError("falta un dato")

    out = g.call_sync("a", no_se)
    assert not out.ok and isinstance(out.error, ActionError) and not g.is_down("a")


def test_tope_de_tiempo_para_async_y_para_bloqueantes():
    import time

    async def colgada():
        await asyncio.sleep(5)

    def bloqueante():
        time.sleep(0.5)
        return 1

    async def main():
        g = Guard(max_failures=5)
        a = await g.call("a", colgada, timeout=0.05)
        b = await g.call("b", bloqueante, blocking=True, timeout=0.05)
        c = await g.call("c", bloqueante, blocking=True, timeout=2)
        return a, b, c

    a, b, c = asyncio.run(main())
    assert a.timed_out and b.timed_out and c.ok and c.value == 1


def test_llamada_async_que_falla():
    async def rota():
        raise KeyError("x")

    out = asyncio.run(Guard().call("a", rota))
    assert not out.ok and isinstance(out.error, KeyError)


# --- texto y fechas (portado de test_fechas_y_horas, Empresas) ---------------------------------------------------------
def test_fechas_y_horas():
    hoy = date(2026, 11, 18)                                   # miércoles
    assert parse_date("el 20/12", hoy) == "2026-12-20"
    assert parse_date("para el 5 de enero", hoy) == "2027-01-05"
    assert parse_date("el jueves", hoy) == "2026-11-19"
    assert parse_date("el miercoles", hoy) == "2026-11-25"
    assert parse_date("manana", hoy) == (hoy + timedelta(days=1)).isoformat()
    assert parse_time("el jueves a las 16") == "16:00"
    assert parse_time("tipo 4 de la tarde") == "16:00"
    assert parse_time("el 20/12") is None
    assert date_in_words("2026-11-19", hoy) == "jueves 19 de noviembre"


def test_texto():
    assert normalize("Publicá el BAÑO") == "publica el bano"
    assert money(150000) == "$ 150.000"


def test_fallas_se_cuentan_por_metodo():
    g = Guard(max_failures=2)

    def roto():
        raise ValueError("x")

    for _ in range(2):
        g.call_sync("a", roto, label="handle")
        g.call_sync("a", lambda: 1, label="interest")          # que interest ande no salva a handle
    assert g.is_down("a") and "handle" in g.down_reason("a")
