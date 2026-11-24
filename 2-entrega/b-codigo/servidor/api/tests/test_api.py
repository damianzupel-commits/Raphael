"""La API de la app sobre la instalación real (harness v2 + orquestador `secretary` + brigada Empresas)."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from
from raphael_core.testing import Clock
from raphael_empresas.sample import MINIMAL

from raphael_empresas_api.app import create_app

BRIGADE = Path(__file__).resolve().parents[5] / "1-harness" / "c-brigadas" / "15-empresas" / "b-codigo"
ORCH = "raphael_orchestrator.orchestrator:RaphaelOrchestrator"


def runtime(connectors=None):
    cfg = {**MINIMAL, "orders": {**MINIMAL["orders"], "required_steps": ["prenda", "nombre"]}}
    inst = installation_from({"id": "t", "edition": "cloud", "identity": {"user": "Ana"},
                              "brigades": {"empresas": {"config": cfg}},
                              "orchestrator": {"entry": ORCH, "config": {"mode": "secretary", "routing": {
                                  "fallback_cook": "empresas/atencion", "classifier": False}}}})
    rt = Runtime(inst, clock=Clock(datetime(2026, 11, 18, 9, 0)), connectors=connectors)
    rep = rt.run(Loader(rt, [BRIGADE], installed=False).apply())
    assert not rep["errors"]
    return rt


@pytest.fixture
def api():
    rt = runtime()
    app = create_app(rt, tick=False)
    app.state.auth.set_key("clave-segura")
    with TestClient(app) as c:
        tok = c.post("/api/v1/login", json={"key": "clave-segura", "device": "test"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c, rt


def client_says(rt, text, who="549341", name=""):
    return rt.run(rt.receive("whatsapp", who, text, name))


def test_salud_sin_sesion_y_todo_lo_demas_pide_sesion():
    rt = runtime()
    with TestClient(create_app(rt, tick=False)) as c:
        h = c.get("/api/v1/health").json()
        assert h["ok"] and h["api"] == 1 and h["ready"] is False
        assert c.post("/api/v1/login", json={"key": "x"}).status_code == 409        # todavía no hay clave
        for path in ("/api/v1/summary", "/api/v1/pending", "/api/v1/orders"):
            assert c.get(path).status_code == 401
        assert c.get("/api/v1/pending", headers={"Authorization": "Bearer inventado"}).status_code == 401


def test_clave_incorrecta_y_bloqueo_por_intentos():
    rt = runtime()
    app = create_app(rt, tick=False)
    app.state.auth.set_key("clave-segura")
    with TestClient(app) as c:
        codes = [c.post("/api/v1/login", json={"key": "mala"}).status_code for _ in range(6)]
        assert codes[0] == 401 and codes[-1] == 429
        assert c.post("/api/v1/login", json={"key": "clave-segura"}).status_code == 429   # bloqueada aunque sea la buena
    with pytest.raises(ValueError):
        app.state.auth.set_key("corta")


def test_pendientes_aprobar_con_cambios_validados(api):
    c, rt = api
    client_says(rt, "quiero un vestido a medida")
    client_says(rt, "Lu")
    [p] = c.get("/api/v1/pending").json()["items"]
    assert p["type"] == "enviar_presupuesto" and p["editable"] == ["price"] and p["can"] == ["approve", "reject"]
    assert c.post(f"/api/v1/pending/{p['id']}/approve", json={"changes": {"contact": "otro"}}).status_code == 422
    assert c.post(f"/api/v1/pending/{p['id']}/approve", json={"changes": {"price": "mucho"}}).status_code == 422
    r = c.post(f"/api/v1/pending/{p['id']}/approve", json={"changes": {"price": 210000}}).json()
    assert r["state"] == "executed" and "$ 210.000" in r["text"]
    assert c.get("/api/v1/pending").json()["items"] == []
    assert c.post(f"/api/v1/pending/{p['id']}/approve", json={}).status_code == 404


def test_lo_humano_se_resuelve_con_respuesta_y_no_se_aprueba(api):
    c, rt = api
    client_says(rt, "¿hacen arreglos de ruedos?", "1")
    [p] = c.get("/api/v1/pending").json()["items"]
    assert p["can"] == ["resolve"]
    assert c.post(f"/api/v1/pending/{p['id']}/approve", json={}).status_code == 409
    assert c.post(f"/api/v1/pending/{p['id']}/resolve", json={"reply": "Sí, desde $ 8.000"}).json()["state"] == "resolved"
    assert rt.outgoing("whatsapp:1")[-1]["text"] == "Sí, desde $ 8.000"


def test_rechazar(api):
    c, rt = api
    client_says(rt, "quiero un turno para probarme el jueves a las 17")
    pid = c.get("/api/v1/pending").json()["items"][0]["id"]
    assert c.post(f"/api/v1/pending/{pid}/reject", json={"reason": "ese día no"}).json()["state"] == "rejected"


def test_secretaria_con_confirmacion(api):
    c, rt = api
    client_says(rt, "me llegó roto, quiero hablar con alguien", "9", "Marta")
    r = c.post("/api/v1/secretary", json={"text": "buen día, ¿qué tareas hay?"}).json()
    assert "Buen día, Ana" in r["text"] and r["tasks"][0]["kind"] == "derivar_humano"
    card = c.post("/api/v1/secretary", json={"text": "contame la 1"}).json()["card"]
    assert card["options"][0]["recommended"]
    assert set(r) == {"text", "suggestions", "tasks", "card", "meta"}


def test_encargos_y_cambio_de_estado(api):
    c, rt = api
    client_says(rt, "quiero un vestido a medida")
    client_says(rt, "Lu")
    pid = c.get("/api/v1/pending").json()["items"][0]["id"]
    c.post(f"/api/v1/pending/{pid}/approve", json={})
    [o] = c.get("/api/v1/orders").json()["items"]
    assert o["number"] == 1 and o["status"] == "presupuesto"
    assert c.post("/api/v1/orders/1/status", json={"status": "borrado"}).status_code == 422
    assert c.post("/api/v1/orders/1/status", json={"status": "listo"}).json()["status"] == "listo"
    assert "está listo" in rt.outgoing("whatsapp:549341")[-1]["text"]           # Avisos, automático
    assert c.get("/api/v1/orders/99").status_code == 400


def test_lecturas(api):
    c, rt = api
    assert c.get("/api/v1/appointments").json() == {"items": []}
    assert c.get("/api/v1/deposits").json() == {"waiting": [], "notified": []}
    assert c.get("/api/v1/questions").json() == {"items": []}
    assert c.get("/api/v1/catalog").json()["state"]["configured"] is False
    assert c.get("/api/v1/summary").json()["business"] == "Taller Ejemplo"
    client_says(rt, "hola", "1")
    assert len(c.get("/api/v1/conversation/whatsapp:1").json()["items"]) == 2
    assert c.get("/api/v1/conversation/..%2Fetc").status_code in (404, 422)
    assert c.get("/api/v1/updates").json()["pending"] == 0


def test_cerrar_sesion(api):
    c, _ = api
    assert c.post("/api/v1/logout").json() == {"ok": True}
    assert c.get("/api/v1/summary").status_code == 401


def test_avisos_y_marcar_vistos(api):
    c, rt = api
    rt.notify("Prueba de aviso", kind="prueba")
    u = c.get("/api/v1/updates").json()
    assert u["notices_unseen"] == 1 and u["notice_last"] == "Prueba de aviso"
    items = c.get("/api/v1/notices").json()
    assert items["unseen"] == 1 and items["items"][0]["kind"] == "prueba" and not items["items"][0]["seen"]
    assert c.post("/api/v1/notices/seen").json() == {"unseen": 0}
    assert c.get("/api/v1/updates").json()["notices_unseen"] == 0
    assert c.get("/api/v1/notices").json()["items"][0]["seen"]
