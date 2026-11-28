"""Captura de campo: notas, voz, fotos, cierre, resumen del día, búsqueda y expediente. Todo en archivos de la PC."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raphael_personal_api import boot, campo
from raphael_personal_api.app import create_app

ROOT = Path(__file__).resolve().parents[5]
INSTALACION = ROOT / "2-entrega/c-despliegue/personal/personal.installation.yaml"
CLAVE = "clave-segura-1"
AHORA = datetime(2026, 11, 30, 21, 15, 0)


class Voz:
    kind = "mock"

    def __init__(self, texto="faltó la milanesa y la mesa 4 esperó 40 minutos"):
        self.texto = texto

    async def transcribe(self, data, suffix=".webm"):
        return {"texto": self.texto}


@pytest.fixture
def cam(tmp_path):
    c = campo.Campo(tmp_path, lambda: AHORA)
    c.crear_negocio("Bodegón de Prueba")
    return c


def test_tema_automatico_por_palabras(cam):
    assert campo.elegir_tema("la mesa 3 esperó mucho la comanda") == "salon"
    assert campo.elegir_tema("faltó stock de papas, tiramos vencido") == "cocina"
    assert campo.elegir_tema("diferencia en la caja con mercado pago") == "caja"
    assert campo.elegir_tema("hola") == "otro"


def test_agregar_guarda_en_el_dia_con_tema(cam):
    n = cam.agregar("bodegon-de-prueba", texto="  La mesa 5 esperó para pagar  ")
    assert n["tema"] == "salon" and n["dia"] == "2026-11-30" and n["texto"] == "La mesa 5 esperó para pagar"
    cam.agregar("bodegon-de-prueba", texto="algo", tema="caja")
    assert [x["tema"] for x in cam.notas("bodegon-de-prueba", dia="2026-11-30")] == ["salon", "caja"]


def test_rechaza_lo_invalido(cam):
    for kw in ({"texto": ""}, {"texto": "x", "tema": "inventado"}, {"texto": "x", "fuente": "video"}):
        with pytest.raises(campo.CampoError):
            cam.agregar("bodegon-de-prueba", **kw)
    with pytest.raises(campo.CampoError):
        cam.agregar("../afuera", texto="x")
    with pytest.raises(campo.CampoError):
        cam.agregar("no-existe", texto="x")
    with pytest.raises(campo.CampoError):
        cam.agregar("bodegon-de-prueba", fuente="foto", media=b"x", mime="application/x-sh")
    with pytest.raises(campo.CampoError):
        cam.agregar("bodegon-de-prueba", fuente="foto", media=b"", mime="image/jpeg")


def test_el_nombre_del_archivo_lo_pone_el_codigo(cam, tmp_path):
    n = cam.agregar("bodegon-de-prueba", fuente="foto", media=b"\xff\xd8jpg", mime="image/jpeg", texto="heladera")
    assert n["archivo"].endswith(".jpg") and (tmp_path / "bodegon-de-prueba/media" / n["archivo"]).read_bytes() == b"\xff\xd8jpg"
    p, mime = cam.media("bodegon-de-prueba", n["archivo"])
    assert mime == "image/jpeg"
    for malo in ("../negocio.json", "a/b.jpg", "x.jpg", ""):
        with pytest.raises(campo.CampoError):
            cam.media("bodegon-de-prueba", malo)


def test_buscar_cuenta_por_dia(cam):
    cam.agregar("bodegon-de-prueba", texto="Faltó la milanesa")
    cam.agregar("bodegon-de-prueba", texto="se terminó el stock de papas, faltante")
    cam.agregar("bodegon-de-prueba", texto="todo bien en caja")
    r = cam.buscar("bodegon-de-prueba", "¿cuántas veces faltó stock?")
    assert r["total"] == 1 and r["dias"] == {"2026-11-30": 1}
    assert cam.buscar("bodegon-de-prueba", "faltó")["total"] == 2
    with pytest.raises(campo.CampoError):
        cam.buscar("bodegon-de-prueba", "¿?")


def test_resumen_sin_ia_usa_el_cierre_si_existe(cam):
    cam.agregar("bodegon-de-prueba", texto="la mesa 2 esperó 30 minutos para pedir")
    cam.agregar("bodegon-de-prueba", texto="diferencia de caja de 2000")
    cam.cierre("bodegon-de-prueba", ["Esperas en el pico", "Diferencia de caja", "Pedido a mano al proveedor"])
    r = cam.resumen("bodegon-de-prueba")
    assert r["perdidas"] == ["Esperas en el pico", "Diferencia de caja", "Pedido a mano al proveedor"]
    assert r["origen_perdidas"] == "cierre del día" and r["ia"] is False and r["total"] == 5
    assert "# Resumen del 2026-11-30" in (cam.root / "bodegon-de-prueba/resumenes/2026-11-30.md").read_text("utf-8")


def test_resumen_sin_cierre_ordena_por_palabras_de_perdida(cam):
    cam.agregar("bodegon-de-prueba", texto="hoy hubo mucha gente")
    cam.agregar("bodegon-de-prueba", texto="faltó pescado y tiramos sobrante vencido")
    r = cam.resumen("bodegon-de-prueba")
    assert len(r["perdidas"]) == 1 and "pescado" in r["perdidas"][0] and r["origen_perdidas"].startswith("reglas")


def test_resumen_con_ia_usa_solo_las_notas(cam):
    cam.agregar("bodegon-de-prueba", texto="faltó la milanesa")
    pedido = []

    def ask(msgs):
        pedido.append(msgs)
        return "PÉRDIDAS: 1. faltante de milanesa"

    r = cam.resumen("bodegon-de-prueba", ask=ask)
    assert r["ia"] and "milanesa" in r["texto_ia"] and "faltó la milanesa" in pedido[0][1]["content"]
    assert "no lo inventes" in pedido[0][0]["content"]
    assert cam.resumen("bodegon-de-prueba", ask=lambda m: None)["ia"] is False   # el modelo no respondió: cae a reglas


def test_expediente_agrupa_por_tema(cam):
    cam.agregar("bodegon-de-prueba", texto="mesa 1 espera", tema="salon")
    cam.agregar("bodegon-de-prueba", texto="stock bajo", tema="cocina")
    md = cam.expediente("bodegon-de-prueba")
    assert md.startswith("# Expediente: Bodegón de Prueba") and "## Salón y comandas (1)" in md and "stock bajo" in md


def test_actualizar_cambia_texto_y_tema(cam):
    n = cam.agregar("bodegon-de-prueba", texto="algo")
    m = cam.actualizar("bodegon-de-prueba", n["id"], texto="mesa 9", tema="salon")
    assert m["texto"] == "mesa 9" and m["tema_elegido"] and cam.notas("bodegon-de-prueba")[0]["tema"] == "salon"
    with pytest.raises(campo.CampoError):
        cam.actualizar("bodegon-de-prueba", "20260101-000000-abcd", texto="x")


# --- la API --------------------------------------------------------------------------------------------------------------
@pytest.fixture
def api(tmp_path):
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=boot.dev_dirs_default(), environ={}, installed=False)
    env_file = tmp_path / "raphael.env"
    env_file.write_text("#\n", encoding="utf-8")
    voz = Voz()
    app = create_app(rt, report=report, tick=False, env_file=env_file, environ={}, speech=voz)
    app.state.auth.set_key(CLAVE)
    with TestClient(app) as c:
        tok = c.post("/api/v1/login", json={"key": CLAVE, "device": "t"}).json()["token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        c.post("/api/v1/campo/negocios", json={"nombre": "Bodegón"}).raise_for_status()
        yield c, voz, tmp_path


def test_la_api_pide_sesion(tmp_path):
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={}, installed=False)
    app = create_app(rt, report=report, tick=False, env_file=tmp_path / "raphael.env", environ={})
    with TestClient(app) as c:
        assert c.get("/api/v1/campo").status_code == 401


def test_flujo_completo_por_la_api(api):
    c, voz, tmp = api
    assert [n["id"] for n in c.get("/api/v1/campo").json()["negocios"]] == ["bodegon"]
    assert c.post("/api/v1/campo/nota", json={"negocio": "bodegon", "texto": "mesa 3 esperó"}).json()["tema"] == "salon"
    v = c.post("/api/v1/campo/voz?negocio=bodegon", content=b"RIFFaudio",
               headers={"Content-Type": "audio/webm;codecs=opus"}).json()
    assert v["estado"] == "ok" and "milanesa" in v["texto"] and v["tema"] in campo.TEMAS and v["archivo"].endswith(".webm")
    f = c.post("/api/v1/campo/foto?negocio=bodegon&tema=cocina&texto=heladera", content=b"\xff\xd8x",
               headers={"Content-Type": "image/jpeg"})
    assert f.json()["fuente"] == "foto"
    assert c.get(f"/api/v1/campo/media/{f.json()['archivo']}?negocio=bodegon").content == b"\xff\xd8x"
    assert c.get("/api/v1/campo/notas?negocio=bodegon&dia=2026-01-01").json()["total"] == 0
    assert c.get("/api/v1/campo/notas?negocio=bodegon&q=milanesa").json()["total"] == 1
    assert c.post("/api/v1/campo/cierre", json={"negocio": "bodegon", "cosas": ["a", "b"]}).status_code == 200
    r = c.get("/api/v1/campo/resumen?negocio=bodegon").json()
    assert r["perdidas"] == ["a", "b"] and r["ia"] is False
    q = c.post("/api/v1/campo/preguntar", json={"negocio": "bodegon", "pregunta": "¿cuántas veces faltó la milanesa?"}).json()
    assert q["coincidencias"] == 1 and q["ia"] is False
    assert "# Expediente: Bodegón" in c.get("/api/v1/campo/expediente?negocio=bodegon").text


def test_audio_sin_voz_queda_a_salvo(tmp_path):
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={}, installed=False)
    app = create_app(rt, report=report, tick=False, env_file=tmp_path / "raphael.env", environ={})
    app.state.auth.set_key(CLAVE)
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + c.post("/api/v1/login", json={"key": CLAVE, "device": "t"}).json()["token"]
        c.post("/api/v1/campo/negocios", json={"nombre": "Bodegón"})
        v = c.post("/api/v1/campo/voz?negocio=bodegon", content=b"audio", headers={"Content-Type": "audio/webm"}).json()
        assert v["estado"] == "sin_transcribir" and "aviso" in v and v["archivo"]
        assert c.get("/api/v1/campo/notas?negocio=bodegon").json()["total"] == 1


def test_errores_claros(api):
    c, _, _ = api
    assert c.post("/api/v1/campo/nota", json={"negocio": "nada", "texto": "x"}).status_code == 422
    assert c.post("/api/v1/campo/foto?negocio=bodegon", content=b"x", headers={"Content-Type": "text/html"}).status_code == 422
    assert c.get("/api/v1/campo/media/..%2Fnegocio.json?negocio=bodegon").status_code in (404, 422)
    assert c.get("/api/v1/campo/notas?negocio=bodegon&dia=ayer").status_code == 422


def test_la_ia_del_resumen_se_pide_siempre_privada(tmp_path):
    rt, report = boot.start(INSTALACION, tmp_path, dev_dirs=[], environ={}, installed=False)
    visto = {}

    def complete(role, msgs, **kw):
        visto.update(kw)
        return "resumen local"

    rt.models.complete = complete
    app = create_app(rt, report=report, tick=False, env_file=tmp_path / "raphael.env", environ={})
    app.state.auth.set_key(CLAVE)
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + c.post("/api/v1/login", json={"key": CLAVE, "device": "t"}).json()["token"]
        c.post("/api/v1/campo/negocios", json={"nombre": "Bodegón"})
        c.post("/api/v1/campo/nota", json={"negocio": "bodegon", "texto": "faltó pescado"})
        r = c.get("/api/v1/campo/resumen?negocio=bodegon&ia=true").json()
    assert r["ia"] and r["texto_ia"] == "resumen local" and visto["private"] is True and visto["prefer"] == "local"


def test_el_material_no_apunta_a_empleados(cam):
    cam.agregar("bodegon-de-prueba", texto="el mozo Juan se equivocó dos comandas y faltó la milanesa", tema="personal")
    cam.agregar("bodegon-de-prueba", texto="faltó la milanesa y esperaron 30 minutos", tema="cocina")
    r = cam.resumen("bodegon-de-prueba")
    assert all("Juan" not in p for p in r["perdidas"]) and len(r["perdidas"]) == 1
    assert any("Juan" in x for x in r["solo_para_damian"])
    assert "Juan" not in (cam.root / "bodegon-de-prueba/resumenes/2026-11-30.md").read_text("utf-8")
    assert "Juan" in cam.expediente("bodegon-de-prueba") and "Juan" not in cam.expediente("bodegon-de-prueba", para_dueno=True)
    pedido = []
    cam.resumen("bodegon-de-prueba", ask=lambda m: pedido.append(m))
    assert "no nombres ni señales a empleados" in pedido[0][0]["content"]
