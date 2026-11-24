"""Modelo intercambiable por rol (brigades/config.py::resolve_role_model, P0.2 / DIV-08). Sin red: los clientes son falsos
y solo registran con qué endpoint y key se armaron. Lo que se prueba: la cadena override del rol -> default del tipo ->
global, que cambiar el modelo de un rol es SOLO configuración, y que la key de un proveedor nunca se usa para otro."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from brigades import config as cfg

NVIDIA, GROQ, LOCAL = "https://integrate.api.nvidia.com/v1", "https://api.groq.com/openai/v1", "http://127.0.0.1:11434/v1"
VARS = ("BRIGADE_LLM", "ORQUESTADOR_LLM", "ORQUESTADOR_VOZ_LLM", "BRIGADE_CEREBRO_LLM", "BRIGADE_RADAR_TECNICO_LLM",
        "AYUDANTE_INVESTIGACION_FORENSE_LLM", "AYUDANTE_CEREBRO_RECUPERADOR_LLM")


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Config conocida: global = NVIDIA con su key; sin ninguna variable por rol. Los clientes son falsos."""
    for v in VARS:
        for suf in ("BASE_URL", "MODEL", "API_KEY"):
            monkeypatch.delenv(f"{v}_{suf}", raising=False)
    monkeypatch.setattr(cfg.settings, "lmstudio_base_url", NVIDIA)
    monkeypatch.setattr(cfg.settings, "lmstudio_model", "nvidia/nemotron-global")
    monkeypatch.setattr(cfg.settings, "llm_api_key", "key-nvidia-global")
    monkeypatch.setattr(cfg, "_cliente", lambda base, key: SimpleNamespace(base_url=base, api_key=key))


def _env(monkeypatch, prefijo, base=None, model=None, key=None):
    for suf, val in (("BASE_URL", base), ("MODEL", model), ("API_KEY", key)):
        if val is not None:
            monkeypatch.setenv(f"{prefijo}_{suf}", val)


# --- la cadena ------------------------------------------------------------------------------------------------------------
def test_sin_overrides_el_jefe_cae_al_default_de_su_tipo_y_despues_al_global(monkeypatch):
    client, model = cfg.resolve_role_model("jefe", "cerebro")
    assert (client.base_url, client.api_key, model) == (NVIDIA, "key-nvidia-global", "nvidia/nemotron-global")
    _env(monkeypatch, "BRIGADE_LLM", model="nvidia/nemotron-jefes")  # default del TIPO (jefes y ayudantes shared)
    assert cfg.resolve_role_model("jefe", "cerebro")[1] == "nvidia/nemotron-jefes"
    assert cfg.describe_role_model("jefe", "cerebro")["origen"] == "BRIGADE_LLM_*"


def test_cambiar_solo_el_modelo_de_un_jefe_hereda_endpoint_y_key(monkeypatch):
    _env(monkeypatch, "BRIGADE_LLM", model="nvidia/nemotron-jefes")
    _env(monkeypatch, "BRIGADE_CEREBRO_LLM", model="nvidia/otro-mas-grande")  # override del ROL: solo el modelo
    client, model = cfg.resolve_role_model("jefe", "cerebro")
    assert model == "nvidia/otro-mas-grande" and (client.base_url, client.api_key) == (NVIDIA, "key-nvidia-global")
    assert cfg.resolve_role_model("jefe", "investigacion")[1] == "nvidia/nemotron-jefes"  # los demás jefes no cambian
    d = cfg.describe_role_model("jefe", "cerebro")
    assert d["label"] == "otro-mas-grande (NVIDIA)" and d["origen"] == "BRIGADE_CEREBRO_LLM_*" and d["ok"]


def test_el_id_de_la_variable_es_el_id_en_mayusculas_con_guion_bajo(monkeypatch):
    _env(monkeypatch, "BRIGADE_RADAR_TECNICO_LLM", model="m-radar")
    assert cfg.resolve_role_model("jefe", "radar-tecnico")[1] == "m-radar"
    assert cfg._env_slug("investigacion-forense") == "INVESTIGACION_FORENSE"


