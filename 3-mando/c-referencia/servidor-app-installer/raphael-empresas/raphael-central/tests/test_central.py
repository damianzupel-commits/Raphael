from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from raphael_central.app import Base, crear_app

ADMIN = {"Authorization": "Bearer " + "x" * 20}


@pytest.fixture
def todo(tmp_path):
    reloj = [datetime(2026, 11, 18, 10)]
    base = Base(str(tmp_path / "c.sqlite"), reloj=lambda: reloj[0])
    return TestClient(crear_app(base, admin_token="x" * 20)), reloj


def test_admin_protegido_y_token_minimo(todo, tmp_path):
    c, _ = todo
    assert c.get("/admin/licencias").status_code == 401
    with pytest.raises(RuntimeError):
        crear_app(Base(str(tmp_path / "y.sqlite")), admin_token="corto")


def test_licencia_se_ata_a_la_primera_instalacion(todo):
    c, _ = todo
    lic = c.post("/admin/licencias", json={"cliente": "Taller", "plan": "pro", "vence": "2027-01-01"}, headers=ADMIN).json()
    assert lic["clave"].startswith("RAPH-")
    ok = c.post("/api/licencias/validar", json={"clave": lic["clave"], "instalacion": "A"}).json()
    assert ok == {"valida": True, "plan": "pro", "vence": "2027-01-01", "cliente": "Taller"}
    otra = c.post("/api/licencias/validar", json={"clave": lic["clave"], "instalacion": "B"}).json()
    assert otra["valida"] is False and "otra instalación" in otra["motivo"]
    c.post(f"/admin/licencias/{lic['clave']}", json={"liberar_instalacion": True}, headers=ADMIN)
    assert c.post("/api/licencias/validar", json={"clave": lic["clave"], "instalacion": "B"}).json()["valida"]


def test_suspender_vencer_e_inexistente(todo):
    c, reloj = todo
    clave = c.post("/admin/licencias", json={"cliente": "T", "vence": "2026-12-01"}, headers=ADMIN).json()["clave"]
    c.post(f"/admin/licencias/{clave}", json={"activa": False}, headers=ADMIN)
    assert c.post("/api/licencias/validar", json={"clave": clave, "instalacion": "A"}).json()["motivo"] == "licencia suspendida"
    c.post(f"/admin/licencias/{clave}", json={"activa": True}, headers=ADMIN)
    reloj[0] = datetime(2026, 12, 5)
    assert c.post("/api/licencias/validar", json={"clave": clave, "instalacion": "A"}).json()["motivo"] == "licencia vencida"
    assert c.post("/api/licencias/validar", json={"clave": "RAPH-NO", "instalacion": "A"}).json()["valida"] is False
    assert c.post("/admin/licencias", json={"cliente": "X", "plan": "gratis"}, headers=ADMIN).status_code == 400


def test_latidos_y_alertas(todo):
    c, reloj = todo
    clave = c.post("/admin/licencias", json={"cliente": "Taller", "plan": "basico"}, headers=ADMIN).json()["clave"]
    [x] = c.get("/admin/instalaciones", headers=ADMIN).json()
    assert x["alertas"] == ["sin instalar"]
    c.post("/api/licencias/validar", json={"clave": clave, "instalacion": "A"})
    assert c.post("/api/latido", json={"clave": clave, "instalacion": "B", "estado": {}}).status_code == 403
    estado = {"servidor": "0.1.0", "brigadas": {"atencion": "0.1.0"}, "uso": {"mensajes": 3100, "limite_mensajes": 3000,
              "excedido": True, "costo_usd": 1.5}, "envios_fallidos": 2, "avisos": [], "pendientes": 4}
    assert c.post("/api/latido", json={"clave": clave, "instalacion": "A", "estado": estado}).json() == {"ok": True}
    [x] = c.get("/admin/instalaciones", headers=ADMIN).json()
    assert x["version"] == "0.1.0" and x["alertas"] == ["2 envíos fallidos", "pasó el tope de mensajes del plan"]
    reloj[0] += timedelta(hours=2)
    assert "sin latido hace más de 1 hora" in c.get("/admin/instalaciones", headers=ADMIN).json()[0]["alertas"]


def test_panel_html(todo):
    c, _ = todo
    assert "Raphael · soporte" in c.get("/admin").text
