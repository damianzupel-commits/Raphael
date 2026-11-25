"""Los adaptadores REALES con un HTTP falso (sin red): los pasos contra Meta y ComfyUI, y que las claves nunca se filtren."""

from __future__ import annotations

import pytest

from raphael_contenido import adapters as ad
from raphael_contenido import entorno
from raphael_contenido.adapters.comfyui import ComfyUI, image_workflow, video_workflow
from raphael_contenido.adapters.http import ServicioError
from raphael_contenido.config import contenido_config
from raphael_contenido.video import edicion as ve
from raphael_contenido.video.runner import SimulatedRunner

TOKEN = "TOKEN-SECRETO-123"


def test_instagram_real_sigue_los_tres_pasos_y_publica(tmp_path):
    calls = []

    def http(method, url, **kw):
        calls.append((method, url.split("?")[0].rsplit("/", 1)[-1]))
        if url.endswith("/media") and method == "POST" and "resumable" in str(kw.get("data")):
            return {"id": "C1", "uri": "https://rupload.example/C1"}
        if "status_code" in url:
            return {"status_code": "FINISHED"}
        if url.endswith("media_publish"):
            return {"id": "M9"}
        return {}
    f = tmp_path / "v.mp4"
    f.write_bytes(b"123")
    ig = ad.InstagramGraph("U1", TOKEN, "v21.0", http=http, sleep=lambda s: None)
    assert ig.publish_reel(f, "hola") == {"media_id": "M9", "simulado": False}
    assert [c[1] for c in calls] == ["media", "C1", "C1", "media_publish"]


def test_instagram_real_nunca_filtra_el_token_en_los_errores(tmp_path):
    def http(method, url, **kw):
        raise ServicioError(f"El servicio respondió 400: bad token {TOKEN}")
    f = tmp_path / "v.mp4"
    f.write_bytes(b"1")
    with pytest.raises(ServicioError) as e:
        ad.InstagramGraph("U1", TOKEN, http=http).publish_reel(f, "x")
    assert TOKEN not in str(e.value) and "***" in str(e.value)


def test_instagram_si_no_termina_de_procesar_no_publica(tmp_path):
    def http(method, url, **kw):
        if "status_code" in url:
            return {"status_code": "ERROR"}
        return {"id": "C", "uri": "https://x"}
    f = tmp_path / "v.mp4"
    f.write_bytes(b"1")
    with pytest.raises(ServicioError, match="no terminó de procesar"):
        ad.InstagramGraph("U", TOKEN, http=http).publish_reel(f, "x")


def test_sin_claves_cada_servicio_avisa_que_falta_y_no_inventa(monkeypatch):
    env: dict = {}
    a = entorno.build(contenido_config({}), env)
    assert a.modos() == {"instagram": "sin_clave", "comfyui": "sin_clave", "metricas": "sin_clave", "anuncios": "sin_clave", "ffmpeg": "real"}
    for fn in (a.metricas.snapshot, a.anuncios.activate):
        with pytest.raises(ServicioError, match="Faltan"):
            fn(1) if fn == a.metricas.snapshot else fn("x")
    assert set(entorno.missing_for_real(env)) == {"instagram y métricas", "anuncios", "imagen y video generados"}


def test_con_claves_en_el_entorno_arma_los_reales_y_mock_fuerza_simulado(tmp_path):
    env = {"IG_USER_ID": "1", "IG_ACCESS_TOKEN": TOKEN, "META_ADS_ACCOUNT_ID": "act_5", "META_ADS_ACCESS_TOKEN": TOKEN,
           "COMFYUI_OUTPUT_DIR": str(tmp_path)}
    assert set(entorno.build(contenido_config({}), env).modos().values()) == {"real"}
    assert set(entorno.build(contenido_config({}), {**env, "CONTENIDO_MODO": "mock"}, mock_dir=tmp_path).modos().values()) == {"mock"}


def test_metricas_reales_toleran_una_metrica_rechazada():
    def http(method, url, **kw):
        if "/insights" in url and "metric=saved" in url:
            raise ServicioError("metric not supported")
        if "/media?" in url:
            return {"data": [{"id": "p1", "like_count": 3, "comments_count": 1, "timestamp": "2026-11-20T10:00:00+0000"}]}
        if "/insights" in url:
            return {"data": [{"values": [{"value": 100}]}]}
        return {"username": "u", "followers_count": 5}
    snap = ad.MetricasGraph("U", TOKEN, http=http).snapshot()
    assert snap["publicaciones"][0]["reach"] == 100 and snap["publicaciones"][0]["saved"] is None
    assert snap["avisos"] and snap["simulado"] is False


def test_anuncios_reales_crean_en_pausa_y_activan():
    sent = []

    def http(method, url, **kw):
        sent.append((url.rsplit("/", 1)[-1], kw["data"].get("status")))
        return {"id": "123"} if url.endswith("campaigns") else {"success": True}
    a = ad.AnunciosMeta("act_5", TOKEN, http=http)
    assert a.create_paused("n", "OUTCOME_AWARENESS")["status"] == "PAUSED"
    assert a.activate("123")["status"] == "ACTIVE"
    assert sent == [("campaigns", "PAUSED"), ("123", "ACTIVE")]


def test_comfyui_real_encola_espera_y_devuelve_la_ruta(tmp_path):
    state = {"n": 0}

    def http(method, url, **kw):
        if url.endswith("system_stats"):
            return {}
        if url.endswith("/prompt"):
            return {"prompt_id": "P"}
        state["n"] += 1
        return {} if state["n"] < 2 else {"P": {"outputs": {"9": {"images": [{"filename": "a.png", "subfolder": ""}]}}}}
    c = ComfyUI("http://127.0.0.1:8188", tmp_path, http=http, sleep=lambda s: None)
    assert c.image("a dress", 500, 500)["path"] == str(tmp_path / "a.png")
    assert image_workflow("x", 500, 500, 1)["6"]["inputs"]["width"] == 496
    assert video_workflow("x", 1, 1)["11"]["inputs"]["length"] == 17


def test_comfyui_apagado_avisa(tmp_path):
    def http(method, url, **kw):
        raise ServicioError("no hay nadie")
    with pytest.raises(ServicioError, match="no está prendido"):
        ComfyUI("http://127.0.0.1:8188", tmp_path, http=http).image("x")


def test_ffmpeg_simulado_no_pisa_y_responde_lecturas(tmp_path):
    ve.configure(base=tmp_path, runner=SimulatedRunner({"a.mp4": {"duracion_s": 42.0}}))
    ve.asegurar_carpetas()
    (ve.entrada_dir() / "a.mp4").write_bytes(b"x")
    assert ve.info(ve.entrada_dir() / "a.mp4")["duracion_s"] == 42.0
    r1 = ve.recortar("a.mp4", 0, 5)
    r2 = ve.recortar("a.mp4", 0, 5)
    assert r1["path"] != r2["path"] and r1["original_intacto"]
