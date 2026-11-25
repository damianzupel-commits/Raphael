"""La brigada montada de verdad: comandos, acciones con su nivel, tools con compuerta, tick, nube, modelos locales y el jefe."""

import json

from kit import BRIGADE_DIR, mounted
from raphael_core import Action


def run(rt, coro):
    return rt.run(coro)


def cmd(rt, cook, name, data=None):
    return rt.run(rt.command("investigacion", cook, name, data or {}, who="persona"))


def test_comandos_forense_de_punta_a_punta(tmp_path):
    rt, _ = mounted()
    c = cmd(rt, "forense", "crear_caso", {"title": "Caso uno"})["id"]
    f = tmp_path / "n.txt"
    f.write_text("mail ana@ejemplo.com")
    r = cmd(rt, "forense", "ingerir", {"case": c, "path": str(f)})
    cmd(rt, "forense", "extraer_entidades", {"case": c, "artefacto": r["sha256"]})
    pend = cmd(rt, "forense", "pendientes", {"case": c})["propuestas"]
    assert pend and cmd(rt, "forense", "caso", {"case": c})["pending_proposals"] == 1
    assert "Pendiente" in cmd(rt, "forense", "informe", {"case": c})["text"]
    assert cmd(rt, "forense", "verificar_log", {"case": c})["ok"]


def test_confirmar_pide_aprobacion_y_al_aprobar_entra_al_caso(tmp_path):
    rt, _ = mounted()
    c = cmd(rt, "forense", "crear_caso", {"title": "C"})["id"]
    f = tmp_path / "n.txt"
    f.write_text("mail ana@ejemplo.com")
    sha = cmd(rt, "forense", "ingerir", {"case": c, "path": str(f)})["sha256"]
    cmd(rt, "forense", "extraer_entidades", {"case": c, "artefacto": sha})
    pid = cmd(rt, "forense", "pendientes", {"case": c})["propuestas"][0]["id"]
    res = rt.run(rt.action("investigacion", "forense", Action("confirmar_propuesta", {"case": c, "id": pid}, summary="confirmar")))
    assert res["state"] == "pending"
    assert cmd(rt, "forense", "caso", {"case": c})["pending_proposals"] == 1       # todavía nada entró
    rt.run(rt.approve(rt.approvals.list(brigade="investigacion")[0]["id"], None, who="persona"))
    assert cmd(rt, "forense", "caso", {"case": c})["pending_proposals"] == 0


def test_acciones_con_nivel():
    rt, _ = mounted()
    c = cmd(rt, "forense", "crear_caso", {"title": "C"})["id"]
    r = rt.run(rt.action("investigacion", "forense", Action("retractar", {"case": c, "kind": "nodo", "id": "x", "reason": "r"})))
    assert r["state"] == "pending"
    r = rt.run(rt.action("investigacion", "ideas", Action("correr_prototipo", {"id": "x"})))
    assert r["state"] == "pending"
    r = rt.run(rt.action("investigacion", "tendencias", Action("borrar_tema", {"tema": "x"})))
    assert r["state"] == "pending"
    r = rt.run(rt.action("investigacion", "scout", Action("buscar_web", {"pregunta": "baterías estado sólido", "verificar": False})))
    assert r["state"] == "executed" and "ejemplo.test" in json.dumps(r, ensure_ascii=False)


def test_aprobar_prototipo_lo_corre():
    rt, _ = mounted()
    i = cmd(rt, "ideas", "nueva", {"title": "p"})["id"]
    p = cmd(rt, "ideas", "guardar_prototipo", {"id": i, "code": "print(21*2)"})["id"]
    res = rt.run(rt.action("investigacion", "ideas", Action("correr_prototipo", {"id": p}, summary="correr")))
    assert res["state"] == "pending"
    pid = rt.approvals.list(brigade="investigacion")[0]["id"]
    done = rt.run(rt.approve(pid, None, who="persona"))
    assert "42" in json.dumps(done, ensure_ascii=False)


def test_tick_revisa_tendencias_solo():
    rt, _ = mounted()
    cmd(rt, "tendencias", "seguir", {"tema": "baterías estado sólido"})
    rt.run(rt.tick())
    assert len(cmd(rt, "tendencias", "avisos")) == 1


def test_tools_registradas_y_prototipo_solo_en_personal():
    rt, _ = mounted()
    assert {"caso_crear", "web_buscar", "prototipo_correr", "tema_seguir"} <= set(rt.tools.names())
    rt2, _ = mounted(edition="cloud")
    assert "prototipo_correr" not in rt2.tools.names() and "prototipo_guardar" in rt2.tools.names()


def test_tool_caso_crear_por_el_gateway():
    rt, _ = mounted()
    tool = rt.tools.get("caso_crear")
    out = rt.run(tool.run({"title": "Desde tool"}))
    assert out == {"id": "desde-tool", "title": "Desde tool"}
    assert rt.run(rt.tools.get("caso_resumen").run({"case": "nope"}))["error"]


def test_config_invalida_no_monta():
    from datetime import datetime

    from raphael_core import Loader, Runtime
    from raphael_core.installation import installation_from
    from raphael_core.testing import Clock
    inst = {"id": "x", "edition": "personal", "brigades": {"investigacion": {"active": True, "config": {"search": {"count": 99}}}}}
    rt = Runtime(installation_from(inst), clock=Clock(datetime(2026, 11, 25)))
    report = rt.run(Loader(rt, [BRIGADE_DIR], installed=False).apply())
    assert report["errors"] and "count" in json.dumps(report["errors"])


def test_la_brigada_es_privada_con_modelos_locales_y_nunca_va_a_la_nube():
    seen = []

    def transport(url, body, headers):
        seen.append(url)
        return {"choices": [{"message": {"content": "- Hay celdas de 400 Wh/kg [1]"}}], "usage": {}}

    rt, _ = mounted(transport=transport)
    r = cmd(rt, "scout", "investigar", {"pregunta": "baterías estado sólido", "verificar": False})
    assert r["modelo"] and seen and all("localhost" in u for u in seen)


def test_sin_modelo_local_avisa_y_no_sale():
    rt, _ = mounted()
    r = cmd(rt, "scout", "investigar", {"pregunta": "baterías", "verificar": False})
    assert not r["modelo"] and any("sin modelo" in a for a in r["avisos"])


def test_el_jefe_degrada_sin_modelo_y_lo_dice():
    rt, _ = mounted()
    rep = rt.run(rt.ask("investigacion", "investigá en la web baterías de estado sólido"))
    assert rep is not None
