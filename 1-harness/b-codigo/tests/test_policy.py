from raphael_core import Level, Origin
from raphael_core.installation import installation_from
from raphael_core.manifest import ActionSpec
from raphael_core.policy import PolicyEngine
from raphael_core.store import Store

ACTIONS = {"leer": ActionSpec(level=Level.AUTO), "enviar": ActionSpec(level=Level.APPROVAL),
           "publicar": ActionSpec(level=Level.APPROVAL, tags={"external"}),
           "pagar": ActionSpec(level=Level.APPROVAL, tags={"spend"}),
           "borrar": ActionSpec(level=Level.HUMAN, tags={"irreversible"})}


def motor(**inst):
    p = PolicyEngine(installation_from({"id": "x", "edition": "personal", **inst}), Store().space("_trust"))
    p.register("b", ACTIONS)
    return p


def test_gana_lo_mas_especifico_no_lo_mas_estricto():
    p = motor(autonomy={"enviar": "humano", "b.enviar": "automatico", "leer": "aprobacion"})
    assert p.level("b", "enviar") is Level.AUTO                        # brigada.acción > acción
    assert p.level("b", "leer") is Level.APPROVAL                      # la instalación puede endurecer
    assert p.level("b", "borrar") is Level.HUMAN                       # manifiesto
    d = p.decide("b", "enviar")
    assert d.source == "la instalación (brigada.acción)" and "automatico" in d.explain()
    assert p.level("b", "nada") is Level.APPROVAL and p.decide("b", "nada").source == "acción no declarada"


def test_riesgosas_en_automatico_solo_con_confirmacion():
    p = motor(autonomy={"borrar": "automatico", "pagar": {"level": "automatico", "confirmed_by": "Damián"}})
    assert p.level("b", "borrar") is Level.HUMAN and p.decide("b", "borrar").notes
    assert p.level("b", "pagar") is Level.AUTO


def test_humano_no_baja_solo_salvo_que_se_configure():
    p = motor(trust={"approvals_to_step_down": 1})
    assert p.record_approval("b", "borrar") is None and p.level("b", "borrar") is Level.HUMAN
    p2 = motor(trust={"approvals_to_step_down": 1, "step_down_from_human": True})
    assert p2.record_approval("b", "borrar") == "lowered" and p2.level("b", "borrar") is Level.APPROVAL
    assert p2.record_approval("b", "borrar") == "propose"              # irreversible: a automático solo con OK


def test_subir_tiene_tope_y_bajar_tambien():
    p = motor(trust={"approvals_to_step_down": 1})
    for _ in range(5):
        p.record_correction("b", "enviar")
    assert p.level("b", "enviar") is Level.HUMAN
    p.reset("b", "enviar", who="x")
    assert p.record_approval("b", "enviar") == "lowered" and p.level("b", "enviar") is Level.AUTO
    assert p.record_approval("b", "enviar") is None and p.level("b", "enviar") is Level.AUTO


def test_terceros_y_tabla():
    p = motor(trust={"third_party_step_up": True})
    assert p.level("b", "leer", Origin.THIRD_PARTY) is Level.APPROVAL
    assert p.level("b", "leer", Origin.OWNER) is Level.AUTO
    t = {(r["brigade"], r["action"]): r for r in p.table()}
    assert t[("b", "pagar")]["risky"] and t[("b", "leer")]["level"] == "automatico"
    p.unregister("b")
    assert p.table() == []


def test_lo_que_sale_al_mundo_nunca_baja_solo_a_automatico():
    """Regla general (Damián, 25 nov 2026): lo que sale hacia afuera cuenta como riesgo, igual que gastar o no tener vuelta."""
    p = motor(trust={"approvals_to_step_down": 1})
    assert ACTIONS["publicar"].risky and ACTIONS["pagar"].risky and ACTIONS["borrar"].risky and not ACTIONS["enviar"].risky
    assert p.record_approval("b", "publicar") == "propose"        # propone bajar, pero no baja sola
    assert p.level("b", "publicar") is Level.APPROVAL
    p2 = motor(autonomy={"b.publicar": "automatico"})              # a mano, sin confirmar: se ignora
    assert p2.level("b", "publicar") is not Level.AUTO
