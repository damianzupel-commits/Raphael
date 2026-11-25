import ast
import io
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from raphael_cuentas import __main__ as cli
from raphael_cuentas import catalogo, entorno, lienzo, plantilla
from raphael_cuentas.adaptadores import AdaptadorReal, AdaptadorSimulado

AQUI = Path(__file__).resolve().parents[1]
SECRETO = "sk-or-SECRETO-NO-DEBE-SALIR-1234"


def test_catalogo_ids_unicos_y_datos_completos():
    ids = [c.id for c in catalogo.CUENTAS]
    assert len(ids) == len(set(ids))
    for c in catalogo.CUENTAS:
        assert c.donde_se_saca and c.donde_se_pega and c.que_se_prueba and c.para_que, c.id


def test_catalogo_no_tiene_valores_de_claves():
    for v in catalogo.todas_las_vars():
        if v.secreta:
            assert v.defecto == ""


def test_plantilla_commiteada_al_dia_y_sin_valores_secretos():
    assert (AQUI / "cuentas.env.plantilla").read_text(encoding="utf-8") == plantilla.generar() + "\n"
    for line in plantilla.generar().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            var = next(x for x in catalogo.todas_las_vars() if x.nombre == k)
            assert not var.secreta or v == ""


def test_lista_de_lienzo_al_dia():
    assert (AQUI / "ENTRADAS-LIENZO.md").read_text(encoding="utf-8") == lienzo.generar() + "\n"


def test_cubre_las_variables_de_la_plantilla_del_servidor():
    srv = AQUI.parent / "raphael.env.plantilla"
    if not srv.is_file():
        pytest.skip("sin plantilla del servidor")
    usadas = {k for k in entorno.parse_env(srv.read_text(encoding="utf-8").replace("# NVIDIA", "NVIDIA"))}
    propias = {v.nombre for v in catalogo.todas_las_vars()}
    assert usadas <= propias, usadas - propias


def test_estados_falta_parcial_lista():
    c = catalogo.cuenta("meta_whatsapp")
    assert entorno.estado_de(c, {}).estado == "falta"
    assert entorno.estado_de(c, {"META_WA_TOKEN": "tok-largo-1234"}).estado == "parcial"
    assert entorno.estado_de(c, {"META_WA_TOKEN": "tok-largo-1234", "META_WA_PHONE_ID": "1"}).estado == "lista"
    assert entorno.estado_de(c, {"META_WA_TOKEN": "<pegar>", "META_WA_PHONE_ID": ""}).estado == "falta"


