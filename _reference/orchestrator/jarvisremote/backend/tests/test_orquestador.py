"""Tests del Orquestador standalone (backend/orquestador/): ruteo, servidor y arranque liviano.
Sin LLM ni red: los jefes y el clasificador se fakean."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from orquestador import routing
from orquestador.server import create_app

PORT = 8010
HOST = {"host": f"127.0.0.1:{PORT}"}


# --- ruteo --------------------------------------------------------------------
@pytest.mark.parametrize("msg,expected", [
    ("¿qué sé de ransomware?", "cerebro"),
    ("qué tengo guardado sobre mis notas de biología", "cerebro"),
    ("conectá las notas del vault sobre redes", "cerebro"),
    ("investigá el estado de los LLM locales en la web", "investigacion"),
    ("ingestá este csv en el caso 3", "investigacion"),
    ("analizá el export de WhatsApp del caso", "investigacion"),
    ("leé https://example.com/paper y resumilo", "investigacion"),
])
def test_reglas_rutean_a_la_brigada_correcta(msg, expected):
    brigade, _ = routing.route_by_rules(msg)
    assert brigade == expected


def test_en_caso_de_no_es_un_caso_forense():
    brigade, _ = routing.route_by_rules("en caso de duda, qué sé de mis notas")
    assert brigade == "cerebro"


def test_sin_senal_o_empate_no_decide():
    assert routing.route_by_rules("hola")[0] is None
    assert routing.route_by_rules("noticias y memoria")[0] is None  # 1 contra 1: empate
    assert routing.route_by_rules("investigá en mis notas")[0] == "cerebro"  # "mis notas" pesa más


def test_override_por_prefijo_saca_el_prefijo():
    r = asyncio.run(routing.route("/investigacion qué sé de X", llm=None))
    assert (r.brigade, r.via, r.message) == ("investigacion", "override", "qué sé de X")
    r = asyncio.run(routing.route("/cerebro: investigá algo en la web", llm=None))
    assert (r.brigade, r.via) == ("cerebro", "override")


def test_brigada_forzada_desde_la_ui_gana_a_las_reglas():
    r = asyncio.run(routing.route("investigá en la web", brigade="cerebro", llm=None))
    assert (r.brigade, r.via) == ("cerebro", "override")


def test_ambiguo_usa_el_llm_local_si_responde():
    async def llm(msg):
        return "investigacion"

    r = asyncio.run(routing.route("Explicame bien cómo viene el tema ese", llm=llm))
    assert (r.brigade, r.via) == ("investigacion", "llm")


def test_un_pedido_muy_corto_sin_senales_no_consulta_al_modelo():
    llamado = []

    async def llm(msg):
        llamado.append(msg)
        return "investigacion"

    for corto in ("hola", "gracias, quedó claro", "¿Cómo venimos?"):
        r = asyncio.run(routing.route(corto, llm=llm))
        assert (r.brigade, r.via) == ("cerebro", "default") and "sin consultar al modelo" in r.reason
    assert llamado == []  # ni latencia ni un mensaje más saliendo a la nube por un saludo


@pytest.mark.parametrize("llm", [None, "falla", "basura"])
def test_ambiguo_sin_llm_cae_a_cerebro(llm):
    async def falla(msg):
        return None

    async def basura(msg):
        return "ninguna"

    fn = {None: None, "falla": falla, "basura": basura}[llm]
    r = asyncio.run(routing.route("hola", llm=fn))
    assert (r.brigade, r.via) == ("cerebro", "default")


def test_reglas_claras_no_llaman_al_llm():
    async def llm(msg):
        raise AssertionError("no debería clasificar con LLM si las reglas deciden")

    r = asyncio.run(routing.route("¿qué sé de ransomware?", llm=llm))
    assert r.via == "reglas"


# --- servidor -----------------------------------------------------------------
class _FakeChief:
    def __init__(self, brigade):
        self.config = SimpleNamespace(name=f"Raphael {brigade}", tool_names={"a", "b"})
        self.model = "fake"
        self.received: list[str] = []

    async def run(self, message, on_event=None):
        self.received.append(message)
        await on_event({"type": "start", "topic": message})
        await on_event({"type": "final", "reply": "listo"})
        return "listo", []


@pytest.fixture
def client(monkeypatch):
    chiefs = {b: _FakeChief(b) for b in routing.BRIGADES}
    monkeypatch.setattr("brigades.registry.get_chief", lambda b: chiefs[b])
    monkeypatch.setattr(routing, "llm_classify", lambda m: asyncio.sleep(0, result=None))
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    c.chiefs = chiefs
    return c


def _stream(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_index_inyecta_el_token_solo_en_host_local(client):
    html = client.get("/").text
    assert 'const TOKEN = "tok"' in html and "__TOKEN__" not in html
    evil = TestClient(create_app(PORT, token="tok"), headers={"host": "evil.example.com"})
    assert evil.get("/").status_code == 403  # anti DNS-rebinding


def test_la_api_exige_token(client):
    assert client.post("/api/chat", json={"message": "hola"}).status_code == 401
    assert client.get("/api/meta", headers={"authorization": "Bearer mal"}).status_code == 401
    assert client.get("/api/meta", headers={"authorization": "Bearer tok"}).status_code == 200


def test_chat_emite_route_y_despues_el_feed_del_jefe(client):
    resp = client.post("/api/chat", json={"message": "¿qué sé de ransomware?"}, headers={"authorization": "Bearer tok"})
    events = _stream(resp)
    assert events[0]["type"] == "route" and events[0]["brigade"] == "cerebro" and events[0]["via"] == "reglas"
    # el `final` del jefe NO sale: su texto se envuelve en un reporte y el ÚNICO `final` es el del orquestador (su voz)
    assert [e["type"] for e in events[1:]] == ["start", "reporte", "comunicacion", "final"]
    assert events[-1]["origen"] == "orquestador" and "listo" in events[-1]["reply"]
    assert events[2]["reporte"]["sintesis_degradada"] is True  # un jefe sin contrato no pasa en silencio: reporte degradado
    assert client.chiefs["cerebro"].received == ["¿qué sé de ransomware?"]
    assert client.chiefs["investigacion"].received == []


def test_chat_rutea_a_investigacion_y_respeta_la_brigada_forzada(client):
    h = {"authorization": "Bearer tok"}
    ev = _stream(client.post("/api/chat", json={"message": "ingestá este csv en el caso 3"}, headers=h))
    assert ev[0]["brigade"] == "investigacion"
    ev = _stream(client.post("/api/chat", json={"message": "ingestá este csv", "brigade": "cerebro"}, headers=h))
    assert ev[0]["brigade"] == "cerebro" and ev[0]["via"] == "override"


def test_mensaje_vacio_y_jefe_que_falla_se_reportan_como_evento(client, monkeypatch):
    h = {"authorization": "Bearer tok"}
    assert _stream(client.post("/api/chat", json={"message": "  "}, headers=h))[0]["type"] == "error"

    async def boom(message, on_event=None):
        raise RuntimeError("Ollama apagado")

    monkeypatch.setattr(client.chiefs["cerebro"], "run", boom)
    ev = _stream(client.post("/api/chat", json={"message": "¿qué sé de X?"}, headers=h))
    assert ev[-1] == {"type": "error", "message": "Ollama apagado"}


# --- arranque liviano ---------------------------------------------------------
def test_arranque_liviano_no_carga_el_monolito():
    backend = Path(__file__).resolve().parent.parent
    code = (
        "import sys; sys.path.insert(0, '.')\n"
        "from orquestador import slim_tools; slim_tools.install(); slim_tools.stub_agent_persona()\n"
        "import orquestador.server; from brigades.registry import get_chief\n"
        "get_chief('cerebro'); get_chief('investigacion')\n"
        "from app.tools import get_tools\n"
        "from brigades.investigacion import investigacion_tool_names\n"
        "from brigades.cerebro import CEREBRO_TOOL_NAMES\n"
        "faltan = (investigacion_tool_names() | CEREBRO_TOOL_NAMES) - set(get_tools())\n"
        "heavy = [m for m in ('pywinauto','pyautogui','yara','clamd','scapy','app.malware','app.pentest','app.phone_link','app.main')\n"
        "         if m in sys.modules]\n"
        "stub = not hasattr(sys.modules['app.agent'], '__file__')\n"
        "print('RESULT', sorted(faltan), heavy, stub)\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=backend, capture_output=True, text=True, timeout=12)
    last = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT")]
    assert last, out.stderr[-500:]
    assert last[0] == "RESULT [] [] True"


# --- datos de las vistas por brigada ------------------------------------------
def test_endpoints_de_las_vistas_por_brigada(client):
    h = {"authorization": "Bearer tok"}
    skills = client.get("/api/investigacion/skills", headers=h).json()["skills"]
    assert {s["modo"] for s in skills} == {"scout", "forense"}
    assert "items" in client.get("/api/cerebro/activity", headers=h).json()
    assert "text" in client.get("/api/cerebro/directrices", headers=h).json()
    for path in ("/api/investigacion/skills", "/api/cerebro/activity", "/api/cerebro/directrices", "/api/investigacion/notes"):
        assert client.get(path).status_code == 401  # sin token no hay datos


# --- modelo EFECTIVO en la UI (2026-11-12) ---------------------------------------------------------------------------
def test_describe_endpoint_muestra_modelo_real_y_proveedor():
    from brigades.config import describe_endpoint

    d = describe_endpoint("https://integrate.api.nvidia.com/v1/", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    assert d["label"] == "nemotron-3.5-super-vl-120b-a12b (NVIDIA)" and d["local"] is False
    assert describe_endpoint("https://openrouter.ai/api/v1", "nvidia/nemotron-3.5-super-vl:free")["label"].endswith("(OpenRouter)")
    assert describe_endpoint("https://api.groq.com/openai/v1", "openai/gpt-oss-120b")["label"] == "gpt-oss-120b (Groq)"
    o = describe_endpoint("http://127.0.0.1:11434/v1", "jarvis-text-v2")
    assert o["local"] is True and o["label"] == "jarvis-text-v2 (Ollama)"  # solo lo genuinamente local se muestra como local


def test_meta_informa_el_modelo_del_orquestador_y_el_efectivo_de_cada_brigada(monkeypatch):
    from brigades import config as bc

    monkeypatch.setattr(bc, "orquestador_info", lambda: {"model": "nvidia/x", "name": "x", "provider": "NVIDIA", "local": False,
                                                          "label": "x (NVIDIA)"})
    chiefs = {b: SimpleNamespace(config=SimpleNamespace(name=b, tool_names=set()), model="raw", model_label="nemo (NVIDIA)")
              for b in (*routing.BRIGADES, *routing.DIRECTAS)}
    monkeypatch.setattr("brigades.registry.get_chief", lambda b: chiefs[b])
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    j = c.get("/api/meta", headers={"Authorization": "Bearer tok", **HOST}).json()
    assert j["orquestador"]["label"] == "x (NVIDIA)"
    assert all(b["model_label"] == "nemo (NVIDIA)" for b in j["brigades"])


def test_la_ui_no_dice_local_fijo_y_muestra_el_modelo_del_orquestador():
    ui = (Path(__file__).resolve().parent.parent / "orquestador" / "ui.html").read_text(encoding="utf-8")
    assert 'id="orqmodelo"' in ui and "j.orquestador" in ui and "model_label" in ui
    for viejo in ("NÚCLEO · LOCAL", 'llm:"modelo local"', "(modelo local)", "Está corriendo Ollama"):
        assert viejo not in ui


# --- el lanzador no reutiliza un orquestador VIEJO (bug real 2026-11-12) ------------------------------------------------
def test_health_informa_cuando_arranco_el_proceso():
    c = TestClient(create_app(PORT, token="tok"), headers=HOST)
    j = c.get("/api/health", headers=HOST).json()
    assert j["ok"] and isinstance(j["started"], float)


def test_un_orquestador_que_arranco_antes_del_codigo_o_del_env_es_viejo(monkeypatch):
    from orquestador import launcher

    monkeypatch.setattr(launcher, "code_mtime", lambda: 1000.0)
    monkeypatch.setattr(launcher, "started_at", lambda port, timeout=1.0: 900.0)
    assert launcher.is_stale(8010) is True          # arrancó antes del último cambio: viejo
    monkeypatch.setattr(launcher, "started_at", lambda port, timeout=1.0: 1500.0)
    assert launcher.is_stale(8010) is False         # arrancó después: al día
    monkeypatch.setattr(launcher, "started_at", lambda port, timeout=1.0: None)
    assert launcher.is_stale(8010) is True          # no informa cuándo arrancó: es de antes de este chequeo


def test_code_mtime_ve_el_codigo_y_el_env():
    from orquestador import launcher

    assert launcher.code_mtime() > 0
