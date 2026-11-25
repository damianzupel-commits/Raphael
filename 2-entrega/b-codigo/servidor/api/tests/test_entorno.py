"""Claves y chequeo de arranque: se leen del archivo, nunca se muestran y el sistema degrada sin ellas."""

import asyncio
from pathlib import Path

from raphael_empresas.boot import start

from raphael_empresas_api.entorno import check, exit_code, load_env, parse_env, render
from raphael_empresas_api.meta import MetaSettings, settings_from_env

INSTALACION = Path(__file__).resolve().parents[4] / "c-despliegue" / "instalacion-clienta" / "clienta.installation.yaml"
KEY = "sk-or-v1-clave-secreta-de-prueba"
ORCH_DEV = Path(__file__).resolve().parents[5] / "1-harness" / "c-brigadas"


def boot(tmp_path, env):
    dev = [ORCH_DEV / "15-empresas" / "b-codigo", ORCH_DEV / "00-orquestador" / "b-codigo"]
    return start(INSTALACION, tmp_path, dev_dirs=dev, installed=False, env=env)[0]


def test_parse_env_acepta_windows_comillas_y_comentarios():
    txt = ("\ufeff# comentario\r\nOPENROUTER_API_KEY = \"sk-or-1\" \r\nexport META_MODE=real  # al final\r\n"
           "VACIA=\r\nraro línea\r\nA=b#c\r\n")
    assert parse_env(txt) == {"OPENROUTER_API_KEY": "sk-or-1", "META_MODE": "real", "VACIA": "", "A": "b#c"}


def test_load_env_no_pisa_el_entorno_y_lee_los_tres_archivos(tmp_path):
    (tmp_path / "raphael.env").write_text("OPENROUTER_API_KEY=del-archivo\nMETA_MODE=real\n", encoding="utf-8")
    (tmp_path / "meta.env").write_text("META_VERIFY_TOKEN=tok\n", encoding="utf-8")
    environ = {"OPENROUTER_API_KEY": "del-sistema"}
    assert load_env(tmp_path, environ=environ) == ["raphael.env", "meta.env"]
    assert environ == {"OPENROUTER_API_KEY": "del-sistema", "META_MODE": "real", "META_VERIFY_TOKEN": "tok"}


def test_sin_claves_arranca_en_reglas_y_dice_que_falta(tmp_path):
    rt = boot(tmp_path, {})
    items = check(env={}, installation=rt.installation, models=rt.models, meta=settings_from_env({}), app_key_set=True)
    por_area = {(i.area, i.status) for i in items}
    assert ("IA", "aviso") in por_area and ("Meta", "aviso") in por_area and ("Perfil", "aviso") in por_area
    assert exit_code(items) == 0            # puede arrancar
    assert exit_code(items, real=True) == 2  # pero no está listo para clientes reales
    assert "Arranca" in render(items)


def test_sin_clave_de_la_app_no_frena_el_arranque(tmp_path):
    """La clave de la app se genera sola en el primer arranque: no es un faltante."""
    rt = boot(tmp_path, {})
    items = check(env={}, installation=rt.installation, models=rt.models, meta=MetaSettings(), app_key_set=False)
    assert [i.status for i in items if i.area == "App"] == ["info"]
    assert exit_code(items) == 0


def test_meta_real_incompleta_falta_y_nunca_muestra_valores(tmp_path):
    env = {"OPENROUTER_API_KEY": KEY, "META_MODE": "real", "META_WA_TOKEN": "token-wa-secreto"}
    rt = boot(tmp_path, env)
    items = check(env=env, installation=rt.installation, models=rt.models, meta=settings_from_env(env), app_key_set=True)
    out = render(items)
    assert "falta META_APP_SECRET" in out and "falta META_VERIFY_TOKEN" in out
    assert KEY not in out and "token-wa-secreto" not in out
    assert exit_code(items) == 2


def test_todo_cargado_queda_listo(tmp_path):
    env = {"OPENROUTER_API_KEY": KEY, "META_MODE": "real", "META_VERIFY_TOKEN": "v", "META_APP_SECRET": "s",
           "META_WA_TOKEN": "t", "META_WA_PHONE_ID": "123"}
    rt = boot(tmp_path, env)
    items = check(env=env, installation=rt.installation, models=rt.models, meta=settings_from_env(env), app_key_set=True,
                  public_url="https://pc.ts.net")
    out = render(items)
    assert "https://pc.ts.net/webhook/meta" in out
    assert not [i for i in items if i.status == "falta"]
    assert [i.status for i in items if i.area == "IA"] == ["ok"]


def test_con_la_clave_la_voz_usa_openrouter_y_solo_ahi(tmp_path):
    """Con OPENROUTER_API_KEY, un pedido libre de la dueña sale por OpenRouter (data_collection=deny); sin clave no sale nada."""
    rt = boot(tmp_path, {"OPENROUTER_API_KEY": KEY})
    llamadas = []

    def falso(url, body, headers):
        llamadas.append((url, headers.get("Authorization"), body.get("provider")))
        return {"choices": [{"message": {"content": "Esta semana viene tranquila, Ana."}}], "usage": {}}

    rt.models._transport = falso
    r = asyncio.run(rt.talk_to_owner("che, contame cómo viene la semana y si me conviene tomar más pedidos o frenar"))
    assert "tranquila" in r.text
    assert llamadas == [("https://openrouter.ai/api/v1/chat/completions", f"Bearer {KEY}", {"data_collection": "deny"})]

    sin = boot(tmp_path / "otra", {})
    sin.models._transport = falso
    r2 = asyncio.run(sin.talk_to_owner("che, contame cómo viene la semana y si me conviene tomar más pedidos o frenar"))
    assert len(llamadas) == 1 and r2.text
