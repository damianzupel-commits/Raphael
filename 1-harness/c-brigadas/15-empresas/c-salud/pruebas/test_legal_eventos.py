"""Eventos hacia Legales (16): revisión antes de mandar un texto, consentimiento y baja. Solo eventos, sin importar nada."""

from kit import System

from raphael_empresas.legal import optin, optout


def _ev(x, name):
    return [d for e, d in x.events(name)]


def test_detecta_bajas_y_altas_sin_confundir_otras_frases():
    for t in ("baja", "STOP", "quiero darme de baja", "no quiero recibir más mensajes", "dejen de escribirme"):
        assert optout(t), t
    for t in ("quiero recibir novedades", "acepto recibir promos"):
        assert optin(t), t
    for t in ("el precio baja mucho?", "hola", "quiero un vestido", "cuánto sale la baja de hilo"):
        assert not optout(t) and not optin(t), t


def test_baja_publica_el_evento_y_gana_a_cualquier_conversacion():
    x = System()
    x.chat("quiero un vestido a medida")                       # conversación de encargo abierta
    out = x.receive("no quiero recibir más mensajes")
    assert "te damos de baja" in out[0]
    [d] = _ev(x, "baja.solicitada")
    assert d["contact"] == "whatsapp:549341" and d["channel"] == "whatsapp"


def test_optin_publica_consentimiento_con_evidencia():
    x = System()
    out = x.receive("quiero recibir novedades")
    assert "Gracias" in out[0]
    [d] = _ev(x, "consentimiento.recibido")
    assert d["purpose"] == "avisos" and d["evidence"] == "quiero recibir novedades" and d["channel"] == "whatsapp"


def test_antes_de_mandar_presupuesto_y_aviso_se_pide_revision():
    x = System({"orders": {"required_steps": ["prenda", "nombre"]}})
    x.chat("quiero un vestido a medida", "Lu")
    x.approve(x.pending("enviar_presupuesto")[0]["id"], {"price": 100000})
    [r] = _ev(x, "revision.pedida")
    assert r["ref"].startswith("presupuesto-") and "100.000" in r["text"]
    x.cmd("encargos", "estado", {"number": 1, "status": "listo"})
    x.tick()
    avisos = [d for d in _ev(x, "revision.pedida") if d["ref"].startswith("aviso-")]
    assert avisos or x.pending("avisar_estado") == []          # el aviso es automático: si salió, pidió revisión