def test_formatos():
    assert entorno.estado_de(catalogo.cuenta("transferencia"), {"TRANSFER_TITULAR": "A", "TRANSFER_CBU_CVU": "123"}).problemas
    ok = {"TRANSFER_TITULAR": "A", "TRANSFER_CBU_CVU": "1" * 22}
    assert entorno.estado_de(catalogo.cuenta("transferencia"), ok).estado == "lista"
    assert entorno.estado_de(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": "abc12345"}).problemas
    assert entorno.estado_de(catalogo.cuenta("tailscale"), {"RAPHAEL_PUBLIC_URL": "http://x.ts.net/"}).problemas
    assert entorno.estado_de(catalogo.cuenta("meta_webhook"), {"META_VERIFY_TOKEN": "a", "META_APP_SECRET": "b",
                                                                 "META_MODE": "prod"}).problemas


def test_cargar_archivo_y_entorno_gana(tmp_path):
    f = tmp_path / "raphael.env"
    f.write_text("# c\nOPENROUTER_API_KEY='del-archivo-1234'\nNVIDIA_API_KEY=nv-1234567\nOTRA=1\n", encoding="utf-8")
    env = entorno.cargar([f], environ={"OPENROUTER_API_KEY": "del-sistema-9999", "PATH": "/x"})
    assert env["OPENROUTER_API_KEY"] == "del-sistema-9999" and env["NVIDIA_API_KEY"] == "nv-1234567"
    assert "PATH" not in env


def test_chequeo_no_muestra_secretos_completos():
    env = {"OPENROUTER_API_KEY": SECRETO}
    texto = entorno.render(entorno.chequear(env), env)
    assert SECRETO not in texto and "1234" in texto


def test_codigo_de_salida():
    assert entorno.codigo_salida(entorno.chequear({})) == 0
    assert entorno.codigo_salida(entorno.chequear({}), estricto=True) == 2
    assert entorno.codigo_salida(entorno.chequear({"OPENROUTER_API_KEY": "mala-clave-1"})) == 2


def test_simulado_no_usa_red_y_avisa_lo_que_falta():
    s = AdaptadorSimulado()
    assert s.probar(catalogo.cuenta("openrouter"), {}).estado == "omitida"
    assert s.probar(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": SECRETO}).estado == "simulada"
    forzado = AdaptadorSimulado({"hetzner": ("falla", "token vencido")})
    assert forzado.probar(catalogo.cuenta("hetzner"), {}).detalle == "token vencido"


class _Resp:
    def __init__(self, cuerpo=b"{}", status=200):
        self._c, self.status = cuerpo, status

    def read(self, n=-1):
        return self._c

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _abridor(resp=None, exc=None, vistos=None):
    def abrir(req, timeout=None):
        if vistos is not None:
            vistos.append(req)
        if exc:
            raise exc
        return resp
    return abrir


def test_real_hace_un_get_de_solo_lectura_con_bearer():
    vistos = []
    r = AdaptadorReal(_abridor(_Resp(b'{"data": {"limit_remaining": 4.2}}'), vistos=vistos))
    res = r.probar(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": SECRETO})
    assert res.estado == "ok" and "4.2" in res.detalle
    assert len(vistos) == 1 and vistos[0].get_method() == "GET" and vistos[0].full_url.startswith("https://openrouter.ai/")
    assert vistos[0].get_header("Authorization") == f"Bearer {SECRETO}"
    assert SECRETO not in res.detalle


def test_real_no_llama_si_falta_algo_o_formato_malo():
    vistos = []
    r = AdaptadorReal(_abridor(_Resp(), vistos=vistos))
    assert r.probar(catalogo.cuenta("openrouter"), {}).estado == "omitida"
    assert r.probar(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": "mala-clave-1"}).estado == "falla"
    assert vistos == []


@pytest.mark.parametrize("codigo,texto", [(401, "rechazada"), (403, "permisos"), (500, "500")])
def test_real_errores_http_sin_filtrar_clave(codigo, texto):
    exc = urllib.error.HTTPError("https://x", codigo, f"malo {SECRETO}", {}, None)
    res = AdaptadorReal(_abridor(exc=exc)).probar(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": SECRETO})
    assert res.estado == "falla" and texto in res.detalle and SECRETO not in res.detalle


def test_real_sin_conexion_y_modelo_local_apagado():
    exc = urllib.error.URLError(ConnectionRefusedError(f"rechazada {SECRETO}"))
    res = AdaptadorReal(_abridor(exc=exc)).probar(catalogo.cuenta("openrouter"), {"OPENROUTER_API_KEY": SECRETO})
    assert res.estado == "falla" and SECRETO not in res.detalle
    loc = AdaptadorReal(_abridor(exc=urllib.error.URLError("refused"))).probar(catalogo.cuenta("local_llm"), {})
    assert loc.estado == "falla" and "no está prendido" in loc.detalle


def test_local_ollama_y_lmstudio():
    vistos = []
    r = AdaptadorReal(_abridor(_Resp(b'{"models": [{"name": "a"}]}'), vistos=vistos))
    assert "1 modelo" in r.probar(catalogo.cuenta("local_llm"), {}).detalle
    assert vistos[0].full_url == "http://127.0.0.1:11434/api/tags"
    r.probar(catalogo.cuenta("local_llm"), {"LOCAL_LLM_URL": "http://127.0.0.1:1234", "LOCAL_LLM_KIND": "lmstudio"})
    assert vistos[1].full_url == "http://127.0.0.1:1234/v1/models"
    vacio = AdaptadorReal(_abridor(_Resp(b'{"models": []}'))).probar(catalogo.cuenta("local_llm"), {})
    assert "no hay modelos" in vacio.detalle


def test_url_publica_exige_https_y_transferencia_no_sale_a_la_red():
    vistos = []
    r = AdaptadorReal(_abridor(_Resp(), vistos=vistos))
    assert r.probar(catalogo.cuenta("tailscale"), {"RAPHAEL_PUBLIC_URL": "https://pc.ts.net"}).estado == "ok"
    assert vistos[0].full_url == "https://pc.ts.net/api/v1/health"
    t = r.probar(catalogo.cuenta("transferencia"), {"TRANSFER_TITULAR": "A", "TRANSFER_CBU_CVU": "1" * 22})
    assert t.estado == "ok" and len(vistos) == 1


def test_cuentas_sin_prueba_en_vivo_se_omiten():
    r = AdaptadorReal(_abridor(_Resp()))
    env = {"DUCKDNS_TOKEN": "tok-1234567", "DUCKDNS_DOMAIN": "mi-tienda"}
    assert r.probar(catalogo.cuenta("duckdns"), env).estado == "omitida"


def test_cli_chequear_probar_simulado(tmp_path):
    f = tmp_path / "raphael.env"
    f.write_text(f"OPENROUTER_API_KEY={SECRETO}\n", encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert cli.main(["chequear", "--env", str(f)]) == 0
        assert cli.main(["probar", "--simulado", "--env", str(f)]) == 0
    assert "SIMULADA" in buf.getvalue() and SECRETO not in buf.getvalue()
    with redirect_stdout(io.StringIO()):
        assert cli.main(["chequear", "--estricto", "--env", str(tmp_path / "no-existe.env")]) == 2


def test_no_importa_otras_piezas():
    prohibidos = ("raphael_core", "raphael_orchestrator", "raphael_empresas", "raphael_empresas_api")
    for py in (AQUI / "codigo" / "src" / "raphael_cuentas").glob("*.py"):
        for n in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                nombres = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                nombres = [n.module or ""]
            else:
                nombres = []
            assert not any(x.split(".")[0] in prohibidos for x in nombres), py.name
