"""El kit del VPS: el paquete trae lo que hace falta y nada que no deba (tests, bases, secretos)."""

import importlib.util
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[4] / "infra" / "cloud"
spec = importlib.util.spec_from_file_location("armar_paquete", DEPLOY / "armar_paquete.py")
armar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(armar)


@pytest.fixture(scope="module")
def names(tmp_path_factory):
    out = armar.build(DEPLOY.parent / "client-install" / "clienta.installation.yaml", tmp_path_factory.mktemp("pk"))
    with tarfile.open(out) as t:
        return {m.name: m for m in t.getmembers()}, out


def test_trae_los_cuatro_paquetes_y_los_scripts(names):
    n, _ = names
    for p in ("raphael-core", "raphael-orchestrator", "raphael-empresas", "raphael-empresas-api"):
        assert f"raphael-v2-nube/piezas/{p}/pyproject.toml" in n
    assert "raphael-v2-nube/piezas/raphael-empresas/src/raphael_empresas/manifest.yaml" in n
    for s in armar.SCRIPTS:
        assert f"raphael-v2-nube/{s}" in n
    assert n["raphael-v2-nube/instalar-v2.sh"].mode & 0o111


def test_no_trae_tests_bases_ni_secretos(names):
    n, _ = names
    bad = [x for x in n if "/tests/" in x or x.endswith((".sqlite", ".env", ".jks", ".pyc")) or "/.datos/" in x
           or "/panel/" in x or "__pycache__" in x]
    assert bad == []


def test_los_scripts_son_de_unix_y_pasan_bash_n(names, tmp_path):
    _, out = names
    with tarfile.open(out) as t:
        t.extractall(tmp_path, filter="data")
    base = tmp_path / "raphael-v2-nube"
    for s in ("instalar-v2.sh", "actualizar-v2.sh", "copia.sh", "raphael-empresas.service", "Caddyfile.plantilla"):
        assert b"\r\n" not in (base / s).read_bytes(), s
    if shutil.which("bash"):
        for s in ("instalar-v2.sh", "actualizar-v2.sh", "copia.sh"):
            assert subprocess.run(["bash", "-n", str(base / s)]).returncode == 0, s


def test_plantillas_sin_valores():
    for f in ("meta.env.plantilla", "tienda.env.plantilla"):
        for line in (DEPLOY / f).read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                assert v in ("", "mock", "graph.instagram.com", "v26.0"), (f, k)
