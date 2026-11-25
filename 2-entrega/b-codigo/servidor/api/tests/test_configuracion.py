"""Configuración desde la app: claves a voluntad, guardadas solo en local, aplicadas en caliente y nunca devueltas completas."""

import stat

import pytest
from fastapi.testclient import TestClient
from test_entorno import boot

from raphael_empresas_api.__main__ import first_key
from raphael_empresas_api.app import create_app
from raphael_empresas_api.meta import MetaChannel, http_post, settings_from_env

KEY = "sk-or-v1-secreta-de-prueba-1234"


@pytest.fixture
def api(tmp_path):
    environ: dict[str, str] = {}
    meta = MetaChannel.build(settings_from_env(environ), threaded=False)
    from raphael_empresas.boot import start
    from test_entorno import INSTALACION, ORCH_DEV

    dev = [ORCH_DEV / "15-empresas" / "b-codigo", ORCH_DEV / "00-orquestador" / "b-codigo"]
    rt, _ = start(INSTALACION, tmp_path, dev_dirs=dev, installed=False, env=environ, connectors=meta.connectors())
    meta.bind(rt)
    env_file = tmp_path / "raphael.env"
    env_file.write_text("# mis claves\nOPENROUTER_API_KEY=\nMETA_MODE=mock\n", encoding="utf-8")
    app = create_app(rt, tick=False, meta=meta, env_file=env_file, environ=environ)
    app.state.auth.set_key("clave-segura")
    with TestClient(app) as c:
        tok = c.post("/api/v1/login", json={"key": "clave-segura", "device": "t"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c, rt, meta, env_file, environ


def put(c, set_=None, clear=None):
    return c.put("/api/v1/config", json={"set": set_ or {}, "clear": clear or []})


def test_sin_sesion_no_se_ve_ni_se_cambia_nada(api):
    c, *_ = api
    c.headers.pop("Authorization")
    assert c.get("/api/v1/config").status_code == 401
    assert put(c, {"OPENROUTER_API_KEY": KEY}).status_code == 401


def test_la_pagina_es_publica_pero_sin_datos(api):
    c, *_ = api
    c.headers.pop("Authorization")
    r = c.get("/config")
    assert r.status_code == 200 and "Configuración" in r.text and r.headers["cache-control"] == "no-store"
    assert KEY not in r.text


def test_poner_una_clave_de_ia_la_aplica_en_caliente_y_no_vuelve_completa(api):
    c, rt, _, env_file, environ = api
    assert rt.models.label("voz") == "sin modelo"
    r = put(c, {"OPENROUTER_API_KEY": KEY})
    assert r.status_code == 200 and KEY not in r.text
    row = next(f for f in r.json()["fields"] if f["name"] == "OPENROUTER_API_KEY")
    assert row["set"] and row["hint"] == "…1234" and "value" not in row
    assert rt.models.label("voz").startswith("deepseek-flash")
    assert KEY not in c.get("/api/v1/config").text
    txt = env_file.read_text(encoding="utf-8")
    assert f"OPENROUTER_API_KEY={KEY}" in txt and "# mis claves" in txt and environ["OPENROUTER_API_KEY"] == KEY
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


def test_sacar_la_clave_la_borra_del_archivo_y_de_la_ia(api):
    c, rt, _, env_file, environ = api
    put(c, {"OPENROUTER_API_KEY": KEY})
    r = put(c, clear=["OPENROUTER_API_KEY"])
    assert not next(f for f in r.json()["fields"] if f["name"] == "OPENROUTER_API_KEY")["set"]
    assert KEY not in env_file.read_text(encoding="utf-8") and "OPENROUTER_API_KEY" not in environ
    assert rt.models.label("voz") == "sin modelo"


def test_meta_pasa_de_mock_a_real_y_vuelve_sin_reiniciar(api):
    c, rt, meta, _, _ = api
    assert not meta.settings.real and "whatsapp" in rt.connectors
    r = put(c, {"META_MODE": "real", "META_WA_TOKEN": "tok-wa-secreto-9999", "META_WA_PHONE_ID": "123"})
    assert meta.settings.real and meta.outbox.transport is http_post
    assert "tok-wa-secreto-9999" not in r.text
    assert any(i["status"] == "falta" and "META_APP_SECRET" in i["text"] for i in r.json()["checks"])
    put(c, {"META_MODE": "mock"})
    assert not meta.settings.real and meta.outbox.transport is not http_post


def test_valores_malos_se_rechazan_y_no_cambian_nada(api):
    c, _, _, env_file, environ = api
    antes = env_file.read_text(encoding="utf-8")
    for bad in ({"OPENROUTER_API_KEY": "con espacio"}, {"OPENROUTER_API_KEY": "linea\nOTRA=1"}, {"META_MODE": "otro"},
                {"PATH": "x"}, {"META_IG_HOST": "evil.example"}, {"RAPHAEL_PUBLIC_URL": "http://x"}):
        assert put(c, bad).status_code == 400
    assert put(c, {"META_MODE": "real", "OPENROUTER_API_KEY": "con espacio"}).status_code == 400
    assert env_file.read_text(encoding="utf-8") == antes and "META_MODE" not in environ


def test_las_de_tienda_piden_reiniciar(api):
    c, *_ = api
    assert put(c, {"SHOPIFY_TOKEN": "shpat_abcdefghijkl"}).json()["restart_needed"] == ["SHOPIFY_TOKEN"]


def test_cambiar_la_clave_de_la_app_cierra_sesiones_y_borra_la_inicial(api):
    c, _, _, env_file, _ = api
    (env_file.parent / "clave-inicial.txt").write_text("x\n")
    assert c.post("/api/v1/config/clave", json={"key": "corta"}).status_code == 400
    assert c.post("/api/v1/config/clave", json={"key": "otra-clave-larga"}).status_code == 200
    assert c.get("/api/v1/config").status_code == 401
    assert not (env_file.parent / "clave-inicial.txt").exists()
    assert c.post("/api/v1/login", json={"key": "otra-clave-larga", "device": "t"}).status_code == 200


def test_primer_arranque_genera_la_clave_y_se_puede_entrar(tmp_path):
    rt = boot(tmp_path, {})
    app = create_app(rt, tick=False, env_file=tmp_path / "raphael.env")
    assert not app.state.auth.has_key()
    msg = first_key(app, tmp_path)
    k = (tmp_path / "clave-inicial.txt").read_text().strip()
    assert k in msg and app.state.auth.has_key()
    with TestClient(app) as c:
        assert c.post("/api/v1/login", json={"key": k, "device": "t"}).status_code == 200