def test_un_rol_se_puede_llevar_a_un_modelo_local_sin_key(monkeypatch):
    _env(monkeypatch, "BRIGADE_CEREBRO_LLM", base=LOCAL, model="jarvis-text-v2")
    client, model = cfg.resolve_role_model("jefe", "cerebro")
    assert (client.base_url, model) == (LOCAL, "jarvis-text-v2") and client.api_key == "local"  # NO se le manda la key de NVIDIA
    assert cfg.describe_role_model("jefe", "cerebro")["local"] is True


def test_la_key_de_un_proveedor_nunca_se_usa_para_otro(monkeypatch):
    _env(monkeypatch, "BRIGADE_CEREBRO_LLM", base=GROQ, model="openai/gpt-oss-120b")  # otro proveedor, sin su key
    with pytest.raises(RuntimeError, match="No se reutiliza la key de otro proveedor"):
        cfg.resolve_role_model("jefe", "cerebro")
    d = cfg.describe_role_model("jefe", "cerebro")
    assert d["ok"] is False and "sin resolver" in d["label"] and "key-nvidia" not in str(d)  # se informa; nunca se muestra una key
    _env(monkeypatch, "BRIGADE_CEREBRO_LLM", key="key-groq")
    client, _ = cfg.resolve_role_model("jefe", "cerebro")
    assert (client.base_url, client.api_key) == (GROQ, "key-groq")


def test_load_chief_client_model_ya_no_filtra_la_key_global_a_otro_endpoint(monkeypatch):
    _env(monkeypatch, "BRIGADE_LLM", base=GROQ, model="openai/gpt-oss-120b")
    with pytest.raises(RuntimeError, match="otro proveedor"):
        cfg.load_chief_client_model()
    _env(monkeypatch, "BRIGADE_LLM", key="key-groq")
    client, model = cfg.load_chief_client_model()
    assert (client.base_url, client.api_key, model) == (GROQ, "key-groq", "openai/gpt-oss-120b")


# --- ayudantes ------------------------------------------------------------------------------------------------------------
def test_el_ayudante_usa_su_modelo_declarado_tal_cual_si_no_hay_override(monkeypatch):
    byom = (SimpleNamespace(base_url=GROQ, api_key="key-groq-scout"), "openai/gpt-oss-120b")
    assert cfg.resolve_role_model("ayudante", helper_id="investigacion-scout", declarado=lambda: byom) is byom  # mismo cliente


def test_el_override_del_ayudante_gana_sobre_lo_declarado_y_no_mezcla_keys(monkeypatch):
    declarado = lambda: (SimpleNamespace(base_url=NVIDIA, api_key="key-nvidia-global"), "nvidia/nemotron-global")  # noqa: E731
    _env(monkeypatch, "AYUDANTE_INVESTIGACION_FORENSE_LLM", model="nvidia/nemotron-chico")
    client, model = cfg.resolve_role_model("ayudante", helper_id="investigacion-forense", declarado=declarado)
    assert model == "nvidia/nemotron-chico" and (client.base_url, client.api_key) == (NVIDIA, "key-nvidia-global")
    _env(monkeypatch, "AYUDANTE_INVESTIGACION_FORENSE_LLM", base=LOCAL, model="jarvis-text-v2")  # a local: privacidad
    client, model = cfg.resolve_role_model("ayudante", helper_id="investigacion-forense", declarado=declarado)
    assert (client.base_url, client.api_key, model) == (LOCAL, "local", "jarvis-text-v2")


