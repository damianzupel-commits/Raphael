"""El harness solo, con brigadas de juguete: contrato, políticas, pendientes, eventos, uso, modelos."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from raphael_harness import Accion, Brigada, ErrorDeAccion, Nivel, Respuesta, perfil_de
from raphael_harness.almacen import Almacen
from raphael_harness.cargador import descubrir
from raphael_harness.politicas import Politicas
from raphael_harness.testing import PERFIL_MINIMO, Reloj, armar
from raphael_harness.texto import fecha_en_palabras, parse_fecha, parse_hora
from datetime import date, timedelta


class Eco(Brigada):
    nombre = "eco"
    version = "9.9.9"
    acciones = {"saludar": Nivel.AUTO, "regalar": Nivel.APROBACION}
    eventos = ("ping",)

    def __init__(self):
        self.eventos_vistos = []

    def interes(self, msg, ctx):
        return 0.5 if "eco" in msg.texto else 0.0

    def atender(self, msg, ctx):
        if "eco" not in msg.texto:
            return None
        acciones = [Accion("saludar", {"a": msg.nombre})]
        if "regalo" in msg.texto:
            acciones.append(Accion("regalar", {"cosa": "flor"}, "Regalar una flor"))
        return Respuesta("eco: " + msg.texto, acciones)

    def ejecutar(self, accion, ctx):
        if accion.tipo == "saludar":
            return "¡saludos!"
        if accion.tipo == "regalar":
            if not accion.datos.get("cosa"):
                raise ErrorDeAccion("falta la cosa")
            return f"te regalo una {accion.datos['cosa']}"
        raise ErrorDeAccion("no")

    def al_evento(self, evento, datos, ctx):
        self.eventos_vistos.append((evento, datos))


def test_responde_y_ejecuta_lo_automatico():
    h = armar(Eco())
    assert h.recibir("prueba", "1", "eco hola") == ["eco: eco hola", "¡saludos!"]


def test_lo_que_requiere_aprobacion_queda_pendiente_y_se_aprueba_con_cambios():
    h = armar(Eco())
    out = h.recibir("prueba", "1", "eco regalo")
    assert "te regalo" not in " ".join(out)
    [p] = h.pendientes()
    assert p["nivel"] == "aprobacion" and p["accion"]["resumen"] == "Regalar una flor"
    res = h.aprobar(p["id"], {"cosa": "rosa"})
    assert res["estado"] == "ejecutada"
    assert h.salientes("prueba:1")[-1]["texto"] == "te regalo una rosa"
    assert h.pendientes() == []


def test_un_error_al_aprobar_deja_el_pendiente_abierto():
    h = armar(Eco())
    h.recibir("prueba", "1", "eco regalo")
    pid = h.pendientes()[0]["id"]
    assert h.aprobar(pid, {"cosa": ""})["estado"] == "error"
    assert h.pendientes()[0]["id"] == pid


def test_el_perfil_endurece_pero_no_relaja():
    h = armar(Eco(), perfil={"politicas": {"saludar": "aprobacion", "confirmar_pago": "automatico"}})
    assert h.politicas.nivel("eco", "saludar") is Nivel.APROBACION
    assert h.politicas.nivel("x", "confirmar_pago") is Nivel.APROBACION
    assert any("confirmar_pago" in a for a in h.avisos)


def test_accion_desconocida_pide_aprobacion():
    assert Politicas({}, []).nivel("x", "borrar_todo") is Nivel.APROBACION


def test_nadie_entiende_queda_para_una_persona():
    h = armar(Eco())
    out = h.recibir("prueba", "1", "algo raro")
    assert "te responde Ana" in out[0]
    assert h.pendientes()[0]["nivel"] == "humano"
    h.resolver(h.pendientes()[0]["id"], "Te respondo yo")
    assert h.salientes("prueba:1")[-1]["texto"] == "Te respondo yo"


def test_eventos_llegan_a_quien_los_escucha():
    e = Eco()
    h = armar(e)
    h._ctx("otra").publicar("ping", {"x": 1})
    assert e.eventos_vistos == [("ping", {"x": 1, "_de": "otra"})]


def test_registro_y_estado_sin_datos_de_clientes():
    h = armar(Eco())
    h.recibir("prueba", "1", "eco hola")
    est = h.estado()
    assert est["brigadas"] == {"eco": "9.9.9"} and est["uso"]["mensajes"] == 1
    assert "eco hola" not in str(est)
    assert any(r["que"] == "accion_ejecutada" for r in h.registro())


def test_tope_de_mensajes_apaga_la_ia_y_avisa_una_vez():
    h = armar(Eco(), perfil={"limites": {"mensajes_mes": 2}})
    for _ in range(4):
        h.recibir("prueba", "1", "eco hola")
    assert h.uso.excedido()
    assert sum(1 for p in h.pendientes() if p["accion"]["tipo"] == "aviso_tope") == 1


def test_modelos_por_rol_y_plan_registran_uso_y_caen_a_none():
    llamadas = []

    def transporte(url, cuerpo, headers):
        llamadas.append((url, cuerpo["model"], headers.get("Authorization")))
        return {"choices": [{"message": {"content": "hola"}}], "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}

    config = {"planes": {"basico": {"redaccion": "barato"}},
              "proveedores": {"barato": {"base_url": "http://x/v1", "model": "m1", "api_key_env": "K",
                                         "usd_por_millon_in": 1.0, "usd_por_millon_out": 2.0}}}
    h = armar(Eco(), config_modelos=config, env={"K": "secreto"}, transporte_ia=transporte)
    ctx = h._ctx("eco")
    assert ctx.ia("redaccion", [{"role": "user", "content": "x"}]) == "hola"
    assert llamadas == [("http://x/v1/chat/completions", "m1", "Bearer secreto")]
    assert ctx.ia("resumen", []) is None                       # rol sin modelo en el plan
    u = h.uso.resumen()
    assert u["tokens_in"] == 1000 and u["costo_usd"] == pytest.approx(0.002)

    h2 = armar(Eco(), config_modelos=config, env={}, transporte_ia=transporte)
    assert h2._ctx("eco").ia("redaccion", []) is None           # sin clave: reglas


def test_falla_de_la_ia_no_rompe():
    def roto(*a):
        raise RuntimeError("caído")

    config = {"planes": {"basico": {"redaccion": "p"}}, "proveedores": {"p": {"base_url": "http://x", "model": "m"}}}
    h = armar(Eco(), config_modelos=config, transporte_ia=roto)
    assert h._ctx("eco").ia("redaccion", []) is None
    assert h.uso.resumen()["fallas_ia"] == 1


def test_perfil_valida_y_rechaza_lo_desconocido():
    p = perfil_de(PERFIL_MINIMO)
    assert p.negocio == "Taller Ejemplo" and p.quien_decide == "Ana"
    with pytest.raises(ValidationError):
        perfil_de({**PERFIL_MINIMO, "campo_raro": 1})
    with pytest.raises(ValidationError):
        perfil_de({**PERFIL_MINIMO, "cobros": {"sena_pct": 150}})
    p2 = perfil_de({**PERFIL_MINIMO, "encargos": {"datos_obligatorios": ["prenda"]}})
    assert "nombre" in p2.encargos.datos_obligatorios


def test_contrato_incompatible_no_se_carga():
    class Vieja(Eco):
        nombre = "vieja"
        contrato = 99

    with pytest.raises(ValueError):
        armar(Vieja())


def test_almacen_por_espacios_y_contadores(tmp_path):
    a = Almacen(str(tmp_path / "x.sqlite"))
    uno, dos = a.espacio("uno"), a.espacio("dos")
    uno.guardar("c", 1, {"v": 1})
    assert dos.obtener("c", 1) is None
    assert [uno.siguiente("n"), uno.siguiente("n"), dos.siguiente("n")] == [1, 2, 1]
    assert uno.listar("c", v=1) == [{"v": 1}]


def test_descubre_repos_vecinos(tmp_path):
    repo = tmp_path / "raphael-saludo" / "src" / "raphael_saludo"
    repo.mkdir(parents=True)
    (repo / "__init__.py").write_text(
        "from raphael_harness import Brigada\nclass S(Brigada):\n    nombre='saludo'\n    version='1.0.0'\nBRIGADA = S\n")
    orq, brig, avisos = descubrir(tmp_path)
    assert "saludo" in brig and orq is None


def test_fechas_y_horas():
    hoy = date(2026, 11, 18)                                   # miércoles
    assert parse_fecha("el 20/12", hoy) == "2026-12-20"
    assert parse_fecha("para el 5 de enero", hoy) == "2027-01-05"
    assert parse_fecha("el jueves", hoy) == "2026-11-19"
    assert parse_fecha("el miercoles", hoy) == "2026-11-25"
    assert parse_fecha("manana", hoy) == (hoy + timedelta(days=1)).isoformat()
    assert parse_hora("el jueves a las 16") == "16:00"
    assert parse_hora("tipo 4 de la tarde") == "16:00"
    assert parse_hora("el 20/12") is None
    assert fecha_en_palabras("2026-11-19", hoy) == "jueves 19 de noviembre"


def test_reloj_controlable():
    r = Reloj()
    h = armar(Eco(), reloj=r)
    assert h._ctx("eco").hoy() == r.ahora.date()


def test_conversacion_y_contactos():
    h = armar(Eco())
    h.recibir("whatsapp", "1", "eco hola", nombre="Cami")
    conv = h.conversacion("whatsapp:1")
    assert [m["de"] for m in conv] == ["cliente", "raphael", "raphael"]
    h.recibir("whatsapp", "1", "eco chau")
    assert [m["texto"][:7] for m in h.conversacion("whatsapp:1")][3:] == ["eco cha", "eco: ec", "¡saludo"]
    assert h.contactos()[0]["nombre"] == "Cami"
