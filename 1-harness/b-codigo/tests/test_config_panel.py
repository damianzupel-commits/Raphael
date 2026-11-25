"""La lógica de la pantalla de Configuración del panel (sin ventana)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "panel"))

import pytest  # noqa: E402
from config_modelo import Configuracion  # noqa: E402


@pytest.fixture
def cfg(tmp_path):
    base = tmp_path / "base.yaml"
    base.write_text(
        """
providers:
  ollama: {base_url: "http://127.0.0.1:11434/v1", model: llama3.1:8b}
  nvidia: {base_url: "https://integrate.api.nvidia.com/v1", model: nemo, api_key_env: NVIDIA_API_KEY}
tiers: {local: [ollama], gratis: [nvidia]}
roles: {mando: [gratis, local], cocinero: [local, gratis]}
private: [seguridad, memoria]
""",
        encoding="utf-8",
    )
    return Configuracion(tmp_path / "raphael.env", tmp_path / "modelos.usuario.yaml", tmp_path / "panel.json", base, environ={})


def test_claves_se_guardan_aplican_y_se_deshacen(cfg):
    cfg.env_file.write_text("# mío\nOTRA=1\n", encoding="utf-8")
    assert cfg.aplicar({"NVIDIA_API_KEY": "nvapi-abc"}) == []
    assert cfg.env() == {"OTRA": "1", "NVIDIA_API_KEY": "nvapi-abc"} and cfg.environ["NVIDIA_API_KEY"] == "nvapi-abc"
    assert "# mío" in cfg.env_file.read_text(encoding="utf-8")
    assert "nvapi-abc" not in str(cfg.historial())  # el historial nunca lleva la clave
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
        cfg.agregar_proveedor("raro", "http://ejemplo.com/v1", "m")  # remota sin https


def test_sacar_de_solo_local_pide_confirmar_y_agregar_es_libre(cfg):
    cfg.poner_privadas(["seguridad", "memoria", "trading"])
    with pytest.raises(PermissionError):
        cfg.poner_privadas(["seguridad"])
    assert cfg.privadas() == ["memoria", "seguridad", "trading"]
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


def test_detecta_el_servicio_por_el_formato():
    from config_modelo import detectar_servicio, variable_para

    assert detectar_servicio("nvapi-abc").variable == "NVIDIA_API_KEY"
    assert detectar_servicio("sk-or-v1-abc").variable == "OPENROUTER_API_KEY"  # sk-or- gana sobre sk-
    assert detectar_servicio("sk-abc").variable == "OPENAI_API_KEY"
    assert detectar_servicio("BSAxyz").variable == "BRAVE_SEARCH_API_KEY"
    assert detectar_servicio("APP_USR-123").variable == "MP_ACCESS_TOKEN"
    assert detectar_servicio("cualquier-cosa") is None
    assert variable_para("Mi Servicio") == "MI_SERVICIO_API_KEY"
    assert variable_para("nvidia") == "NVIDIA_API_KEY" and variable_para("GROQ_API_KEY") == "GROQ_API_KEY"
    with pytest.raises(ValueError):
        variable_para("1!")


def test_agregar_clave_arranca_vacio_y_lista_lo_cargado(cfg):
    assert cfg.claves() == []
    assert cfg.agregar_clave("nvapi-abc") == ("NVIDIA_API_KEY", [])
    with pytest.raises(ValueError, match="no reconozco"):
        cfg.agregar_clave("clave-rara-123")
    assert cfg.agregar_clave("clave-rara-123", "Mi Servicio")[0] == "MI_SERVICIO_API_KEY"
    assert cfg.agregar_clave("TEST-9")[1] == ["MP_ACCESS_TOKEN"]
    claves = {c["servicio"]: c["valor"] for c in cfg.claves()}
    assert claves["NVIDIA"] == "nvapi-abc" and claves["MI_SERVICIO_API_KEY"] == "clave-rara-123"
    with pytest.raises(ValueError):
        cfg.agregar_clave("con espacios adentro", "Otro")
    cfg.aplicar(None, ["NVIDIA_API_KEY"])
    assert "NVIDIA" not in {c["servicio"] for c in cfg.claves()}


def test_el_boton_recargar_relee_el_env_y_aplica_los_modelos(tmp_path, monkeypatch):
    from demo import PanelState

    monkeypatch.setattr("raphael_core.loader._from_entry_points", lambda: ([], []))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("RAPHAEL_ENV_FILE", str(tmp_path / "raphael.env"))
    st = PanelState(project_root=tmp_path, data_dir=tmp_path / "datos")
    # editado a mano, afuera del panel
    (tmp_path / "raphael.env").write_text("OPENROUTER_API_KEY=sk-or-nueva-1234\n", encoding="utf-8")
    assert st.reload() == ""
    assert __import__("os").environ["OPENROUTER_API_KEY"] == "sk-or-nueva-1234"


def test_un_private_vacio_de_versiones_viejas_no_pisa_la_lista_del_proyecto(cfg):
    cfg.usuario_file.write_text("private: []\n", encoding="utf-8")
    assert cfg.privadas() == ["memoria", "seguridad"]


def test_la_lista_solo_local_solo_suma_y_saca_lo_confirmado(cfg):
    cfg.poner_privadas(["seguridad", "memoria", "trading"])
    assert cfg.privadas() == ["memoria", "seguridad", "trading"]
    with pytest.raises(PermissionError):
        cfg.poner_privadas([])  # vaciarla pide confirmar
    cfg.poner_privadas(["seguridad"], confirmar_nube=True)
    assert cfg.privadas() == ["seguridad"]
    cfg.poner_privadas(["seguridad", "memoria"])  # volver a sumar es libre
    assert cfg.privadas() == ["memoria", "seguridad"]


def test_con_un_cargador_propio_tus_cambios_pasan_por_el(cfg):
    import yaml as _yaml

    from raphael_core.models.config import models_from

    def cargador(ruta, env):
        datos = _yaml.safe_load(open(ruta, encoding="utf-8").read())
        datos["providers"]["ollama"]["model"] = env.get("OLLAMA_MODEL", "x")  # lo que hace cerebro.load con el entorno
        return models_from(datos)

    cfg.cargador = cargador
    cfg.environ["OLLAMA_MODEL"] = "qwen3:8b"
    cfg.poner_rol("mando", ["local"])
    c = cfg.modelos()
    assert c.providers["ollama"].model == "qwen3:8b" and c.roles["mando"] == ["local"]
