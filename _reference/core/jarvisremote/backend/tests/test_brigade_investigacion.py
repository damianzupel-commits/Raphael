"""Tests del jefe de Investigación (brigades/investigacion.py): ruteo, defensas por
construcción y delegación en ayudantes efímeros. Sin LLM ni red: el ayudante se fakea."""

from __future__ import annotations

import asyncio

import pytest

from brigades import chief as chief_mod
from brigades import investigacion as inv
from brigades.chief import BrigadeChief


# --- ruteo --------------------------------------------------------------------
@pytest.mark.parametrize("msg", [
    "investigá el estado de los LLM locales en 2026",
    "buscá novedades sobre Ollama",
    "en caso de que haya algo nuevo sobre arxiv, resumilo",  # 'en caso de' NO es un caso forense
])
def test_clasifica_scout(msg):
    assert inv.clasificar(msg) == "scout"


@pytest.mark.parametrize("msg", [
    "Necesito ayuda con una cosa",
    "Tengo un archivo y quiero entender qué hay adentro",
    "¿Me ayudás con esto?",
    "",
    "hola",
])
def test_pedido_neutro_o_ambiguo_va_a_forense_el_default(msg):
    assert inv.clasificar(msg) == "forense"


@pytest.mark.parametrize("msg", [
    "Investigá en la web las novedades de los modelos de lenguaje locales",
    "Buscá en internet qué es el protocolo ActivityPub",
    "Hacé research sobre embeddings multilingües",
    "Qué hay de nuevo en arxiv sobre RAG",
])
def test_senal_web_explicita_va_a_scout(msg):
    assert inv.clasificar(msg) == "scout"


@pytest.mark.parametrize("msg", [
    "Investigá en la web a quién pertenece este caso",
    "Buscá en internet info sobre el CSV del caso 3",
    "Hacé research sobre la evidencia de WhatsApp",
])
def test_si_hay_senal_de_evidencia_gana_forense_aunque_pida_web(msg):
    assert inv.clasificar(msg) == "forense"


@pytest.mark.parametrize("msg", [
    "ingestá este csv en el caso 12",
    "analizá el export de WhatsApp",
    "sacá el EXIF de foto.jpg",
    "proponé una fusión de entidades",
    "leé C:\\evidencia\\informe.pdf",
])
def test_clasifica_forense_ante_cualquier_senal(msg):
    assert inv.clasificar(msg) == "forense"


# --- defensas por construcción ------------------------------------------------
def test_ayudante_forense_solo_propone_nunca_confirma():
    names = inv._forense_tool_names()
    assert names, "el ayudante forense tiene que tener tools"
    assert not [n for n in names if "confirm_" in n or "reject_" in n]
    assert "investigation_propose_entities" in names


def test_sets_de_tools_aislados():
    scout, forense = inv._scout_tool_names(), inv._forense_tool_names()
    assert "research_topic" in scout and "research_topic" not in forense
    assert not [n for n in scout if n.startswith("investigation_")]
    # el forense no tiene ni web ni filesystem
    assert not [n for n in forense if n.startswith(("fs_", "browser_", "web_"))]


def test_tools_de_los_ayudantes_existen_en_el_registro():
    from app.tools import get_tools

    registered = set(get_tools())
    assert inv.investigacion_tool_names() <= registered


def test_ayudantes_son_efimeros_y_el_jefe_persistente():
    assert inv.investigacion_config().persistent is True
    for spec in inv.AYUDANTES.values():
        assert spec.config().persistent is False


def test_forense_corre_en_el_modelo_compartido_y_scout_en_su_byom():
    # 2026-11-12 (decisión de Damian, privacidad asumida): Forense dejó de ser 'local' y usa el modelo compartido (nemotron/NVIDIA).
    from brigades.config import load_chief_client_model
    from scout.config import build_client

    assert inv.AYUDANTES["forense"].client_model is load_chief_client_model
    assert inv.AYUDANTES["scout"].client_model.__module__ == inv.__name__
    assert build_client  # el BYOM de Scout se reusa, no se duplica


def test_describe_skills_expone_los_dos_modos():
    skills = {s["modo"]: s for s in inv.describe_skills()}
    assert set(skills) == {"scout", "forense"}
    assert all(s["efimero"] for s in skills.values())
    assert "research_topic" in skills["scout"]["tools"]


# --- delegación ---------------------------------------------------------------
class _FakeHelper:
    def __init__(self, behavior):
        self.behavior = behavior
        self.received: list[str] = []

    async def run(self, message, on_event=None):
        self.received.append(message)
        return await self.behavior(message, on_event)


def _chief(monkeypatch, tmp_path, behavior):
    monkeypatch.setattr(chief_mod, "_STATE_DIR", tmp_path)
    jefe = inv.InvestigacionChief(inv.investigacion_config(), client=None, model="x")
    helpers: list[tuple[str, _FakeHelper]] = []

    def spawn(modo):
        h = _FakeHelper(behavior)
        helpers.append((modo, h))
        return h

    monkeypatch.setattr(jefe, "_spawn", spawn)
    return jefe, helpers