def test_los_specs_reales_resuelven_por_rol(monkeypatch):
    from brigades import cerebro, investigacion

    _env(monkeypatch, "AYUDANTE_CEREBRO_RECUPERADOR_LLM", model="m-recuperador")
    _env(monkeypatch, "BRIGADE_CEREBRO_LLM", model="m-jefe-cerebro")
    assert cerebro.SPEC.ayudante("recuperador").resolve_client_model()[1] == "m-recuperador"
    assert cerebro.SPEC.load_client_model()[1] == "m-jefe-cerebro"
    assert investigacion.SPEC.load_client_model()[1] == "nvidia/nemotron-global"  # otro jefe: no lo toca


# --- orquestador y su voz ----------------------------------------------------------------------------------------------------
def test_el_orquestador_conserva_su_regla_la_key_solo_de_su_variable_o_del_mismo_endpoint(monkeypatch):
    client, model = cfg.load_orquestador_client_model()  # sin ORQUESTADOR_LLM_*: default NVIDIA; el global ES NVIDIA -> reusa su key
    assert (client.base_url, client.api_key, model) == (cfg.DEFAULT_ORQUESTADOR_BASE_URL, "key-nvidia-global", cfg.DEFAULT_ORQUESTADOR_MODEL)
    monkeypatch.setattr(cfg.settings, "lmstudio_base_url", "https://openrouter.ai/api/v1")  # el global es OTRO proveedor
    with pytest.raises(RuntimeError, match="ORQUESTADOR_LLM_API_KEY"):
        cfg.load_orquestador_client_model()
    _env(monkeypatch, "ORQUESTADOR_LLM", key="key-orq")
    assert cfg.load_orquestador_client_model()[0].api_key == "key-orq"


def test_la_voz_usa_el_modelo_del_orquestador_salvo_que_tenga_el_suyo(monkeypatch):
    _env(monkeypatch, "ORQUESTADOR_LLM", model="nvidia/nemotron-orq", key="key-orq")
    assert cfg.resolve_role_model("voz")[1] == "nvidia/nemotron-orq"
    _env(monkeypatch, "ORQUESTADOR_VOZ_LLM", model="nvidia/modelo-que-redacta-mejor")
    client, model = cfg.resolve_role_model("voz")
    assert model == "nvidia/modelo-que-redacta-mejor" and client.api_key == "key-orq"
    assert cfg.resolve_role_model("orquestador")[1] == "nvidia/nemotron-orq"  # el clasificador no cambia
    assert cfg.describe_role_model("voz")["origen"] == "ORQUESTADOR_VOZ_LLM_*"


def test_rol_desconocido_se_rechaza():
    with pytest.raises(ValueError):
        cfg.resolve_role_model("router")


def test_ningun_modelo_ni_endpoint_hardcodeado_fuera_del_default_documentado():
    """Requisito (a): ningún rol hardcodea modelo ni endpoint. Lo único fijo en el CÓDIGO (docstrings y comentarios no
    cuentan) es el default global documentado y la tabla de nombres de proveedores, los dos en brigades/config.py."""
    import ast
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    patron = re.compile(r"nemotron-3\.5|integrate\.api\.nvidia\.com|api\.groq\.com|gpt-oss-120b|openrouter\.ai")
    permitidos = {"DEFAULT_ORQUESTADOR_MODEL", "DEFAULT_ORQUESTADOR_BASE_URL", "_PROVEEDORES"}
    culpables = []
    for carpeta in ("brigades", "orquestador"):
        for f in sorted((raiz / carpeta).glob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            docstrings, exentos = set(), set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                    primero = node.body[0]
                    if isinstance(primero, ast.Expr) and isinstance(primero.value, ast.Constant) and isinstance(primero.value.value, str):
                        docstrings.add(id(primero.value))
                if f.name == "config.py" and isinstance(node, ast.Assign) and any(getattr(t, "id", "") in permitidos for t in node.targets):
                    exentos |= {id(n) for n in ast.walk(node)}
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str) and patron.search(node.value)
                        and id(node) not in docstrings and id(node) not in exentos):
                    culpables.append(f"{carpeta}/{f.name}:{node.lineno}: {node.value[:80]!r}")
    assert culpables == [], "\n".join(culpables)
