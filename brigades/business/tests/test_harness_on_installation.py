"""Lo que probaba el harness de Empresas 0.4, ahora sobre la instalación real (harness v2 + orquestador + brigada).

Portados de `raphael-harness/tests/test_harness.py` (18). Ahí se probaba el harness con una brigada de juguete; acá
el mismo comportamiento con la brigada de verdad. Cambio de semántica (decisión del 21 nov 2026): "el perfil endurece
pero no relaja" pasa a "sin pisos, pero bajar a automático algo con gasto o irreversible exige confirmed_by"."""

from datetime import date, timedelta

import pytest
import yaml
from kit import BRIGADE_DIR, System, answers
from pydantic import ValidationError
from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.loader import discover
from raphael_core.text_es import date_in_words, parse_date, parse_time

from raphael_empresas.config import business_config
from raphael_empresas.sample import MINIMAL

SHORT = {"orders": {"required_steps": ["prenda", "nombre"]}}
C = "whatsapp:549341"


def with_quote(**kw):
    x = System(SHORT, **kw)
    x.chat("quiero un vestido a medida", "Lu")
    return x


def test_responde_y_ejecuta_lo_automatico():
    x = with_quote()
    x.approve(x.pending()[0]["id"])
    x.cmd("encargos", "estado", {"number": 1, "status": "en_confeccion"})       # -> avisar_estado (automático)
    assert "Ya estamos trabajando" in x.out(C)[-1] and x.pending() == []


def test_lo_que_requiere_aprobacion_queda_pendiente_y_se_aprueba_con_cambios():
    x = with_quote()
    assert not any("$ " in t for t in x.out(C))                       # todavía no salió ningún precio
    [p] = x.pending()
    assert p["level"] == "aprobacion" and p["summary"].startswith("Encargo #1 de Lu")
    assert x.approve(p["id"], {"price": 210000})["state"] == "executed"
    assert "$ 210.000" in x.out(C)[-1] and x.pending() == []


def test_un_error_al_aprobar_deja_el_pendiente_abierto():
    x = with_quote()
    pid = x.pending()[0]["id"]
    assert x.approve(pid, {"price": 0})["state"] == "error"
    assert x.pending()[0]["id"] == pid


def test_la_instalacion_endurece_y_lo_irreversible_no_se_relaja_sin_confirmar():
    x = System(autonomy={"empresas.avisar_estado": "aprobacion", "empresas.confirmar_pago": "automatico"})
    assert x.rt.policy.decide("empresas", "avisar_estado").level.value == "aprobacion"
    assert x.rt.policy.decide("empresas", "confirmar_pago").level.value == "aprobacion"
    assert any("confirmar_pago" in w and "se ignora" in w for w in x.rt.warnings)


def test_accion_desconocida_pide_aprobacion():
    assert System().rt.policy.decide("empresas", "borrar_todo").level.value == "aprobacion"


def test_nadie_entiende_queda_para_una_persona():
    x = System()
    out = x.receive("algo raro", sender="1")
    assert "te responde Ana" in out[0]
    [p] = x.pending()
    assert p["level"] == "humano"
    x.resolve(p["id"], "Te respondo yo")
    assert x.out("whatsapp:1")[-1] == "Te respondo yo"


def test_eventos_llegan_a_quien_los_escucha():
    x = System()
    x.publish("turno.pedido", {"contact": "whatsapp:9", "name": "Lu", "preference": "el jueves a las 10"})
    assert [p["action"]["type"] for p in x.pending()] == ["confirmar_turno"]
    x.publish("encargo.creado", {"number": 1})                       # nadie lo escucha: no pasa nada
    assert len(x.pending()) == 1


def test_registro_y_estado_sin_datos_de_clientes():
    x = with_quote()
    x.approve(x.pending()[0]["id"])
    st = x.rt.status()
    assert st["brigades"]["empresas"]["version"] == "2.0.0" and st["usage"]["messages"] == 2
    assert "vestido" not in str(st) and "Lu" not in str(st["brigades"])
    assert any(e["what"] == "accion_ejecutada" for e in x.rt.audit.entries())


