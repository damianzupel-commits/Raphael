"""Archivos de claves privados: chmod 600 en Linux y macOS, icacls en Windows (simulado: acá no hay Windows)."""

import subprocess
import sys
from pathlib import Path

import pytest

from raphael_empresas_api import permisos


def fake_run(rc=0, stdout=""):
    calls = []

    def run(args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, rc, stdout=stdout, stderr="")

    run.calls = calls
    return run


@pytest.mark.skipif(sys.platform == "win32", reason="Windows no aplica los permisos de chmod")
def test_en_linux_queda_600(tmp_path):
    f = tmp_path / "raphael.env"
    f.write_text("X=1\n")
    f.chmod(0o644)
    assert permisos.restringir(f, windows=False) is True
    assert (f.stat().st_mode & 0o777) == 0o600 and permisos.es_privado(f, windows=False)


def test_en_windows_corta_la_herencia_y_deja_solo_al_usuario(tmp_path):
    run = fake_run()
    f = tmp_path / "raphael.env"
    assert permisos.restringir(f, windows=True, run=run, user="DESKTOP\\damian") is True
    args = run.calls[0]
    assert args[0] == "icacls" and "/inheritance:r" in args and "DESKTOP\\damian:(F)" in args
    assert not any("Everyone" in a or "Users" in a for a in args[2:])   # args[1] es la ruta, que en Windows pasa por C:\Users


def test_si_icacls_falla_no_finge_que_quedo_protegido(tmp_path):
    assert permisos.restringir(tmp_path / "a", windows=True, run=fake_run(rc=5)) is False

    def roto(*a, **k):
        raise FileNotFoundError("icacls")

    assert permisos.restringir(tmp_path / "a", windows=True, run=roto) is False


def test_es_privado_en_windows_detecta_accesos_abiertos(tmp_path):
    ok = fake_run(stdout=f"{tmp_path}\\x DESKTOP\\damian:(F)\n NT AUTHORITY\\SYSTEM:(F)\n")
    abierto = fake_run(stdout=f"{tmp_path}\\x BUILTIN\\Users:(I)(RX)\n DESKTOP\\damian:(F)\n")
    assert permisos.es_privado(Path(tmp_path / "x"), windows=True, run=ok) is True
    assert permisos.es_privado(Path(tmp_path / "x"), windows=True, run=abierto) is False
