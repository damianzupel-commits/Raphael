"""Raphael personal cliente-servidor: cerebro mixto (lo privado solo local), API con sesión, aprobaciones y voz."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from raphael_personal_api import boot, campos, cerebro
from raphael_personal_api.app import create_app

ROOT = Path(__file__).resolve().parents[5]
INSTALACION = ROOT / "2-entrega/c-despliegue/personal/personal.installation.yaml"
CLAVE = "clave-segura-1"
NVIDIA = "nvapi-secreta-de-prueba-9876"


def local_arriba(url: str) -> dict:
    return {"data": [{"id": "llama3.1:8b"}]}


def local_caido(url: str) -> dict:
    raise ConnectionError("apagado")


# --- cerebro ----------------------------------------------------------------------------------------------------------
def test_modelos_por_defecto_son_mixtos():
    cfg = cerebro.load(environ={})
    assert cfg.tiers["local"] == ["ollama", "lmstudio"] and cfg.tiers["gratis"] == ["nvidia"]
    assert {"seguridad", "investigacion", "memoria", "operaciones"} <= set(cfg.private)
    assert cfg.paid_cap_usd_month == 0          # el escalón pago no se usa salvo que Damián lo suba


def test_cualquier_rol_se_cambia_por_configuracion():
    cfg = cerebro.load(environ={"RAPHAEL_ROL_MANDO": "local,gratis", "RAPHAEL_PRIVADAS": "trading, legales",
                                "OLLAMA_MODEL": "qwen3:8b"})
    assert cfg.roles["mando"] == ["local", "gratis"] and cfg.providers["ollama"].model == "qwen3:8b"
    assert {"trading", "legales"} <= set(cfg.private)


def test_la_direccion_unica_de_cuentas_y_apis_tambien_vale():
    cfg = cerebro.load(environ={"LOCAL_LLM_URL": "http://127.0.0.1:1234", "LOCAL_LLM_KIND": "lmstudio"})
    assert cfg.providers["lmstudio"].base_url == "http://127.0.0.1:1234/v1"


@pytest.mark.parametrize("env", [{"RAPHAEL_ROL_VOZ": "nube"}, {"OLLAMA_URL": "http://192.168.1.50:11434/v1"},
                                 {"RAPHAEL_PRIVADAS": "Con Espacios"}])
def test_configuracion_que_abriria_lo_privado_a_la_nube_se_rechaza(env):
    with pytest.raises(ValueError):
        cerebro.load(environ=env)


def test_lo_privado_nunca_sale_a_la_nube_aunque_el_local_este_apagado(tmp_path):
    rt, _ = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={"NVIDIA_API_KEY": NVIDIA}, installed=False)
    llamadas = []

    def transporte(url, body, headers):
        llamadas.append(url)
        if "127.0.0.1" in url:
            raise ConnectionError("apagado")
        return {"choices": [{"message": {"content": "respuesta de la nube"}}]}

    rt.models._transport = transporte
    assert rt.models.complete("cocinero", [{"role": "user", "content": "x"}], target="seguridad") is None
    assert llamadas and all("127.0.0.1" in u for u in llamadas)          # ni un pedido salió a NVIDIA
    llamadas.clear()
    assert rt.models.complete("voz", [{"role": "user", "content": "hola"}]) == "respuesta de la nube"   # lo no privado sí
    assert any("nvidia" in u for u in llamadas)


def test_los_ids_privados_cubren_las_brigadas_sensibles_del_repo():
    """Si el manifiesto de Seguridad, Investigación, Memoria u Operaciones trae otro id, hay que sumarlo a `private`."""
    cfg = cerebro.load(environ={})
    for carpeta in ("05-seguridad", "07-investigacion", "09-memoria", "12-operaciones"):
        m = ROOT / "1-harness/c-brigadas" / carpeta / "b-codigo" / "manifest.yaml"
        if m.is_file():
            ident = yaml.safe_load(m.read_text(encoding="utf-8"))["id"]
            assert ident in cfg.private, f"{carpeta} tiene el id '{ident}', que no está en modelos.personal.yaml → private"


def test_aviso_una_sola_vez_cuando_el_local_se_apaga_y_cuando_vuelve():
    avisos = []
    w = cerebro.LocalWatch(lambda t, **d: avisos.append((d["kind"], t)), cerebro.load(environ={}), local_caido)
    w.check()
    w.check()
    assert [k for k, _ in avisos] == ["modelo_local_apagado"] and "nada sensible a la nube" in avisos[0][1]
    w.fetch = local_arriba
    w.check()
    w.check()
    assert [k for k, _ in avisos] == ["modelo_local_apagado", "modelo_local_ok"]


def test_el_modelo_local_prendido_pero_sin_el_modelo_dice_que_hacer():
    cfg = cerebro.load(environ={"OLLAMA_MODEL": "otro:7b"})
    st = cerebro.status(cfg, cerebro.probe_local(cfg, lambda u: {"data": [{"id": "llama3.1:8b"}]} if "11434" in u else
                                                  (_ for _ in ()).throw(ConnectionError())))
    assert not st["local"]["ready"] and any("ollama pull otro:7b" in h for h in st["local"]["hints"])
    assert st["private_mode"] == "reglas"


# --- API --------------------------------------------------------------------------------------------------------------
class FalsaVoz:
    kind = "mock"

    async def status(self, refresh=False):
        return {"kind": "mock", "enabled": True}

    async def transcribe(self, data, suffix=".webm"):
        if not data:
            raise RuntimeError("no llegó audio")
        return {"texto": "hola raphael", "idioma": "es", "suffix": suffix}

    async def speak(self, text):
        return b"RIFF" + text.encode()


class FalsoEnlace:
    """Hace de `raphael_operaciones.adapters.phone.link`: anota lo que el servidor le pasa."""

    def __init__(self):
        self.calls = []

    async def register(self, ws):
        self.calls.append(("register", None))

    async def handle_incoming(self, msg):
        self.calls.append(("incoming", msg))

    async def unregister(self, ws):
        self.calls.append(("unregister", None))


@pytest.fixture
def api(tmp_path):
    environ: dict[str, str] = {}
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=boot.dev_dirs_default(), environ=environ, installed=False)
    env_file = tmp_path / "raphael.env"
    env_file.write_text("# claves\n", encoding="utf-8")
    state = {"fetch": local_caido}
    app = create_app(rt, report=report, tick=False, env_file=env_file, environ=environ, speech=FalsaVoz(),
                     fetch=lambda u: state["fetch"](u), phone_link=(enlace := FalsoEnlace()))
    app.state.enlace = enlace
    app.state.auth.set_key(CLAVE)
    with TestClient(app) as c:
        tok = c.post("/api/v1/login", json={"key": CLAVE, "device": "t"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c, rt, env_file, environ, state, app


def test_sin_sesion_no_se_ve_nada(api):
    c, *_ = api
    c.headers.pop("Authorization")
    h = c.get("/api/v1/health").json()
    assert h["edition"] == "personal" and h["ready"] is True
    for ruta in ("/api/v1/summary", "/api/v1/brain", "/api/v1/pending", "/api/v1/config", "/api/v1/voz"):
        assert c.get(ruta).status_code == 401
    assert c.post("/api/v1/chat", json={"text": "hola"}).status_code == 401
    assert c.get("/").status_code == 200 and "Raphael" in c.get("/").text


def test_el_arranque_tolera_brigadas_que_todavia_no_existen(api):
    c, rt, *_ = api
    s = c.get("/api/v1/summary").json()
    assert rt.orchestrator is not None and not s["errors"].get("_orchestrator")
    ids = {b["id"]: b for b in c.get("/api/v1/brigades").json()["items"]}
    assert ids["seguridad"]["private"] is True and ids["empresas"]["active"] is False


def test_el_cerebro_avisa_si_el_local_esta_apagado(api):
    c, _, _, _, state, _ = api
    d = c.get("/api/v1/brain?refresh=true").json()
    assert d["local"]["ready"] is False and d["private_mode"] == "reglas" and d["local"]["hints"]
    state["fetch"] = local_arriba
    d = c.get("/api/v1/brain?refresh=true").json()
    assert d["local"]["ready"] is True and d["private_mode"] == "local"


def test_hablar_con_raphael_responde_aunque_no_haya_ia(api):
    c, *_ = api
    r = c.post("/api/v1/chat", json={"text": "hola, ¿estás?"})
    assert r.status_code == 200 and isinstance(r.json()["text"], str) and r.json()["text"]


def test_nada_se_aprueba_solo_y_lo_humano_solo_se_resuelve(api):
    c, rt, *_ = api
    assert c.get("/api/v1/pending").json()["items"] == []
    assert c.post("/api/v1/pending/99/approve").status_code == 404
    assert c.post("/api/v1/pending/99/resolve", json={"reply": "ok"}).status_code == 404


def test_poner_una_clave_la_aplica_en_caliente_y_no_vuelve_completa(api):
    c, rt, env_file, environ, *_ = api
    r = c.put("/api/v1/config", json={"set": {"NVIDIA_API_KEY": NVIDIA}, "clear": []})
    assert r.status_code == 200 and NVIDIA not in r.text and NVIDIA not in c.get("/api/v1/config").text
    row = next(f for f in r.json()["fields"] if f["name"] == "NVIDIA_API_KEY")
    assert row["set"] and row["hint"] == "…9876"
    assert f"NVIDIA_API_KEY={NVIDIA}" in env_file.read_text(encoding="utf-8")
    assert rt.models.label("voz").startswith("nvidia")


def test_un_cambio_de_rol_se_aplica_y_uno_invalido_no_guarda_nada(api):
    c, rt, env_file, environ, *_ = api
    assert c.put("/api/v1/config", json={"set": {"RAPHAEL_ROL_MANDO": "local", "RAPHAEL_PRIVADAS": "trading"}}).status_code == 200
    assert rt.models.config.roles["mando"] == ["local"] and "trading" in rt.models.config.private
    antes = env_file.read_text(encoding="utf-8")
    for malo in ({"OLLAMA_URL": "http://10.0.0.5:11434/v1"}, {"RAPHAEL_ROL_VOZ": "nube"}, {"LOCAL_LLM_KIND": "otro"}):
        assert c.put("/api/v1/config", json={"set": malo}).status_code == 400
    assert env_file.read_text(encoding="utf-8") == antes


def test_cambiar_la_clave_cierra_las_sesiones(api):
    c, *_ = api
    assert c.post("/api/v1/config/clave", json={"key": "otra-clave-9"}).status_code == 200
    assert c.get("/api/v1/summary").status_code == 401


def test_voz_transcribe_y_habla_solo_con_sesion(api):
    c, *_ = api
    assert c.get("/api/v1/voz").json()["enabled"] is True
    r = c.post("/api/v1/voz/transcribir", content=b"audio", headers={"Content-Type": "audio/wav"})
    assert r.json()["texto"] == "hola raphael" and r.json()["suffix"] == ".wav"
    assert c.post("/api/v1/voz/transcribir", content=b"").status_code == 422
    h = c.post("/api/v1/voz/hablar", json={"text": "hola"})
    assert h.status_code == 200 and h.content.startswith(b"RIFF") and h.headers["content-type"] == "audio/wav"


def test_sin_voz_instalada_lo_dice_en_vez_de_romper(tmp_path):
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={}, installed=False)
    app = create_app(rt, report=report, tick=False, environ={})
    app.state.auth.set_key(CLAVE)
    with TestClient(app) as c:
        tok = c.post("/api/v1/login", json={"key": CLAVE}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        assert c.get("/api/v1/voz").json()["enabled"] is False
        assert c.post("/api/v1/voz/hablar", json={"text": "hola"}).status_code == 503


def test_el_chequeo_dice_que_falta_sin_mostrar_valores(api):
    c, *_ = api
    c.put("/api/v1/config", json={"set": {"NVIDIA_API_KEY": NVIDIA}})
    checks = c.get("/api/v1/config").json()["checks"]
    assert any(i["area"] == "IA local" and i["status"] == "aviso" for i in checks)
    assert any(i["area"] == "IA nube" and i["status"] == "ok" for i in checks)
    assert NVIDIA not in str(checks)


def test_los_campos_de_cuentas_y_apis_estan_en_la_pantalla():
    nombres = {f.name for f in campos.FIELDS}
    assert {"LOCAL_LLM_URL", "LOCAL_LLM_KIND", "DUCKDNS_TOKEN", "DUCKDNS_DOMAIN", "HCLOUD_TOKEN"} <= nombres


# --- despliegue en Windows ----------------------------------------------------------------------------------------------
DESPLIEGUE = ROOT / "2-entrega/c-despliegue/personal"


def test_la_plantilla_de_claves_solo_trae_variables_que_la_pantalla_conoce():
    from raphael_empresas_api.entorno import parse_env

    valores = parse_env((DESPLIEGUE / "personal.env.plantilla").read_text(encoding="utf-8"))
    assert valores and set(valores) <= {f.name for f in campos.FIELDS}
    assert not any(valores.values())           # la plantilla no trae ninguna clave


def test_los_scripts_de_windows_son_ascii_con_crlf_y_hacen_lo_prometido():
    for f in DESPLIEGUE.glob("*.bat"):
        raw = f.read_bytes()
        assert all(b < 128 for b in raw) and b"\r\n" in raw, f.name
    assert "ONLOGON" in (DESPLIEGUE / "instalar-servicio.bat").read_text()
    ts = (DESPLIEGUE / "celular-tailscale.bat").read_text().lower()
    assert "funnel" not in ts.replace("no usa funnel", "").replace("funnel de raphael empresas", "")
    assert "--https=%raphael_ts_port%" in ts and "8443" in ts and "serve reset" not in ts.replace('nunca hace "serve reset"', "")
    assert "raphael_personal_api" in (DESPLIEGUE / "arrancar-personal.bat").read_text()
    assert "arrancar-personal.bat" in (DESPLIEGUE / "arrancar-oculto.vbs").read_text()


def test_la_instalacion_personal_es_maestra_y_sin_clasificador_en_la_nube():
    inst = yaml.safe_load(INSTALACION.read_text(encoding="utf-8"))
    assert inst["edition"] == "personal" and inst["orchestrator"]["config"]["mode"] == "master"
    assert inst["orchestrator"]["config"]["routing"]["classifier_cloud"] is False
    assert not inst.get("autonomy")            # ningún nivel bajado a mano: manda lo que dice cada manifiesto


def test_un_login_fallido_publica_acceso_fallido_sin_la_clave(api):
    c, rt, *_ = api
    c.headers.pop("Authorization")
    r = c.post("/api/v1/login", json={"key": "clave-equivocada", "device": "celu"})
    assert r.status_code == 401
    ev = [d for e, d in rt.bus.history if e == "acceso.fallido"]
    assert ev and ev[-1]["source"] and "clave-equivocada" not in str(ev)


def test_eventos_y_comandos_para_los_clientes_de_las_brigadas(api):
    c, rt, *_ = api
    rt.bus.publish("pin.agregado", {"lat": -32.9, "lon": -60.6}, source="geo")
    rt.bus.publish("otra.cosa", {}, source="x")
    items = c.get("/api/v1/events?event=pin.agregado").json()["items"]
    assert [i["event"] for i in items] == ["pin.agregado"] and items[0]["data"]["lat"] == -32.9
    sin_brigada = {"brigade": "geolocalizacion", "cook": "mapa", "name": "pines"}
    assert c.post("/api/v1/command", json=sin_brigada).status_code in (400, 404, 422)
    assert c.post("/api/v1/command", json={"brigade": "Mal Id", "cook": "x", "name": "y"}).status_code == 422


# --- celular de Operaciones: emparejamiento y /ws/phone ---------------------------------------------------------------------
def test_emparejar_el_celular_con_un_codigo_de_un_solo_uso(api):
    c, rt, env_file, environ, state, app = api
    environ["RAPHAEL_PUBLIC_URL"] = "https://pc.tail1.ts.net"
    p = c.post("/api/v1/phone/pair").json()
    assert len(p["code"]) == 8 and p["payload"] == f"raphael://pair?host=https://pc.tail1.ts.net&code={p['code']}"
    c.headers.pop("Authorization")
    r = c.post("/api/v1/phone/redeem", json={"code": p["code"].lower(), "device": "celu"})
    assert r.status_code == 200
    tok = r.json()["token"]
    assert c.get("/api/v1/summary", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert c.post("/api/v1/phone/redeem", json={"code": p["code"]}).status_code == 401      # ya se usó


def test_codigo_malo_se_cuenta_se_bloquea_y_avisa_a_seguridad(api):
    c, rt, *_ = api
    c.headers.pop("Authorization")
    estados = [c.post("/api/v1/phone/redeem", json={"code": "ZZZZZZZZ"}).status_code for _ in range(6)]
    assert estados[:5] == [401] * 5 and estados[5] == 429
    assert any(e == "acceso.fallido" and d.get("via") == "emparejamiento" for e, d in rt.bus.history)


def test_pedir_un_codigo_exige_sesion(api):
    c, *_ = api
    c.headers.pop("Authorization")
    assert c.post("/api/v1/phone/pair").status_code == 401


def test_ws_phone_usa_el_enlace_de_operaciones(api):
    c, rt, env_file, environ, state, app = api
    with c.websocket_connect("/ws/phone", headers={"Authorization": c.headers["Authorization"]}) as ws:
        ws.send_text('{"id": "1", "result": 5}')
    calls = app.state.enlace.calls
    assert [k for k, _ in calls] == ["register", "incoming", "unregister"] and calls[1][1] == '{"id": "1", "result": 5}'


def test_ws_phone_acepta_el_token_en_el_primer_mensaje_y_nunca_en_la_direccion(api):
    c, rt, env_file, environ, state, app = api
    tok = c.headers["Authorization"][7:]
    with TestClient(app) as anon, anon.websocket_connect("/ws/phone") as ws:
        ws.send_json({"token": tok})
        ws.send_text("hola")
    assert [k for k, _ in app.state.enlace.calls] == ["register", "incoming", "unregister"]


def test_ws_phone_sin_sesion_se_cierra_sin_tocar_el_enlace_y_avisa(api):
    from starlette.websockets import WebSocketDisconnect

    c, rt, env_file, environ, state, app = api
    tok = c.headers["Authorization"][7:]
    with TestClient(app) as anon:      # un cliente sin la sesión puesta por defecto
        for ruta, headers in ((f"/ws/phone?token={tok}", {}),            # por la dirección no vale
                              ("/ws/phone", {"Authorization": "Bearer falso"})):
            with pytest.raises(WebSocketDisconnect) as e, anon.websocket_connect(ruta, headers=headers) as ws:
                ws.send_json({"token": "falso"})
                ws.receive_text()
            assert e.value.code == 1008
    assert app.state.enlace.calls == []
    assert any(e == "acceso.fallido" and d.get("via") == "ws/phone" for e, d in rt.bus.history)


def test_ws_phone_sin_operaciones_instalada_cierra_con_motivo(tmp_path, monkeypatch):
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr("raphael_personal_api.app.phone_link_default", lambda: None)   # aunque la brigada esté instalada con pip

    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={}, installed=False)
    app = create_app(rt, report=report, tick=False, environ={})
    with TestClient(app) as c, pytest.raises(WebSocketDisconnect) as e, c.websocket_connect("/ws/phone"):
        pass
    assert e.value.code == 1013


def test_los_roles_no_muestran_un_modelo_local_que_no_esta_prendido():
    cfg = cerebro.load(environ={"NVIDIA_API_KEY": NVIDIA})
    from raphael_core.models import ModelGateway, Usage

    class Espacio:
        def get(self, *a):
            return None

        def put(self, *a):
            pass

    ahora = lambda: __import__("datetime").datetime(2026, 11, 25)  # noqa: E731
    gw = ModelGateway(cfg, Usage(Espacio(), 10**6, ahora), env={"NVIDIA_API_KEY": NVIDIA})
    caido = cerebro.probe_local(cfg, local_caido)
    st = cerebro.status(cfg, caido, gw)
    assert st["roles"]["ruteo"]["now"].startswith("nvidia")          # local primero, pero apagado: no se muestra
    assert "ollama" not in str(st["roles"]) and "lmstudio" not in str(st["roles"])
    st = cerebro.status(cfg, cerebro.probe_local(cfg, local_arriba), gw)
    assert st["roles"]["ruteo"]["now"].startswith("ollama")
    sin_nube = ModelGateway(cfg, Usage(Espacio(), 10**6, ahora), env={})
    assert cerebro.status(cfg, caido, sin_nube)["roles"]["mando"]["now"] == "sin modelo (reglas)"


def test_el_codigo_trae_un_qr_si_esta_segno_y_la_pagina_deja_cargar_imagenes_data(api):
    pytest.importorskip("segno")
    c, rt, env_file, environ, *_ = api
    environ["RAPHAEL_PUBLIC_URL"] = "https://pc.tail1.ts.net"
    d = c.post("/api/v1/phone/pair").json()
    assert "<svg" in d["qr_svg"]
    assert "img-src data:" in c.get("/").headers["content-security-policy"]


def test_el_tope_de_gasto_es_cero_salvo_que_se_pida():
    from raphael_personal_api import cerebro

    assert cerebro.load(environ={}).paid_cap_usd_month == 0
    assert cerebro.load(environ={"RAPHAEL_TOPE_PAGO_USD": "5"}).paid_cap_usd_month == 5
    assert cerebro.check_field("RAPHAEL_TOPE_PAGO_USD", "2,5") == "2.5"
    for mal in ("-1", "mucho", "5000"):
        try:
            cerebro.check_field("RAPHAEL_TOPE_PAGO_USD", mal)
        except ValueError:
            continue
        raise AssertionError(mal)


def test_el_deslizador_de_autonomia_llega_al_runtime(tmp_path):
    rt, _ = boot.start(INSTALACION, tmp_path / "a", dev_dirs=[], environ={}, installed=False)
    assert rt.installation.profile == "equilibrado"                      # sin variable: el de siempre
    rt, _ = boot.start(INSTALACION, tmp_path / "b", dev_dirs=[], environ={"RAPHAEL_AUTONOMIA": "cauteloso"}, installed=False)
    assert rt.installation.profile == "cauteloso"
    with pytest.raises(ValueError, match="no existe"):
        boot.start(INSTALACION, tmp_path / "c", dev_dirs=[], environ={"RAPHAEL_AUTONOMIA": "temerario"}, installed=False)


def test_el_panel_del_celular_trae_brigadas_tareas_efimeros_y_herramientas(api):
    c, rt, *_ = api
    d = c.get("/api/v1/panel").json()
    assert set(d) >= {"contract", "edition", "down", "brigades", "tasks", "ephemerals", "tools"}
    assert d["edition"] == "personal"
    assert all({"id", "name", "mounted", "private", "cooks"} <= set(b) for b in d["brigades"])
    assert [b for b in d["brigades"] if b["mounted"]], "con las brigadas del repo montadas"
    assert all({"name", "owner", "level", "enabled"} <= set(t) for t in d["tools"])
    c.headers.pop("Authorization")
    assert c.get("/api/v1/panel").status_code == 401