def test_tope_de_mensajes_avisa_una_vez():
    x = System(limits={"messages_month": 2})
    for _ in range(4):
        x.receive("hola")
    assert x.rt.usage.exceeded()
    assert sum(1 for p in x.pending() if p["action"]["type"] == "aviso_tope") == 1


def test_modelos_por_rol_registran_uso_y_sin_modelo_caen_a_reglas():
    x = System(transport=answers(["Marta recibió algo roto."]))
    x.receive("me llegó roto, quiero hablar con alguien", sender="9", name="Marta")
    x.say("hola")
    assert "Marta recibió algo roto" in x.say("contame la 1").text
    assert x.rt.usage.summary()["tokens_in"] > 0
    y = System()
    y.receive("me llegó roto, quiero hablar con alguien", sender="9", name="Marta")
    y.say("hola")
    assert "lo último que dijo" in y.say("contame la 1").text


def test_falla_de_la_ia_no_rompe():
    x = System(transport=answers([RuntimeError("caído")] * 3))
    x.receive("me llegó roto, quiero hablar con alguien", sender="9", name="Marta")
    x.say("hola")
    assert "lo último que dijo" in x.say("contame la 1").text


def test_la_config_valida_y_rechaza_lo_desconocido():
    cfg = business_config(MINIMAL)
    assert cfg.business.name == "Taller Ejemplo" and cfg.business.owner == "Ana"
    with pytest.raises(ValidationError):
        business_config({**MINIMAL, "campo_raro": 1})
    with pytest.raises(ValidationError):
        business_config({**MINIMAL, "payments": {"deposit_pct": 150}})
    assert "nombre" in business_config({"orders": {"required_steps": ["prenda"]}}).orders.required_steps
    rt = Runtime(installation_from({"id": "t", "edition": "cloud", "brigades": {"empresas": {
        "active": True, "config": {**MINIMAL, "payments": {"deposit_pct": 150}}}}}))
    report = rt.run(Loader(rt, [BRIGADE_DIR], installed=False).apply())
    assert "deposit_pct" in report["errors"]["empresas"] and "empresas" not in rt.brigades


def test_contrato_incompatible_no_se_carga(tmp_path):
    m = yaml.safe_load((BRIGADE_DIR / "manifest.yaml").read_text(encoding="utf-8"))
    m["contract"] = ">=3.0,<4"
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "manifest.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    rt = Runtime(installation_from({"id": "t", "edition": "cloud", "brigades": {"empresas": {"config": MINIMAL}}}))
    report = rt.run(Loader(rt, [tmp_path], installed=False).apply())
    assert "contrato" in report["errors"]["empresas"] and not rt.brigades


def test_almacen_por_espacios_y_contadores():
    x = System()
    enc, ag = x.ctx("encargos"), x.ctx("agenda")
    enc.data.put("chats", "c", {"v": 1})
    assert ag.data.get("chats", "c") is None                       # cada cocinero ve su conversación
    enc.shared.put("orders", 1, {"v": 1})
    assert ag.shared.get("orders", 1) == {"v": 1}                  # lo común de la brigada lo ven todos
    assert [enc.shared.next("n"), enc.shared.next("n"), enc.data.next("n")] == [1, 2, 1]
    assert enc.shared.list("orders", v=1) == [{"v": 1}]


def test_el_cargador_la_encuentra_en_la_carpeta_de_brigadas():
    found, warnings = discover([BRIGADE_DIR.parent], installed=False)        # raphael/brigades
    assert "empresas" in found and found["empresas"].path.parent == BRIGADE_DIR


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


def test_reloj_controlable():
    x = System()
    assert x.ctx("encargos").today() == x.clock.now.date()
    x.clock.advance(days=2)
    assert x.ctx("agenda").today() == date(2026, 11, 20)


def test_conversacion_y_contactos():
    x = System()
    x.receive("hola", sender="1", name="Cami")
    conv = x.rt.conversation("whatsapp:1")
    assert [m["from"] for m in conv] == ["contact", "raphael"] and "Taller Ejemplo" in conv[1]["text"]
    x.receive("¿qué horario tienen?", sender="1")
    assert len(x.rt.conversation("whatsapp:1")) == 4
    assert x.rt.contacts()[0]["name"] == "Cami"
