"""Config (config de la brigada > entorno > por defecto seguro), guardarraíles de texto, sandbox y modos."""

import os
import sys

import pytest
from raphael_core.contract import ActionError

from raphael_operaciones import guardrails
from raphael_operaciones.config import ConfigError, load_config
from raphael_operaciones.fs import Sandbox, SandboxError
from raphael_operaciones.modes import ModeState, OperationMode, agent_turn, parse_mode


# --- config -------------------------------------------------------------------------------------------------------------
def test_los_defaults_son_los_mas_seguros():
    c = load_config({}, {})
    assert c.adapters == "simulado" and c.mode is OperationMode.AUTONOMOUS and not c.real
    assert not (c.pc_shell or c.desktop or c.phone_shell or c.phone_camera or c.fs_allow_delete or c.supervisor
                or c.web_local_net)


def test_la_config_manda_sobre_el_entorno_y_el_entorno_sobre_el_default():
    env = {"OPERACIONES_ADAPTADORES": "real", "OPERACIONES_PC_SHELL": "si", "OPERACIONES_FS_RAICES": "/a;/b"}
    c = load_config({"adaptadores": "simulado"}, env)
    assert c.adapters == "simulado" and c.pc_shell is True and c.fs_roots == ("/a", "/b")


@pytest.mark.parametrize("cfg", [{"adaptadores": "casi"}, {"pc_shell": "tal vez"}, {"celular_timeout": 0},
                                 {"fs_raices": 5}])
def test_un_valor_invalido_da_error_claro(cfg):
    with pytest.raises(ConfigError):
        load_config(cfg, {})


def test_un_modo_desconocido_cae_a_autonomo_y_avisa():
    c = load_config({"modo": "libre"}, {})
    assert c.mode is OperationMode.AUTONOMOUS and "no reconocido" in c.notes[0]
    assert parse_mode("Supervisado")[0] is OperationMode.SUPERVISED


# --- guardarraíles ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cmd", ["format c:", "cmd /c format d: /q", "echo hola && format e:", "diskpart", "bcdedit /set x",
                                 "shutdown /s /t 0", "rm -rf /", "rm -rf ~", "mkfs.ext4 /dev/sda", "dd if=x of=/dev/sda",
                                 "vssadmin delete shadows /all", "rd /s /q C:\\", ":(){ :|:& };:"])
def test_frena_lo_obviamente_destructivo(cmd):
    with pytest.raises(guardrails.BlockedError):
        guardrails.check_pc_command(cmd)


@pytest.mark.parametrize("cmd", ["git log --format=%h", "python -c \"print('{}'.format(1))\"", "dir", "echo formatear",
                                 "pytest -q", "rm -rf build"])
def test_no_frena_lo_comun_aunque_tenga_palabras_parecidas(cmd):
    guardrails.check_pc_command(cmd)


def test_frena_en_el_celular_y_al_lanzar():
    with pytest.raises(guardrails.BlockedError):
        guardrails.check_phone_command("rm -rf /")
    with pytest.raises(guardrails.BlockedError):
        guardrails.check_launch("diskpart.exe")
    guardrails.check_phone_command("ls /sdcard")


def test_el_registro_tacha_secretos_y_lo_tipeado():
    r = guardrails.redact_args({"password": "x", "text": "mi clave", "url": "u" * 300, "n": 1})
    assert r["password"] == "***" and r["text"] == "<8 caracteres>" and r["url"].endswith("…") and r["n"] == 1


# --- sandbox y modos ----------------------------------------------------------------------------------------------------
def _sb(tmp_path, mode=OperationMode.AUTONOMOUS, **cfg):
    ms = ModeState(mode)
    return Sandbox(load_config({"carpeta_segura": str(tmp_path / "seg"), **cfg}, {}), ms), ms


def test_no_se_sale_de_la_carpeta_segura(tmp_path):
    sb, _ = _sb(tmp_path)
    sb.ensure_home()
    sb.write_file("a/b.txt", "hola")
    assert sb.read_file("a/b.txt")["content"] == "hola"
    for bad in ("../fuera.txt", str(tmp_path / "otra" / "x.txt"), "a/../../x"):
        with pytest.raises(SandboxError):
            sb.resolve(bad)


@pytest.mark.skipif(sys.platform == "win32", reason="los symlinks piden permisos en Windows")
def test_un_symlink_que_apunta_afuera_no_sirve(tmp_path):
    sb, _ = _sb(tmp_path)
    home = sb.ensure_home()
    (tmp_path / "secreto").mkdir()
    (tmp_path / "secreto" / "s.txt").write_text("x")
    os.symlink(tmp_path / "secreto", home / "enlace")
    with pytest.raises(SandboxError):
        sb.read_file("enlace/s.txt")


def test_el_modo_supervisado_abre_raices_amplias_y_el_autonomo_no(tmp_path):
    amplia = tmp_path / "amplia"
    amplia.mkdir()
    (amplia / "x.txt").write_text("hola")
    sb, ms = _sb(tmp_path, fs_supervisado=str(amplia))
    with pytest.raises(SandboxError):
        sb.read_file(str(amplia / "x.txt"))
    ms.set(OperationMode.SUPERVISED)
    assert sb.read_file(str(amplia / "x.txt"))["content"] == "hola"
    ms.set(OperationMode.AUTONOMOUS)    # bajar siempre se puede
    with pytest.raises(SandboxError):
        sb.read_file(str(amplia / "x.txt"))


def test_una_carpeta_prohibida_gana_aunque_este_dentro_de_una_raiz(tmp_path):
    sb, ms = _sb(tmp_path, fs_prohibidas=str(tmp_path / "seg" / "boveda"))
    sb.ensure_home()
    (tmp_path / "seg" / "boveda").mkdir()
    (tmp_path / "seg" / "boveda" / "p.txt").write_text("personal")
    with pytest.raises(SandboxError, match="personal"):
        sb.read_file("boveda/p.txt")


def test_borrar_esta_apagado_salvo_que_se_habilite(tmp_path):
    sb, _ = _sb(tmp_path)
    sb.write_file("x.txt", "1")
    with pytest.raises(SandboxError):
        sb.delete_path("x.txt")
    sb2, _ = _sb(tmp_path, fs_permitir_borrar=True)
    assert sb2.delete_path("x.txt")["deleted"].endswith("x.txt")
    with pytest.raises(SandboxError, match="raíz"):
        sb2.delete_path(".")


def test_mover_no_pisa_un_destino_que_ya_existe(tmp_path):
    sb, _ = _sb(tmp_path)
    sb.write_file("a.txt", "1")
    sb.write_file("b.txt", "2")
    with pytest.raises(ActionError):
        sb.move_path("a.txt", "b.txt")


def test_no_se_puede_auto_escalar_desde_un_llamado_de_tool():
    ms = ModeState(OperationMode.AUTONOMOUS)
    with agent_turn(), pytest.raises(PermissionError, match="Auto-escalada"):
        ms.set(OperationMode.SUPERVISED)
    assert ms.mode is OperationMode.AUTONOMOUS
    ms.set(OperationMode.SUPERVISED)      # fuera de un llamado (la persona) sí
    with agent_turn():
        ms.set(OperationMode.AUTONOMOUS)  # bajar sí
