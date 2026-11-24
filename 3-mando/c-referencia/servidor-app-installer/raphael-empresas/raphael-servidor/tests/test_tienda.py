"""Tienda de brigadas: arranca solo con el orquestador; las brigadas se descargan y se acoplan en caliente."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from raphael_servidor.app import crear_app
from raphael_servidor.config import Config

RAIZ = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (RAIZ / "raphael-encargos").is_dir() or not shutil.which("git"),
                                reason="faltan los repos vecinos o git")


@pytest.fixture
def cliente(tmp_path):
    piezas = tmp_path / "piezas"
    piezas.mkdir()
    for base in ("raphael-harness", "raphael-orquestador"):            # lo que trae la instalación
        shutil.copytree(RAIZ / base, piezas / base, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    datos = tmp_path / "datos"
    datos.mkdir()
    perfil = yaml.safe_load((RAIZ / "raphael-harness" / "ejemplos" / "perfil-ropa-medida.yaml").read_text(encoding="utf-8"))
    perfil["brigadas"] = []
    (datos / "perfil.yaml").write_text(yaml.safe_dump(perfil, allow_unicode=True), encoding="utf-8")
    # "GitHub" de prueba: copias git de los repos de brigadas
    fuente = tmp_path / "github"
    for r in ("raphael-atencion", "raphael-encargos", "raphael-cobros"):
        shutil.copytree(RAIZ / r, fuente / r, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git"))
        subprocess.run(["git", "init", "-q"], cwd=fuente / r, check=True)
        subprocess.run(["git", "add", "-A"], cwd=fuente / r, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], cwd=fuente / r, check=True)
    cfg = Config(dir=datos, piezas=str(piezas), fuente_local=str(fuente), tareas=False)
    with TestClient(crear_app(cfg)) as c:
        c.headers["Authorization"] = "Bearer " + c.post("/api/primera-clave", json={"clave": "clave-segura"}).json()["token"]
        yield c, piezas, datos


def estados(c):
    return {b["nombre"]: b["estado"] for b in c.get("/api/brigadas").json()["brigadas"]}


def test_arranca_solo_con_el_orquestador(cliente):
    c, _, _ = cliente
    d = c.get("/api/brigadas").json()
    assert d["orquestador"].startswith("orquestador ")
    assert set(estados(c).values()) == {"bloqueada"}
    r = c.post("/api/probar", json={"texto": "¿qué horario tienen?"}).json()["respuestas"]
    assert "te responde Ana" in r[0]                                     # sin brigadas: pasa a una persona


def test_descargar_activar_y_el_orquestador_la_usa_sin_reiniciar(cliente):
    c, piezas, datos = cliente
    assert c.post("/api/brigadas/atencion/activar").status_code == 400   # primero hay que descargarla
    assert c.post("/api/brigadas/atencion/descargar").json()["estado"] == "descargada"
    assert (piezas / "raphael-atencion" / "src").is_dir()
    assert estados(c)["atencion"] == "descargada"
    assert c.post("/api/brigadas/atencion/activar").json() == {"activas": ["atencion"]}
    assert "atencion" in yaml.safe_load((datos / "perfil.yaml").read_text(encoding="utf-8"))["brigadas"]
    assert "Atendemos" in c.post("/api/probar", json={"texto": "¿qué horario tienen?"}).json()["respuestas"][0]
    assert c.get("/api/resumen").json()["brigadas"] == {"atencion": "0.1.0"}

    c.post("/api/brigadas/atencion/desactivar")
    assert estados(c)["atencion"] == "descargada"
    assert "te responde" in c.post("/api/probar", json={"texto": "¿qué horario tienen?", "quien": "otro"}).json()["respuestas"][0]


def test_dependencias_entre_brigadas(cliente):
    c, _, _ = cliente
    c.post("/api/brigadas/cobros/descargar")
    assert "necesita" in c.post("/api/brigadas/cobros/activar").json()["detail"]
    c.post("/api/brigadas/encargos/descargar")
    c.post("/api/brigadas/encargos/activar")
    assert c.post("/api/brigadas/cobros/activar").status_code == 200
    assert "la necesita" in c.post("/api/brigadas/encargos/desactivar").json()["detail"]


def test_solo_lo_del_catalogo(cliente):
    c, _, _ = cliente
    assert c.post("/api/brigadas/malware/descargar").status_code == 400
    assert c.post("/api/brigadas/agenda/descargar").status_code == 400  # no está en la fuente de prueba


def test_la_duena_le_habla_al_orquestador_y_ve_lo_que_pasa_en_las_brigadas_acopladas(cliente):
    c, _, _ = cliente
    assert "nada pendiente" in c.post("/api/secretaria", json={"texto": "buen día"}).json()["texto"]
    for b in ("atencion", "encargos"):
        c.post(f"/api/brigadas/{b}/descargar")
        c.post(f"/api/brigadas/{b}/activar")
    c.post("/api/probar", json={"texto": "me llegó roto, quiero hablar con alguien", "nombre": "Marta"})
    r = c.post("/api/secretaria", json={"texto": "¿qué tareas tenemos hoy?"}).json()
    assert r["tareas"] and "Marta" in r["tareas"][0]["titulo"]
    f = c.post("/api/secretaria", json={"texto": "contame la 1"}).json()["ficha"]
    assert f["pendiente"]["nivel"] == "humano" and f["conversacion"] and f["opciones"][0]["recomendada"]
    assert "Te recomiendo la 1)" in c.post("/api/secretaria", json={"texto": "¿cuál hago primero?"}).json()["texto"]
    assert c.post("/api/secretaria", json={"texto": "x"}, headers={"Authorization": "Bearer mal"}).status_code == 401


def test_conectar_el_celular_es_opt_in_y_pide_reiniciar(cliente, monkeypatch):
    c, _, datos = cliente
    monkeypatch.delenv("RAPHAEL_HOST", raising=False)
    d = c.get("/api/conexion").json()
    assert d == {"activado": False, "escuchando": False, "direcciones": [], "nube": False}          # por defecto solo desde la propia PC
    assert c.post("/api/conexion", json={"celular": True}).json() == {"activado": True, "reiniciar": True}
    assert (datos / "celular.on").exists() and c.get("/api/conexion").json()["activado"]
    monkeypatch.setenv("RAPHAEL_HOST", "0.0.0.0")                                     # así arranca el lanzador con la marca
    assert c.get("/api/conexion").json()["escuchando"] is True
    c.post("/api/conexion", json={"celular": False})
    assert not (datos / "celular.on").exists()
    assert c.get("/api/conexion", headers={"Authorization": "Bearer mal"}).status_code == 401
