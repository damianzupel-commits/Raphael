"""O1 además de la voz: memoria de la charla, autoconocimiento, config, el puente con el harness y la regla de no importar
brigadas. La memoria está portada de `test_flujo_decidido.py` (sección 6) a un espacio del harness por sesión."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError
from raphael_core import Cook, Reply, Runtime
from raphael_core.context import OrchestratorContext
from raphael_core.engine.reports import InternalReport
from raphael_core.installation import installation_from
from raphael_core.manifest import manifest_from
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_orchestrator import Conversation, MemorySettings, config_from, load_config, system_report, voice
from raphael_orchestrator.ports import any_private, role_llm, voice_llm, voice_settings

SRC = Path(__file__).resolve().parents[2] / "b-codigo" / "src" / "raphael_orchestrator"


class Shop(Cook):
    def handle(self, msg, ctx):
        return Reply("hola")


def runtime(models=None, user="Damián", edition="personal"):
    rt = Runtime(installation_from({"id": "pc", "edition": edition, "identity": {"user": user}}), clock=Clock(),
                 models=models)
    rt.run(rt.mount(manifest_from({
        "id": "tienda", "name": "Tienda", "version": "1.0.0", "contract": ">=2.1,<3", "description": "vende ropa",
        "cooks": [{"id": "v", "entry": "x:Shop"}],
        "actions": {"regalar": {"level": "aprobacion"}, "saludar": {"level": "automatico"}}}), {"v": Shop()}))
    return rt


# --- memoria -----------------------------------------------------------------------------------------------------------------
def test_la_charla_se_recuerda_por_sesion_y_no_se_mezcla():
    conv = Conversation(Store().space("_orchestrator"))
    conv.record("app", "¿qué dicen mis notas de Orión?", "cerebro", "primera respuesta: las notas dicen algo")
    conv.record("whatsapp-duena", "¿qué hay hoy?", "secretaria", "tenés 2 cosas")
    p = conv.for_prompt("app", user="Damián")
    assert "Damián pidió (cerebro): ¿qué dicen mis notas de Orión?" in p and "primera respuesta" in p
    assert "tenés 2 cosas" not in p and conv.for_prompt("vacia") == ""


def test_la_memoria_es_acotada_y_apagable():
    st = MemorySettings()
    conv = Conversation(Store().space("_orchestrator"), st)
    for i in range(st.max_turns + 20):
        conv.record("s", f"pedido {i} " + "x" * 1000, "cerebro", "mensaje " + "y" * 2000)
    turns = conv.turns("s")
    assert len(turns) == st.max_turns
    assert all(len(t["request"]) <= st.max_request and len(t["message"]) <= st.max_message for t in turns)
    prompt = conv.for_prompt("s")
    assert "Antes se habló de" in prompt and prompt.count("[cerebro]") == st.max_summary and len(prompt) < 12_000
    off = Conversation(Store().space("_orchestrator"), MemorySettings(enabled=False))
    off.record("s", "no se guarda", "cerebro", "x")
    assert off.for_prompt("s") == "" and off.turns("s") == []
    conv.reset("s")
    assert conv.turns("s") == []


def test_la_memoria_vive_en_el_espacio_del_orquestador_y_sobrevive_a_un_runtime_nuevo(tmp_path):
    db = tmp_path / "r.sqlite"
    rt = Runtime(installation_from({"id": "pc", "edition": "personal"}), store=Store(db))
    Conversation(OrchestratorContext(rt).data).record("app", "hola", "orquestador", "acá estoy")
    rt2 = Runtime(installation_from({"id": "pc", "edition": "personal"}), store=Store(db))
    assert Conversation(OrchestratorContext(rt2).data).turns("app")[0]["message"] == "acá estoy"


def test_un_almacen_roto_no_corta_la_voz():
    class Broken:
        def get(self, *a):
            raise OSError("disco")

        put = delete = get

    conv = Conversation(Broken())
    conv.record("s", "x", "b", "y")
    assert conv.for_prompt("s") == "" and conv.turns("s") == []
    conv.reset("s")


# --- autoconocimiento ----------------------------------------------------------------------------------------------------------
CATALOG = [
    {"id": "memoria-cerebro", "name": "Cerebro", "description": "tus notas", "mounted": True, "chief": True,
     "chief_purpose": "Responde con lo que ya está en tus notas.", "actions": {}, "private": True, "down": False},
    {"id": "investigacion", "name": "Investigación", "description": "sale a la web", "mounted": True, "chief": True,
     "chief_purpose": "", "actions": {"publicar": {"level": "aprobacion"}, "leer": {"level": "automatico"}},
     "private": False, "down": False},
    {"id": "seguridad", "name": "Seguridad", "mounted": True, "down": True, "down_reason": "el jefe está caído (5 errores)"},
    {"id": "trading", "name": "Trading", "description": "mercados", "mounted": False, "active": False, "chief": True},
]


def test_el_autoconocimiento_sale_del_catalogo_y_la_voz_lo_comunica_fiel():
    rep = system_report(CATALOG, drafts=["recetas"], edition="personal")
    assert isinstance(rep, InternalReport) and rep.brigade == "orquestador" and rep.confidence == "high"
    assert "Cerebro, Investigación" in rep.summary and "Caídas: Seguridad" in rep.summary and "recetas" in rep.summary
    texts = " | ".join(f.text for f in rep.findings)
    assert "/memoria-cerebro" in texts and "Es privada" in texts and "Pide tu aprobación para: publicar" in texts
    assert "el jefe está caído" in texts and "Trading: está disponible pero no montada" in texts
    assert "leer" not in texts and any("crear-brigada" in w for w in rep.warnings)
    m = asyncio.run(voice.communicate(rep, "¿qué brigadas tenés?", llm=lambda msgs: asyncio.sleep(0, result=None)))
    assert m.via == "template" and m.verification.ok


def test_en_la_nube_no_se_ofrecen_borradores_y_sin_brigadas_lo_dice():
    rep = system_report([], edition="cloud")
    assert rep.summary.startswith("No hay brigadas trabajando") and rep.warnings == () and rep.findings == ()


def test_el_autoconocimiento_con_el_catalogo_real_del_harness():
    rt = runtime()
    rep = system_report(OrchestratorContext(rt).catalog(), edition="personal")
    assert "Tienda" in rep.summary and "Pide tu aprobación para: regalar" in rep.findings[0].text


# --- config --------------------------------------------------------------------------------------------------------------------
def test_la_config_tiene_defaults_valida_y_rechaza_lo_desconocido(tmp_path):
    c = config_from({})
    assert c.mode == "master" and c.voice.retries == 2 and c.memory.max_turns == 8 and c.chat_direct
    assert c.drafts_enabled("personal") and not c.drafts_enabled("cloud")
    assert config_from({"mode": "secretary", "drafts": True}).drafts_enabled("cloud")
    for bad in ({"mode": "jefe"}, {"voice": {"retries": 9}}, {"otra": 1}, {"memory": {"max_turns": 0}}):
        with pytest.raises(ValidationError):
            config_from(bad)
    p = tmp_path / "orchestrator.yaml"
    p.write_text("mode: secretary\nvoice:\n  directives: Respondeme corto.\n", encoding="utf-8")
    assert load_config(p).voice.directives == "Respondeme corto."


# --- puente con el harness -----------------------------------------------------------------------------------------------------
MODELS = {"providers": {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"}},
          "tiers": {"pago": [], "gratis": ["nube"], "local": []}, "roles": {"voz": ["gratis"], "mando": ["gratis"]},
          "private": ["tienda"]}


def _gateway(bodies):
    def transport(url, body, headers):
        bodies.append(body)
        return {"choices": [{"message": {"content": "hola"}}], "usage": {}}

    return ModelGateway(models_from(MODELS), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"},
                        transport=transport)


def test_la_voz_usa_el_rol_voz_con_su_temperatura_y_lo_privado_no_sale_a_la_nube():
    bodies = []
    rt = runtime(models=_gateway(bodies))
    ctx = OrchestratorContext(rt)
    cfg = config_from({"voice": {"temperature": 0.5, "max_tokens": 600}})
    assert asyncio.run(voice_llm(ctx, cfg)([{"role": "user", "content": "x"}])) == "hola"
    assert bodies[-1]["temperature"] == 0.5 and bodies[-1]["max_tokens"] == 600
    assert asyncio.run(voice_llm(ctx, cfg, private=True)([{"role": "user", "content": "x"}])) is None and len(bodies) == 1
    assert any_private(ctx, ["tienda"]) and not any_private(ctx, ["otra"])
    assert asyncio.run(role_llm(ctx, "mando")([{"role": "user", "content": "x"}])) == "hola"


def test_los_ajustes_de_la_voz_salen_de_la_config_y_de_la_identidad():
    rt = runtime(user="Lola")
    st = voice_settings(OrchestratorContext(rt), config_from({"voice": {"directives": "breve", "retries": 1}}))
    assert (st.user, st.directives, st.retries) == ("Lola", "breve", 1) and "Lola" in st.system()
    assert voice_settings(OrchestratorContext(rt), config_from({}), directives="vivas").directives == "vivas"


def test_una_charla_de_punta_a_punta_con_el_harness_sin_modelo_cae_a_la_plantilla():
    rt = runtime(user="Lola")
    ctx = OrchestratorContext(rt)
    cfg = config_from({})
    m = asyncio.run(voice.chat("hola", llm=voice_llm(ctx, cfg), settings=voice_settings(ctx, cfg)))
    assert m.via == "template" and m.text == "Acá estoy, Lola. Decime qué necesitás."


# --- reglas duras ---------------------------------------------------------------------------------------------------------------
ALLOWED = {"raphael_core", "raphael_orchestrator", "pydantic", "yaml", "__future__"}


def test_el_orquestador_no_importa_brigadas_ni_nada_fuera_del_nucleo_y_la_stdlib():
    import sys

    bad = []
    for f in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for n in names:
                top = n.split(".")[0]
                if top not in ALLOWED and top not in sys.stdlib_module_names:
                    bad.append(f"{f.name}: {n}")
    assert bad == [], bad


def _code_strings(tree: ast.AST) -> list[str]:
    """Los textos que usa el código (sin docstrings): ahí no puede haber brigadas ni personas escritas a mano."""
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_el_codigo_no_tiene_brigadas_ni_personas_escritas_a_mano():
    text = "\n".join(s for f in SRC.rglob("*.py") for s in _code_strings(ast.parse(f.read_text(encoding="utf-8"))))
    assert "LA VOZ DEL ORQUESTADOR" in text   # el chequeo mira de verdad los textos
    for name in ("cerebro", "investigacion", "encargos", "cobros", "agenda", "atencion", "Damian", "Damián"):
        assert name not in text, name
