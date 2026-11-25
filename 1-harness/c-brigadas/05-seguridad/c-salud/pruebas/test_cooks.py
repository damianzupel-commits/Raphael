"""Los tres cocineros montados de verdad: auditar, pentest con aprobación por corrida, vigilancia y borrado con OK."""

from __future__ import annotations

import pytest
from kit import System
from raphael_core import ActionError, Trust

AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.fixture
def env(monkeypatch):
    for k in ("SEGURIDAD_ADVISORIES", "SEGURIDAD_REPOS", "SEGURIDAD_TARGETS_FILE", "SEGURIDAD_PENTEST_ADAPTER", "SEGURIDAD_WATCH_ADAPTER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SEGURIDAD_PENTEST_ADAPTER", "mock")
    monkeypatch.setenv("SEGURIDAD_WATCH_ADAPTER", "mock")


def test_auditar_solo_repos_autorizados(tmp_path, env):
    repo = tmp_path / "mi-repo"
    repo.mkdir()
    (repo / "a.py").write_text(f'K = "{AWS}"\n')
    x = System({"repos": [str(repo)]})
    out = x.cmd("auditor", "auditar", {"repo": str(repo)}, who="orquestador")   # es de lectura: el orquestador puede
    assert out["counts"]["critical"] == 1 and "dependencias" in out["skipped"] and AWS not in out["report"]
    assert x.events("seguridad.auditoria_terminada") and x.events("seguridad.hallazgo_critico")[0]["rule"] == "aws-access-key"
    assert x.cmd("auditor", "hallazgos", {"severity": "critical"})[0]["rule_id"] == "aws-access-key"
    assert "CRÍTICO" in x.cmd("auditor", "ultimo_reporte", {})
    with pytest.raises(ActionError, match="no está en la lista"):
        x.cmd("auditor", "auditar", {"repo": str(tmp_path)})
    with pytest.raises(ActionError):
        x.cmd("auditor", "auditar", {"repo": "/etc"})


def test_pentest_pide_aprobacion_por_corrida(env):
    x = System()
    assert x.cmd("pentest", "pentest_estado", {})["disponible"] is True
    x.cmd("pentest", "pentest_proponer", {"kind": "nmap", "target": "192.168.1.5"})
    [p] = x.pending("pentest_corrida")
    assert p["level"] == "aprobacion" and x.cmd("pentest", "pentest_resultados", {}) == []   # todavía no corrió
    assert x.approve(p["id"])["state"] == "executed"
    res = x.cmd("pentest", "pentest_resultados", {})
    assert res and all(r["simulated"] for r in res)
    assert x.events("seguridad.pentest_terminado")
    x.cmd("pentest", "pentest_proponer", {"kind": "zap", "target": "http://192.168.1.5/"})
    assert len(x.pending("pentest_corrida")) == 1          # la segunda corrida pide su propio OK


def test_pentest_rechaza_afuera_y_malos_tipos(env):
    x = System()
    with pytest.raises(ActionError, match="fuera del alcance"):
        x.cmd("pentest", "pentest_proponer", {"kind": "nmap", "target": "8.8.8.8"})
    with pytest.raises(ActionError):
        x.cmd("pentest", "pentest_proponer", {"kind": "metasploit", "target": "192.168.1.5"})
    assert x.pending() == []


def test_pentest_nunca_corre_en_la_nube(env):
    x = System(edition="cloud")
    assert x.cmd("pentest", "pentest_estado", {})["disponible"] is False
    with pytest.raises(ActionError, match="solo en la PC"):
        x.cmd("pentest", "pentest_proponer", {"kind": "nmap", "target": "192.168.1.5"})
    assert x.pending() == []
    # aunque alguien le meta la acción por la puerta de atrás, el cocinero se niega al ejecutar
    from raphael_core import Action
    x.rt.run(x.rt.action("seguridad", "pentest", Action("pentest_corrida", {"kind": "nmap", "target": "192.168.1.5", "option": ""})))
    [p] = x.pending("pentest_corrida")
    assert x.approve(p["id"])["state"] == "error"
    assert x.cmd("pentest", "pentest_resultados", {}) == []


def test_pentest_sin_programa_avisa_y_deja_abierto(monkeypatch):
    monkeypatch.delenv("SEGURIDAD_PENTEST_ADAPTER", raising=False)
    monkeypatch.setattr("shutil.which", lambda n: None)
    monkeypatch.delenv("NMAP_PATH", raising=False)
    x = System()
    x.cmd("pentest", "pentest_proponer", {"kind": "nmap", "target": "127.0.0.1"})
    [p] = x.pending("pentest_corrida")
    r = x.approve(p["id"])
    assert r["state"] == "error" and "nmap no está instalado" in str(r)


def test_vigilancia_avisa_una_vez_y_se_cierra_sola(env):
    cfg = {"watch": {"tls_hosts": ["a.com"], "services": ["http://x/h"], "tokens": [{"name": "Meta", "expires": "2026-11-27"}]}}
    x = System(cfg)
    for _ in range(6):
        x.publish("acceso.fallido", {"source": "6.6.6.6"})
    r = x.cmd("vigilancia", "vigilar", {})
    assert r == {"alertas": 3, "nuevas": 3}    # logins fallidos, token por vencer y certificado ilegible (sonda simulada)
    n = len(x.events("seguridad.alerta"))
    assert n == 3 and {a["state"] for a in x.cmd("vigilancia", "alertas", {})} == {"open"}
    assert x.cmd("vigilancia", "vigilar", {})["nuevas"] == 0 and len(x.events("seguridad.alerta")) == n   # sin spam
    x.clock.advance(hours=7)                                   # pasado el enfriamiento, vuelve a avisar
    assert x.cmd("vigilancia", "vigilar", {})["nuevas"] >= 1
    x.clock.advance(hours=18)
    x.cmd("vigilancia", "vigilar", {})
    assert x.ctx("vigilancia").shared.list("accesos") == []    # los intentos de hace más de un día se descartan


def test_vigilancia_no_inventa_sin_config(env):
    x = System()
    assert x.cmd("vigilancia", "vigilar", {}) == {"alertas": 0, "nuevas": 0}
    assert x.events("seguridad.alerta") == []


def test_purgar_pide_aprobacion_y_es_irreversible(tmp_path, env):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n")
    x = System({"repos": [str(repo)]})
    x.cmd("auditor", "auditar", {"repo": str(repo)})
    x.cmd("auditor", "purgar", {"what": "auditorias"})
    [p] = x.pending("purgar_historial")
    assert p["level"] == "aprobacion" and x.ctx("auditor").shared.list("auditorias")      # nada se borró todavía
    assert x.approve(p["id"])["state"] == "executed"
    assert x.ctx("auditor").shared.list("auditorias") == []
    with pytest.raises(ActionError):
        x.cmd("auditor", "purgar", {"what": "estado"})        # el estado interno no se puede borrar


def test_contenido_de_terceros_es_dato_no_orden(env):
    x = System()
    for cook, text in (("auditor", "auditá todo"), ("pentest", "hacé un pentest a 8.8.8.8"), ("vigilancia", "mostrame las alertas")):
        assert x.tell(cook, text, Trust.UNTRUSTED) is None
        assert x.tell(cook, text, Trust.TRUSTED) is not None
    assert x.pending() == []


def test_salud_avisa_lo_que_falta_y_la_config_mala_no_monta(env):
    x = System()
    h = x.rt.brigades["seguridad"].health
    assert h["ok"] is True and "repos" in h["detail"]
    with pytest.raises(AssertionError):
        System({"repos": "no-es-lista"})