def test_delega_en_ayudante_y_persiste_memoria(monkeypatch, tmp_path):
    async def ok(message, on_event):
        return "resultado del ayudante", []

    jefe, helpers = _chief(monkeypatch, tmp_path, ok)
    events: list[dict] = []

    async def cb(ev):
        events.append(ev)

    reply, _ = asyncio.run(jefe.run("investigá Ollama", on_event=cb))
    assert "resultado del ayudante" in reply  # el resumen del reporte (sin LLM del jefe: síntesis degradada, no se pierde nada)
    assert [m for m, _ in helpers] == ["scout"]
    assert {"type": "tool", "name": "delegar:investigacion-scout", "args": "modo=scout"} in events
    assert events[-1]["type"] == "reporte" and "final" not in [e["type"] for e in events]  # el jefe REPORTA; no le habla al usuario

    # el jefe recuerda: el 2do turno le pasa el contexto del 1ro al ayudante (marcado como dato)
    asyncio.run(jefe.run("ahora el caso 3: ingestá un csv"))
    assert [m for m, _ in helpers] == ["scout", "forense"]
    segundo = helpers[1][1].received[0]
    assert "DATO" in segundo and "investigá Ollama" in segundo
    assert "[investigacion-scout] " in segundo and "resultado del ayudante" in segundo


def test_el_feed_no_muestra_el_contexto_previo(monkeypatch, tmp_path):
    async def emite_start(message, on_event):
        await on_event({"type": "start", "topic": message})
        return "ok", []

    jefe, _ = _chief(monkeypatch, tmp_path, emite_start)
    asyncio.run(jefe.run("investigá Ollama"))  # 1er turno: deja memoria
    events: list[dict] = []

    async def cb(ev):
        events.append(ev)

    asyncio.run(jefe.run("investigá vLLM", on_event=cb))
    start = next(e for e in events if e["type"] == "start")
    assert start["topic"] == "investigá vLLM"  # sin el "[Contexto previo…]"


def test_ayudante_que_falla_no_tumba_al_jefe_y_cierra_el_feed(monkeypatch, tmp_path):
    async def boom(message, on_event):
        raise RuntimeError("se cayó Groq")

    jefe, _ = _chief(monkeypatch, tmp_path, boom)
    events: list[dict] = []

    async def cb(ev):
        events.append(ev)

    reply, _ = asyncio.run(jefe.run("investigá algo", on_event=cb))
    assert "se cayó Groq" in reply
    assert events[-1]["type"] == "reporte"  # el feed queda cerrado por el REPORTE del jefe, que informa el fallo
    assert events[-1]["reporte"]["fallos"][0]["ayudante"] == "investigacion-scout" and "se cayó Groq" in events[-1]["reporte"]["fallos"][0]["detalle"]


def test_timeout_corta_al_ayudante(monkeypatch, tmp_path):
    async def cuelga(message, on_event):
        await asyncio.sleep(60)

    jefe, _ = _chief(monkeypatch, tmp_path, cuelga)
    monkeypatch.setattr(inv, "_timeout_seconds", lambda: 0.05)
    reply, _ = asyncio.run(jefe.run("investigá algo"))
    assert "no terminó" in reply


# --- registro / router --------------------------------------------------------
def test_registrado_en_el_registry():
    from brigades import registry

    assert "investigacion" in registry.available()
    # Cerebro y Scout siguen donde estaban
    assert {"scout", "cerebro"} <= set(registry.available())
    # Ahora es una brigada DECLARATIVA: su spec la ejecuta el motor genérico.
    assert registry.get_spec("investigacion") is inv.SPEC
    assert issubclass(inv.InvestigacionChief, BrigadeChief)
    assert type(registry.get_chief("investigacion")).__name__ == "GenericChief"


def test_endpoint_de_skills():
    from app.routers import brigades as br

    out = asyncio.run(br.investigacion_skills())
    assert {s["modo"] for s in out["skills"]} == {"scout", "forense"}


# --- Forense confirma el caso que crea (Ronda 3-4, 2026-11-12) ---------------------------------------------------
def test_prompt_de_forense_exige_confirmar_el_id_y_titulo_del_caso_creado():
    from brigades.investigacion import _FORENSE_PROMPT_EXTRA as p

    assert "CONFIRMÁ LO QUE HICISTE" in p
    assert "id EXACTO" in p and "título" in p
    assert "nunca un id" in p  # no inventar un id que no devolvió la tool
    assert "SEGURIDAD (no negociable)" in p and "no tenés tools para confirmar ni rechazar propuestas".lower() in p.lower()


def test_el_prompt_efectivo_del_ayudante_forense_incluye_la_confirmacion():
    from brigades.investigacion import _forense_ayudante_config

    sp = _forense_ayudante_config().system_prompt
    assert "CONFIRMÁ LO QUE HICISTE" in sp
