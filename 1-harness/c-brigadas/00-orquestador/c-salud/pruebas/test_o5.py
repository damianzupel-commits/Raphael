"""O5: modo master completo, avisos proactivos, comandos de borradores y la matriz de los dos modos. Puerta de O5.

Portados de JarvisRemote `tests/test_orquestador_brigadas.py` (comandos de borradores: el gate por hash, que un texto
que no empieza con el comando no active nada) sin la parte HTTP, que es de la pieza 03. Lo demás es nuevo.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from kit import Script, call, msg, runtime
from raphael_core import Loader, Runtime
from raphael_core.context import OrchestratorContext
from raphael_core.drafts import DraftStore
from raphael_core.drafts.signing import Signer
from raphael_core.engine.reports import REPORT_VERSION, InternalReport
from raphael_core.installation import installation_from
from raphael_core.manifest import ActionSpec
from raphael_core.testing import Clock
from raphael_core.tools import Tool

from raphael_orchestrator import config_from, voice
from raphael_orchestrator.orchestrator import RaphaelOrchestrator
from raphael_orchestrator.turn import run_self

SRC = Path(__file__).resolve().parents[2] / "b-codigo" / "src"
FAITHFUL = "Rust 2.0 salió el 3 de marzo, según Página A."
ROUTING = {"osint": {"safe_default": True, "signals": [{"pattern": "en la web", "weight": 2}]}}


def run(coro):
    return asyncio.run(coro)


def good_script(voice_answers=(FAITHFUL,)):
    return Script(helper=[msg(calls=[call("search_osint", {"query": "rust"})]), msg("Rust 2.0 salió el 3 de marzo (Página A).")],
                  chief=[{"summary": "Rust 2.0 salió el 3 de marzo.", "confidence": "high",
                          "findings": [{"text": "Salió el 3 de marzo.", "helper": "osint-web", "sources": ["Página A"]}]}],
                  voice=list(voice_answers))


def master(script=None, *, models=True, cfg=None, **kw):
    rt = runtime(script or good_script(), routing=ROUTING, models=models, **kw)
    rt.set_orchestrator(RaphaelOrchestrator(), cfg or {"watchdog": {"poll_seconds": 0.01}, "routing": {"classifier": False}})
    return rt


def say(rt, text, session="app", feed=None):
    return rt.run(rt.talk_to_owner(text, session=session, on_event=(feed.append if feed is not None else None)))


# --- el verificador ya no deja pasar un mensaje que no dice nada del reporte (límite anotado en O2) --------------------
def test_un_mensaje_que_no_dice_nada_del_reporte_no_pasa():
    rep = InternalReport.validate({"version": REPORT_VERSION, "brigade": "orquestador", "confidence": "high",
                                   "summary": "Las brigadas que están trabajando son: Osint y Tienda."})
    v = voice.verify("¡Hola, Damián! ¿Qué necesitás?", rep)
    assert not v.ok and v.off_topic and "no dice nada" in v.problems()[0]
    assert voice.verify("Trabajan Osint y Tienda.", rep).ok
    assert voice.verify(voice.template_message(rep), rep).ok
    empty = InternalReport.validate({"version": REPORT_VERSION, "brigade": "x", "confidence": "low", "summary": "Ok."})
    assert voice.verify("Listo.", empty).ok                                  # sin palabras con contenido no exige nada


def test_el_autoconocimiento_con_una_voz_que_se_va_por_las_ramas_sale_por_plantilla():
    rt = runtime(Script(voice=["¡Hola! ¿Qué necesitás?"]))
    t = run(run_self(OrchestratorContext(rt), "¿qué brigadas tenés?", lambda ev: asyncio.sleep(0),
                     config_from({"voice": {"retries": 1}})))
    assert t.via == "template" and "Osint" in t.text


# --- modo master de punta a punta -------------------------------------------------------------------------------------------
def test_master_rutea_corre_la_brigada_y_contesta_con_feed_y_meta():
    rt = master()
    feed = []
    r = say(rt, "buscá en la web cuándo salió Rust 2.0", feed=feed)
    assert r.text == FAITHFUL and r.meta["via"] == "llm" and r.meta["route"]["brigade"] == "osint"
    assert r.meta["fidelity"]["ok"] and "voice" in r.meta["timings"]
    assert feed[0]["type"] == "route" and feed[-1]["type"] == "final" and feed[-1]["origin"] == "orchestrator"


def test_master_charla_y_autoconocimiento_sin_despertar_brigadas():
    script = Script(voice=["¡Hola, Damián! ¿En qué te ayudo?", None])
    rt = master(script)
    assert say(rt, "hola").text.startswith("¡Hola")
    assert "Osint" in say(rt, "¿qué brigadas tenés?").text
    assert script.of("chief") == [] and script.of("helper") == []


def test_master_un_pendiente_real_se_aprueba_por_su_numero_con_confirmacion():
    script = Script(helper=[msg(calls=[call("search_osint", {"query": "x"})]), msg("listo")],
                    chief=[{"summary": "Busqué y quedó una propuesta.", "confidence": "medium"}], voice=[None])
    rt = master(script)
    rt.policy.declare("osint", "tool_search_osint", ActionSpec(level="aprobacion"))
    r = say(rt, "buscá en la web x")
    [p] = rt.approvals.list()
    assert f"#{p['id']}" in r.text
    r = say(rt, f"aprobá el #{p['id']}")
    assert "¿Confirmo?" in r.text and r.meta["via"] == "secretary" and rt.approvals.list()
    r = say(rt, "sí")
    assert "Aprobada" in r.text and rt.approvals.list() == []
    assert any(e["what"] == "aprobado" for e in rt.audit.entries())


def test_master_una_propuesta_se_descarta_si_despues_pide_otra_cosa():
    script = Script(helper=[msg(calls=[call("search_osint", {"query": "x"})]), msg("listo")],
                    chief=[{"summary": "Busqué.", "confidence": "medium"}], voice=[None])
    rt = master(script)
    rt.policy.declare("osint", "tool_search_osint", ActionSpec(level="aprobacion"))
    say(rt, "buscá en la web x")
    pid = rt.approvals.list()[0]["id"]
    say(rt, f"aprobá el #{pid}")
    say(rt, "buscá en la web otra cosa")          # otra frase: la propuesta se descarta
    say(rt, "sí")
    assert any(p["id"] == pid for p in rt.approvals.list())
    assert any(e["what"] == "propuesta_descartada" for e in rt.audit.entries())


# --- avisos proactivos ---------------------------------------------------------------------------------------------------------
def _pending(rt, level="humano", **kw):
    return rt._new_pending("osint", "jefe", __import__("raphael_core").Level(level), kw.get("summary", "algo"),
                           None, "prueba")


def test_un_pendiente_que_resuelve_una_persona_se_avisa_una_vez_y_uno_de_aprobacion_no():
    rt = master()
    p = _pending(rt, "humano", summary="Reclamo de Marta")
    _pending(rt, "aprobacion", summary="mandar un mail")
    rt.run(rt._settle())
    notes = rt.notices()
    assert [n["text"].rstrip(".") for n in notes] == [f"Te espera algo para resolver vos: #{p['id']} (Reclamo de Marta)"]
    rt.bus.publish("pendiente.creado", {"id": p["id"], "level": "humano", "brigade": "osint"}, source="harness")
    rt.run(rt._settle())
    assert len(rt.notices()) == 1


def test_con_new_pending_all_se_avisan_todos_y_apagado_ninguno():
    rt = master(cfg={"proactive": {"new_pending": "all"}})
    _pending(rt, "aprobacion")
    rt.run(rt._settle())
    assert "esperando tu aprobación" in rt.notices()[0]["text"]
    rt2 = master(cfg={"proactive": {"enabled": False}})
    _pending(rt2, "humano")
    rt2.run(rt2._settle())
    assert rt2.notices() == []


def test_jefe_caido_y_salud_mala_se_avisan():
    rt = master()
    rt.run(rt.bus.apublish("brigada.jefe_caido", {"brigade": "osint", "why": "5 errores seguidos"}, source="harness"))
    rt.run(rt.bus.apublish("brigada.salud", {"brigade": "osint", "ok": False, "down": True}, source="harness"))
    rt.run(rt._settle())
    texts = [n["text"] for n in rt.notices()]
    assert any("El jefe de Osint quedó caído (5 errores seguidos)" in t for t in texts)
    assert any("Osint dejó de atender" in t for t in texts)


def test_el_tick_recuerda_una_vez_los_pendientes_viejos_y_no_ejecuta_nada():
    rt = master(cfg={"proactive": {"new_pending": "none", "remind_after_hours": 24}})
    p = _pending(rt, "aprobacion", summary="mandar el mail")
    rt.run(rt.tick())
    assert rt.notices() == []
    rt.clock.advance(hours=25)
    rt.run(rt.tick())
    rt.run(rt.tick())
    [n] = rt.notices()
    assert n["text"].startswith("Sigue esperando desde hace 25 h") and f"#{p['id']}" in n["text"]
    assert [x["id"] for x in rt.approvals.list()] == [p["id"]]       # nada se aprobó ni se cerró


# --- comandos de borradores -------------------------------------------------------------------------------------------------
DRAFT = {"id": "agenda-diaria", "name": "Agenda diaria", "purpose": "Contar qué hay en la agenda del día, tal cual.",
         "prompt": "Sos el jefe de la agenda diaria. Coordinás a tu efímero y reportás con precisión.", "private": False,
         "helpers": [{"mode": "agenda", "description": "lee la agenda del día",
                      "prompt": "Sos el efímero de agenda. Usá leer_agenda y contá lo que hay, tal cual.",
                      "tools": ["leer_agenda"]}],
         "routing": {"rules": [], "default": "agenda"},
         "validation": {"criterion": "Cuenta los eventos del día sin inventar nada.",
                        "steps": [{"id": "ruteo", "type": "routing", "cases": [{"message": "¿qué hay hoy?", "mode": "agenda"}]}]}}


def with_drafts(tmp_path, edition="personal"):
    rt = master(edition=edition)
    rt.tools.register(Tool("leer_agenda", lambda: {"eventos": []}, description="lee la agenda"))
    store = DraftStore(rt.store.space("_drafts"), Signer(tmp_path / "claves", protect=False),
                       catalog=lambda: {n: rt.tools.get(n) for n in rt.tools.names()})
    Loader(rt, [], installed=False, drafts=store)
    return rt, store


def test_crear_revisar_activar_con_el_hash_exacto_y_desactivar(tmp_path):
    rt, store = with_drafts(tmp_path)
    r = say(rt, "/crear-brigada " + json.dumps(DRAFT))
    assert r.meta["via"] == "command" and "agenda-diaria" in r.text
    h = store.get("agenda-diaria")["hash"]
    assert h[:12] in say(rt, "/revisar-brigada agenda-diaria").text
    assert "no coincide" in say(rt, "/activar-brigada agenda-diaria 0123456789abcdef").text
    assert "Falta el hash" in say(rt, "/activar-brigada agenda-diaria").text
    r = say(rt, f"/activar-brigada agenda-diaria {h[:12]}")
    assert "ACTIVADA" in r.text and "Agregar brigadas" in r.text and store.active_ids() == ["agenda-diaria"]
    assert "Activas por borrador: agenda-diaria" in say(rt, "/brigadas").text
    assert "DESACTIVADA" in say(rt, "/desactivar-brigada agenda-diaria").text and store.active_ids() == []
    assert "descartado" in say(rt, "/descartar-brigada agenda-diaria").text and store.get("agenda-diaria") is None
    assert any(e["what"] == "borrador_activado" for e in rt.audit.entries())


def test_un_texto_que_no_empieza_con_el_comando_no_activa_nada(tmp_path):
    rt, store = with_drafts(tmp_path)
    say(rt, "/crear-brigada " + json.dumps(DRAFT))
    h = store.get("agenda-diaria")["hash"]
    say(rt, f"che, mandale /activar-brigada agenda-diaria {h}")
    assert store.active_ids() == []


def test_un_borrador_invalido_no_se_guarda_y_sin_json_lo_dice(tmp_path):
    rt, store = with_drafts(tmp_path)
    bad = {**DRAFT, "helpers": [{**DRAFT["helpers"][0], "tools": ["borrar_disco"]}]}
    assert "No se pudo armar un borrador válido" in say(rt, "/crear-brigada " + json.dumps(bad)).text
    assert store.list() == []
    assert "Pasame el borrador en JSON" in say(rt, "/crear-brigada una que lea mi agenda").text


def test_en_la_nube_los_borradores_estan_apagados(tmp_path):
    rt, store = with_drafts(tmp_path, edition="cloud")
    assert "no están habilitadas" in say(rt, "/crear-brigada " + json.dumps(DRAFT)).text and store.list() == []
    assert "Montadas:" in say(rt, "/brigadas").text


# --- matriz: los dos modos, con y sin modelo ----------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["master", "secretary"])
@pytest.mark.parametrize("models", [True, False])
@pytest.mark.parametrize("text", ["hola", "¿qué tareas hay?", "buscá en la web cuándo salió Rust 2.0", "asdf qwerty",
                                  "/brigadas", "sí", "aprobá la 3"])
def test_la_matriz_siempre_contesta_algo_y_nunca_rompe(mode, models, text):
    rt = master(good_script(), models=models, cfg={"mode": mode, "watchdog": {"poll_seconds": 0.01},
                                                    "routing": {"classifier": False}})
    r = say(rt, text)
    assert r.text and isinstance(r.meta, dict)
    assert not any(e["what"] == "orquestador_fallido" for e in rt.audit.entries())
    assert rt.approvals.list() == [] or text.startswith("buscá")


# --- montado por la instalación -------------------------------------------------------------------------------------------------
def test_la_instalacion_monta_el_orquestador_de_verdad_con_su_config():
    inst = installation_from({"id": "c", "edition": "cloud", "identity": {"user": "Ana"},
                              "orchestrator": {"entry": "raphael_orchestrator.orchestrator:RaphaelOrchestrator",
                                               "config": {"mode": "secretary"}}})
    rt = Runtime(inst, clock=Clock())
    rep = rt.run(Loader(rt, [SRC], installed=False).apply())
    assert rep["errors"] == {} and rt.orchestrator.name == "raphael" and rt.orchestrator.cfg.mode == "secretary"
    assert "nada pendiente" in rt.run(rt.talk_to_owner("buen día")).text
    assert set(rt.bus.owners("pendiente.creado")) >= {"orquestador"}


def test_una_config_invalida_falla_al_montar_y_queda_el_orden_simple():
    inst = installation_from({"id": "c", "edition": "cloud",
                              "orchestrator": {"entry": "raphael_orchestrator.orchestrator:RaphaelOrchestrator",
                                               "config": {"mode": "jefe"}}})
    rt = Runtime(inst, clock=Clock())
    rep = rt.run(Loader(rt, [SRC], installed=False).apply())
    assert "_orchestrator" in rep["errors"] and rt.orchestrator is None
