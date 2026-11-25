"""La lógica de la pantalla de Configuración del panel (sin ventana)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "panel"))

import pytest  # noqa: E402
from config_modelo import Configuracion  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text("""
providers:
  ollama: {base_url: "http://127.0.0.1:11434/v1", model: llama3.1:8b}
  nvidia: {base_url: "https://integrate.api.nvidia.com/v1", model: nemo, api_key_env: NVIDIA_API_KEY}
tiers: {local: [ollama], gratis: [nvidia]}
roles: {mando: [gratis, local], cocinero: [local, gratis]}
private: [seguridad, memoria]
""", encoding="utf-8")
    return Configuracion(tmp_path / "raphael.env", tmp_path / "modelos.usuario.yaml", tmp_path / "panel.json", base, environ={})


def test_claves_se_guardan_aplican_y_se_deshacen(cfg):
    cfg.env_file.write_text("# mío\nOTRA=1\n", encoding="utf-8")
    assert cfg.aplicar({"NVIDIA_API_KEY": "nvapi-abc"}) == []
    assert cfg.env() == {"OTRA": "1", "NVIDIA_API_KEY": "nvapi-abc"} and cfg.environ["NVIDIA_API_KEY"] == "nvapi-abc"
    assert "# mío" in cfg.env_file.read_text(encoding="utf-8")
    assert "nvapi-abc" not in str(cfg.historial())                     # el historial nunca lleva la clave
    cfg.deshacer()
    assert "NVIDIA_API_KEY" not in cfg.env() and "NVIDIA_API_KEY" not in cfg.environ


def test_valida_todo_antes_de_cambiar_algo(cfg):
    with pytest.raises(ValueError):
        cfg.aplicar({"NVIDIA_API_KEY": "nvapi-ok", "LOCAL_LLM_URL": "http://ejemplo.com:1234"})
    assert cfg.env() == {}
    with pytest.raises(ValueError):
        cfg.aplicar({"RAPHAEL_PUBLIC_URL": "http://x"})
    assert cfg.aplicar({"MP_ACCESS_TOKEN": "TEST-123"}) == ["MP_ACCESS_TOKEN"]


def test_proveedor_propio_y_destino_por_brigada(cfg):
    cfg.agregar_proveedor("groq", "https://api.groq.com/openai/v1", "llama-3.3", "GROQ_API_KEY")
    c = cfg.poner_destino("cocinero", "investigacion", ["groq"])
    assert c.overrides["cocinero.investigacion"] == ["propio-cocinero-investigacion"]
    assert c.tiers["propio-cocinero-investigacion"] == ["groq"]
    c = cfg.poner_destino("cocinero", "investigacion", [])
    assert "cocinero.investigacion" not in c.overrides


def test_privadas_solo_aceptan_proveedores_de_esta_pc(cfg):
    with pytest.raises(ValueError, match="solo-local"):
        cfg.poner_destino("cocinero", "memoria", ["nvidia"])
    cfg.poner_destino("cocinero", "memoria", ["ollama"])
    with pytest.raises(ValueError):
        cfg.agregar_proveedor("raro", "http://ejemplo.com/v1", "m", escalon="local")
    with pytest.raises(ValueError):
        cfg.agregar_proveedor("raro", "http://ejemplo.com/v1", "m")        # remota sin https


def test_sacar_de_solo_local_pide_confirmar_y_agregar_es_libre(cfg):
    cfg.poner_privadas(["seguridad", "memoria", "trading"])
    with pytest.raises(PermissionError):
        cfg.poner_privadas(["seguridad"])
    assert cfg.privadas() == ["seguridad", "memoria", "trading"]
    cfg.poner_privadas(["seguridad"], confirmar_nube=True)
    assert cfg.privadas() == ["seguridad"]


def test_roles_y_deshacer_modelos(cfg):
    cfg.poner_rol("mando", ["local"])
    assert cfg.modelos().roles["mando"] == ["local"]
    with pytest.raises(ValueError):
        cfg.poner_rol("mando", ["inexistente"])
    cfg.deshacer()
    assert cfg.modelos().roles["mando"] == ["gratis", "local"]


def test_apariencia_perfiles_y_exportar_sin_claves(cfg):
    assert cfg.poner_apariencia(tema="claro", acento="#ff7922")["tema"] == "claro"
    with pytest.raises(ValueError):
        cfg.poner_apariencia(acento="rojo")
    cfg.aplicar({"NVIDIA_API_KEY": "nvapi-secreta", "RAPHAEL_VOZ_MODO": "local"})
    exp = cfg.exportar()
    assert "nvapi-secreta" not in str(exp) and exp["variables"] == {"RAPHAEL_VOZ_MODO": "local"}
    cfg.guardar_perfil("ahorro")
    cfg.aplicar({"RAPHAEL_VOZ_MODO": "off"})
    cfg.cargar_perfil("ahorro")
    assert cfg.env()["RAPHAEL_VOZ_MODO"] == "local" and cfg.env()["NVIDIA_API_KEY"] == "nvapi-secreta"
