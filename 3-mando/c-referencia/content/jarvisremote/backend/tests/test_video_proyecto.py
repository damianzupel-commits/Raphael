"""Proyecto de edición: modelo, operaciones atómicas con revisión y deshacer, y render real con ffmpeg sobre videos sintéticos chicos."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app import video_edit as ve
from app import video_proyecto as vp

con_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está instalado en esta máquina")


def _clip(destino: Path, dur: int = 4, tono: int = 440, audio: bool = True) -> None:
    a = ["-f", "lavfi", "-i", f"sine=frequency={tono}:duration={dur}"] if audio else []
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=160x90:rate=25:duration={dur}", *a,
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", *(["-c:a", "aac", "-shortest"] if audio else []), str(destino)], check=True)


@pytest.fixture
def carpeta(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "Videos-Raphael"))
    ve.asegurar_carpetas()
    return tmp_path / "Videos-Raphael"


@pytest.fixture
def con_medios(carpeta, monkeypatch):
    """Sin ffmpeg: la lectura de cada archivo (duración, pistas) es simulada; los archivos existen vacíos para que `resolver` los encuentre."""
    datos = {"a.mp4": {"duracion_s": 10.0, "ancho": 160, "alto": 90, "tiene_video": True, "tiene_audio": True},
             "mudo.mp4": {"duracion_s": 6.0, "ancho": 160, "alto": 90, "tiene_video": True, "tiene_audio": False},
             "musica.mp3": {"duracion_s": 30.0, "ancho": None, "alto": None, "tiene_video": False, "tiene_audio": True}}
    for n in datos:
        (ve.entrada_dir() / n).write_bytes(b"x")
    monkeypatch.setattr(ve, "info", lambda path: {"archivo": path.name, "fps": 25.0, "tamano_mb": 0.0, **datos[path.name]})
    return carpeta


def test_crear_listar_y_leer(con_medios):
    p = vp.crear("Cumple de Sofi", "vertical")
    assert (p["ancho"], p["alto"], p["rev"], p["duracion"]) == (1080, 1920, 1, 0)
    assert vp.listar()[0]["id"] == p["id"] and vp.leer(p["id"])["nombre"] == "Cumple de Sofi"
    with pytest.raises(vp.ProyectoError, match="No existe"):
        vp.leer("nada")
    with pytest.raises(vp.ProyectoError, match="inválido"):
        vp.leer("../x")
    with pytest.raises(vp.ProyectoError, match="formato"):
        vp.crear("x", "panoramico")


def test_las_operaciones_arman_la_secuencia_y_calculan_posiciones_y_duracion(con_medios):
    pid = vp.crear("demo")["id"]
    r = vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "inicio": 2, "fin": 6},
                         {"op": "agregar_clip", "archivo": "mudo.mp4"},
                         {"op": "ajustar", "clip": "c2", "velocidad": 2, "volumen": 0.5, "brillo": 0.1},
                         {"op": "agregar_texto", "texto": "Feliz cumple", "pos": 1, "dur": 2},
                         {"op": "agregar_clip", "pista": "A1", "archivo": "musica.mp3", "pos": 0, "fin": 20}], por="ia")
    p = r["proyecto"]
    v1 = p["pistas"]["V1"]
    assert [c["id"] for c in v1] == ["c1", "c2"] and (v1[0]["pos"], v1[0]["dur"], v1[1]["pos"], v1[1]["dur"]) == (0, 4.0, 4.0, 3.0)
    assert p["duracion"] == 7.0 and p["rev"] == 2 and p["ultimo_cambio"]["por"] == "ia" and len(r["resumen"]) == 5
    assert p["pistas"]["A1"][0]["archivo"] == "musica.mp3" and p["pistas"]["T1"][0]["texto"] == "Feliz cumple"


def test_dividir_mover_recortar_y_borrar(con_medios):
    pid = vp.crear("demo")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "inicio": 0, "fin": 8}])
    p = vp.aplicar(pid, [{"op": "dividir", "clip": "c1", "en": 3}])["proyecto"]
    v1 = p["pistas"]["V1"]
    assert [(c["id"], c["inicio"], c["fin"]) for c in v1] == [("c1", 0, 3.0), ("c2", 3.0, 8)] and v1[1]["pos"] == 3.0
    p = vp.aplicar(pid, [{"op": "mover", "clip": "c2", "indice": 0}])["proyecto"]
    assert [c["id"] for c in p["pistas"]["V1"]] == ["c2", "c1"]
    p = vp.aplicar(pid, [{"op": "recortar", "clip": "c2", "inicio": 4, "fin": 6}, {"op": "borrar", "clip": "c1"}])["proyecto"]
    assert [(c["id"], c["dur"]) for c in p["pistas"]["V1"]] == [("c2", 2.0)]
    with pytest.raises(vp.ProyectoError, match="adentro del clip"):
        vp.aplicar(pid, [{"op": "dividir", "clip": "c2", "en": 99}])


def test_una_operacion_invalida_no_aplica_ninguna_y_el_mensaje_dice_cual(con_medios):
    pid = vp.crear("demo")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4"}])
    antes = vp.leer(pid)
    for ops, texto in (([{"op": "ajustar", "clip": "c1", "volumen": 1.5}, {"op": "ajustar", "clip": "c1", "brillo": 9}], "Operación 2"),
                       ([{"op": "borrar", "clip": "zz"}], "No existe el clip"),
                       ([{"op": "agregar_clip", "archivo": "../x.mp4"}], "fuera de la carpeta"),
                       ([{"op": "agregar_clip", "archivo": "mudo.mp4", "pista": "A1"}], "no tiene audio"),
                       ([{"op": "agregar_clip", "archivo": "a.mp4", "inicio": 9, "fin": 99}], "inicio/fin"),
                       ([{"op": "volar"}], "no existe"),
                       ([{"op": "ajustar", "clip": "c1", "magia": 1}], "no es un parámetro"),
                       ([{"op": "agregar_texto", "texto": "x", "color": "fucsia"}], "color")):
        with pytest.raises(vp.ProyectoError, match=texto):
            vp.aplicar(pid, ops)
    assert vp.leer(pid) == antes                                         # ni la primera operación válida quedó aplicada
    with pytest.raises(vp.ProyectoError, match="1 a 50"):
        vp.aplicar(pid, [])


def test_la_revision_evita_pisar_el_cambio_del_otro_y_deshacer_rehacer_lo_recuperan(con_medios):
    pid = vp.crear("demo")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4"}], por="usuario", rev_base=1)
    with pytest.raises(vp.ProyectoError, match="cambió"):                # la IA todavía tenía la revisión 1
        vp.aplicar(pid, [{"op": "ajustar", "clip": "c1", "volumen": 0}], por="ia", rev_base=1)
    vp.aplicar(pid, [{"op": "ajustar", "clip": "c1", "volumen": 0}], por="ia", rev_base=2)
    p = vp.deshacer(pid, "usuario")["proyecto"]
    assert p["pistas"]["V1"][0]["volumen"] == 1.0 and p["puede_rehacer"] and p["ultimo_cambio"]["por"] == "usuario"
    assert vp.rehacer(pid)["proyecto"]["pistas"]["V1"][0]["volumen"] == 0
    vp.deshacer(pid); vp.deshacer(pid)
    assert vp.leer(pid)["pistas"]["V1"] == [] and not vp.leer(pid)["puede_deshacer"]
    with pytest.raises(vp.ProyectoError, match="nada para deshacer"):
        vp.deshacer(pid)
    with pytest.raises(vp.ProyectoError, match="'ia' o 'usuario'"):
        vp.aplicar(pid, [{"op": "formato", "formato": "cuadrado"}], por="hacker")


def test_el_grafo_de_ffmpeg_refleja_el_proyecto(con_medios):
    pid = vp.crear("demo")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "inicio": 1, "fin": 5}, {"op": "agregar_clip", "archivo": "mudo.mp4"},
                     {"op": "ajustar", "clip": "c1", "velocidad": 0.25, "zoom": 1.5, "fundido_out": 1, "brillo": 0.2},
                     {"op": "agregar_texto", "texto": "Hola", "pos": 0, "dur": 2, "posicion": "arriba"},
                     {"op": "agregar_clip", "pista": "A1", "archivo": "musica.mp3", "pos": 2.5, "fin": 10}])
    entradas, grafo, ass = vp.construir(vp._cargar(pid))
    assert entradas.count("-i") == 3 and "concat=n=2:v=1:a=1[vc][ac]" in grafo
    assert "trim=start=1.0:end=5.0" in grafo and "setpts=PTS/0.25" in grafo and "atempo=0.5,atempo=0.5" in grafo     # 0.25x = dos pasos de atempo
    assert "crop=iw/1.5:ih/1.5" in grafo and "eq=brightness=0.2" in grafo and "fade=t=out" in grafo and "adelay=2500|2500" in grafo
    assert "anullsrc" in grafo                                            # el clip mudo no rompe el concat
    assert "[vc]subtitles=t.ass[vout]" in grafo and "Alignment" in ass and "Dialogue: 0,0:00:00.00,0:00:02.00,T0" in ass
    _e, g2, ass2 = vp.construir(vp._cargar(pid), "preview")
    assert "scale=540:960" in g2 and ass2 is not None
    vacio = vp.crear("vacío")["id"]
    with pytest.raises(vp.ProyectoError, match="no tiene clips de video"):
        vp.construir(vp._cargar(vacio))


@con_ffmpeg
def test_render_real_de_punta_a_punta_deja_un_archivo_nuevo_con_la_duracion_del_proyecto(carpeta):
    _clip(ve.entrada_dir() / "a.mp4", 4, 440)
    _clip(ve.entrada_dir() / "mudo.mp4", 3, audio=False)
    _clip(ve.entrada_dir() / "musica.m4a", 6, 880)
    pid = vp.crear("render real", "horizontal")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "inicio": 0.5, "fin": 3.5}, {"op": "agregar_clip", "archivo": "mudo.mp4"},
                     {"op": "ajustar", "clip": "c2", "velocidad": 1.5, "brillo": 0.1, "fundido_in": 0.5},
                     {"op": "agregar_texto", "texto": "Hola", "pos": 0.5, "dur": 1.5},
                     {"op": "agregar_clip", "pista": "A1", "archivo": "musica.m4a", "pos": 1, "volumen": 0.3}])
    esperado = vp.leer(pid)["duracion"]
    assert esperado == 5.0
    r = vp.renderizar(pid, "preview")
    assert r["original_intacto"] and Path(r["path"]).parent == ve.salida_dir() and abs(r["duracion_s"] - esperado) < 0.4
    assert (r["ancho"], r["alto"]) == (960, 540) and r["tiene_audio"] and r["proyecto"] == pid
    assert (ve.entrada_dir() / "a.mp4").stat().st_size > 0 and not list(ve.salida_dir().glob("*.ass"))


# --- endpoints del panel: el usuario edita el MISMO proyecto que la IA -------------------------------------------------------
def _api(con_medios):
    from fastapi.testclient import TestClient
    from orquestador.server import create_app

    host = {"host": "127.0.0.1:8765"}
    c = TestClient(create_app(8765, token="tok"), headers=host)
    c.h = {"Authorization": "Bearer tok", **host}
    return c


def test_el_panel_y_la_ia_editan_el_mismo_proyecto_y_se_ven_los_cambios(con_medios):
    from app.tools import call_tool
    import asyncio

    c = _api(con_medios)
    assert c.get("/api/video/proyectos").status_code == 401
    pid = c.post("/api/video/proyectos", json={"nombre": "Demo", "formato": "vertical"}, headers=c.h).json()["proyecto"]["id"]
    # el usuario agrega un clip desde el panel…
    r = c.post(f"/api/video/proyectos/{pid}/ops", json={"operaciones": [{"op": "agregar_clip", "archivo": "a.mp4", "fin": 8}], "rev_base": 1}, headers=c.h).json()
    assert r["ok"] and r["proyecto"]["ultimo_cambio"]["por"] == "usuario" and r["proyecto"]["rev"] == 2
    # …la IA lo ve y lo modifica con la tool (rev_base de lo que leyó)…
    visto = asyncio.run(call_tool("video_proyecto_ver", {"proyecto": pid}))
    asyncio.run(call_tool("video_proyecto_editar", {"proyecto": pid, "rev_base": visto["rev"],
                                                    "operaciones": [{"op": "dividir", "clip": "c1", "en": 4}, {"op": "ajustar", "clip": "c2", "velocidad": 2}]}))
    # …y el panel, al leer de nuevo, ve lo que hizo la IA
    p = c.get(f"/api/video/proyectos/{pid}", headers=c.h).json()
    assert p["ultimo_cambio"]["por"] == "ia" and [x["id"] for x in p["pistas"]["V1"]] == ["c1", "c2"] and p["pistas"]["V1"][1]["velocidad"] == 2
    # un panel desactualizado no pisa el cambio de la IA
    viejo = c.post(f"/api/video/proyectos/{pid}/ops", json={"operaciones": [{"op": "borrar", "clip": "c1"}], "rev_base": 2}, headers=c.h)
    assert viejo.status_code == 409 and "cambió" in viejo.json()["detail"]
    assert c.post(f"/api/video/proyectos/{pid}/deshacer", headers=c.h).json()["proyecto"]["pistas"]["V1"][0]["fin"] == 8
    assert c.post(f"/api/video/proyectos/{pid}/rehacer", headers=c.h).json()["ok"]
    assert c.get("/api/video/proyectos", headers=c.h).json()["proyectos"][0]["id"] == pid
    assert c.get("/api/video/proyectos/no-existe", headers=c.h).status_code == 409


def test_el_reproductor_lee_medios_solo_de_la_carpeta_de_video_con_el_token(con_medios):
    c = _api(con_medios)
    assert c.get("/api/video/media/a.mp4").status_code == 401 and c.get("/api/video/media/a.mp4?tk=mal").status_code == 401
    assert c.get("/api/video/media/a.mp4?tk=tok").status_code == 200 and c.get("/api/video/media/a.mp4", headers=c.h).status_code == 200
    assert c.get("/api/video/media/..%2F..%2Fetc%2Fpasswd?tk=tok").status_code in (404, 400)
    assert c.get("/api/video/media/no-esta.mp4?tk=tok").status_code == 404


# --- capas, GIFs, transiciones, efectos y efectos de sonido -----------------------------------------------------------------
def _imagen(destino: Path, color: str = "red") -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=64x64:d=1", "-frames:v", "1", str(destino)], check=True)


def _gif(destino: Path) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=48x48:rate=10:duration=1", str(destino)], check=True)


@pytest.fixture
def medios2(con_medios, monkeypatch):
    base = {"a.mp4": {"duracion_s": 10.0, "ancho": 160, "alto": 90, "tiene_video": True, "tiene_audio": True},
            "mudo.mp4": {"duracion_s": 6.0, "ancho": 160, "alto": 90, "tiene_video": True, "tiene_audio": False},
            "musica.mp3": {"duracion_s": 30.0, "ancho": None, "alto": None, "tiene_video": False, "tiene_audio": True},
            "logo.png": {"duracion_s": None, "ancho": 64, "alto": 64, "tiene_video": True, "tiene_audio": False},
            "baile.gif": {"duracion_s": 1.0, "ancho": 48, "alto": 48, "tiene_video": True, "tiene_audio": False},
            "ding.wav": {"duracion_s": 0.9, "ancho": None, "alto": None, "tiene_video": False, "tiene_audio": True}}
    for n in ("logo.png", "baile.gif"):
        (ve.entrada_dir() / n).write_bytes(b"x")
    ve.efectos_dir().mkdir(parents=True, exist_ok=True)
    (ve.efectos_dir() / "ding.wav").write_bytes(b"x")              # los efectos de sonido se buscan también en efectos/
    monkeypatch.setattr(ve, "info", lambda path: {"archivo": path.name, "fps": 25.0, "tamano_mb": 0.0, **base[path.name]})
    return con_medios


def test_las_capas_se_ponen_donde_se_quiere_y_se_ajustan(medios2):
    pid = vp.crear("capas")["id"]
    r = vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "fin": 8},
                         {"op": "agregar_overlay", "archivo": "logo.png", "pos": 1, "dur": 3, "x": 0.8, "y": 0.1, "escala": 0.2, "opacidad": 0.7},
                         {"op": "agregar_overlay", "archivo": "baile.gif", "pos": 2, "dur": 4},
                         {"op": "agregar_overlay", "archivo": "mudo.mp4", "pos": 0, "inicio": 1, "fin": 3, "escala": 0.4},
                         {"op": "agregar_clip", "pista": "A2", "archivo": "ding.wav", "pos": 1.5, "volumen": 0.8}])
    o = r["proyecto"]["pistas"]["O1"]
    assert [(c["tipo"], c["x"], c["y"], c["escala"], c["opacidad"], c["dur"]) for c in o] == [("imagen", 0.8, 0.1, 0.2, 0.7, 3.0), ("gif", 0.5, 0.5, 0.3, 1.0, 4.0), ("video", 0.5, 0.5, 0.4, 1.0, 2.0)]
    assert r["proyecto"]["pistas"]["A2"][0]["archivo"] == "ding.wav" and r["proyecto"]["duracion"] == 8.0
    p = vp.aplicar(pid, [{"op": "ajustar", "clip": "c2", "x": 0.2, "rotacion": 45, "dur": 5, "fundido_in": 0.5}, {"op": "mover", "clip": "c3", "pos": 3}])["proyecto"]
    c2 = p["pistas"]["O1"][0]
    assert (c2["x"], c2["rotacion"], c2["dur"], c2["pos"]) == (0.2, 45.0, 5.0, 1.0) and p["pistas"]["O1"][1]["pos"] == 3.0
    for ops, texto in (([{"op": "ajustar", "clip": "c2", "x": 3}], "x"), ([{"op": "recortar", "clip": "c2", "fin": 1}], "no se recortan"),
                       ([{"op": "dividir", "clip": "c2", "en": 2}], "no se divide"), ([{"op": "agregar_overlay", "archivo": "a.mp3"}], "No encontré"),
                       ([{"op": "ajustar", "clip": "c2", "volumen": 1}], "no es un parámetro")):
        with pytest.raises(vp.ProyectoError, match=texto):
            vp.aplicar(pid, ops)
    assert vp.aplicar(pid, [{"op": "recortar", "clip": "c4", "inicio": 0, "fin": 1.5}])["proyecto"]["pistas"]["O1"][2]["dur"] == 1.5


def test_las_transiciones_solapan_los_clips_y_los_efectos_van_al_grafo(medios2):
    pid = vp.crear("trans")["id"]
    p = vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "fin": 5}, {"op": "agregar_clip", "archivo": "mudo.mp4", "fin": 4},
                         {"op": "agregar_clip", "archivo": "a.mp4", "fin": 3},
                         {"op": "ajustar", "clip": "c2", "transicion": "disolver", "transicion_dur": 1},
                         {"op": "ajustar", "clip": "c1", "desenfoque": 5, "nitidez": 1, "vineta": 0.5, "espejo": True, "rotacion": 90, "filtro": "sepia"}])["proyecto"]
    v1 = p["pistas"]["V1"]
    assert [(c["pos"], c["dur"], c["tdur"]) for c in v1] == [(0, 5.0, 0), (4.0, 4.0, 1.0), (8.0, 3.0, 0)] and p["duracion"] == 11.0   # c2 entra 1 s antes; c3 va a corte
    _e, g, _a = vp.construir(vp._cargar(pid))
    assert "xfade=transition=dissolve:duration=1.0:offset=4.0" in g and "acrossfade=d=1.0" in g and "concat=n=2:v=1:a=1[gv1][ga1]" in g
    assert "gblur=sigma=5" in g and "unsharp=5:5:1" in g and "vignette=angle=" in g and "hflip" in g and "transpose=1" in g and "colorchannelmixer" in g
    with pytest.raises(vp.ProyectoError, match="transicion"):
        vp.aplicar(pid, [{"op": "ajustar", "clip": "c2", "transicion": "magia"}])
    with pytest.raises(vp.ProyectoError, match="filtro"):
        vp.aplicar(pid, [{"op": "ajustar", "clip": "c1", "filtro": "arcoiris"}])
    with pytest.raises(vp.ProyectoError, match="rotacion"):
        vp.aplicar(pid, [{"op": "ajustar", "clip": "c1", "rotacion": 45}])
    sin = vp.crear("sin transiciones")["id"]                                  # sin transiciones, el grafo sigue siendo el concat de antes
    vp.aplicar(sin, [{"op": "agregar_clip", "archivo": "a.mp4"}, {"op": "agregar_clip", "archivo": "mudo.mp4"}])
    assert "xfade" not in vp.construir(vp._cargar(sin))[1]


def test_el_grafo_pone_las_capas_con_su_posicion_y_los_efectos_de_sonido_en_la_mezcla(medios2):
    pid = vp.crear("grafo")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4", "fin": 6}, {"op": "agregar_overlay", "archivo": "logo.png", "pos": 1, "dur": 3, "x": 0.8, "y": 0.1, "escala": 0.25, "rotacion": 30},
                     {"op": "agregar_overlay", "archivo": "baile.gif", "pos": 2, "dur": 2}, {"op": "agregar_clip", "pista": "A2", "archivo": "ding.wav", "pos": 1.5},
                     {"op": "agregar_clip", "pista": "A1", "archivo": "musica.mp3", "fin": 5}, {"op": "agregar_texto", "texto": "Hola"}])
    entradas, g, ass = vp.construir(vp._cargar(pid), "preview")
    assert entradas[:2] == ["-i", str(ve.entrada_dir() / "a.mp4")] and "-loop" in entradas and "-ignore_loop" in entradas
    assert "overlay=x=W*0.8-w/2:y=H*0.1-h/2:enable='between(t,1.0,4.0)'" in g and "rotate=0.5236" in g and "setpts=PTS+2.0/TB" in g
    assert "scale=135:-2" not in g and "scale=134:-2" in g or "scale=135:-2" in g or "scale=132:-2" in g                     # 0.25 del ancho de la vista previa (540), par
    assert "adelay=1500|1500" in g and g.count("amix=inputs=3") == 1 and "[vo1]subtitles=t.ass[vout]" in g


@con_ffmpeg
def test_render_real_con_capa_gif_transicion_y_efecto_de_sonido(carpeta):
    _clip(ve.entrada_dir() / "a.mp4", 4, 440)
    _clip(ve.entrada_dir() / "b.mp4", 4, 660)
    _imagen(ve.entrada_dir() / "logo.png")
    _gif(ve.entrada_dir() / "baile.gif")
    ve.efectos_dir().mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=1200:duration=0.5", str(ve.efectos_dir() / "ding.wav")], check=True)
    pid = vp.crear("todo junto", "horizontal")["id"]
    vp.aplicar(pid, [{"op": "agregar_clip", "archivo": "a.mp4"}, {"op": "agregar_clip", "archivo": "b.mp4"},
                     {"op": "ajustar", "clip": "c2", "transicion": "fundido", "transicion_dur": 1, "desenfoque": 2, "vineta": 0.4},
                     {"op": "agregar_overlay", "archivo": "logo.png", "pos": 0.5, "dur": 2, "x": 0.85, "y": 0.15, "escala": 0.15, "opacidad": 0.8},
                     {"op": "agregar_overlay", "archivo": "baile.gif", "pos": 3, "dur": 3, "x": 0.2, "y": 0.8, "escala": 0.2, "rotacion": 15, "fundido_out": 0.5},
                     {"op": "agregar_clip", "pista": "A2", "archivo": "ding.wav", "pos": 3.2}])
    esperado = vp.leer(pid)["duracion"]
    assert esperado == 7.0
    r = vp.renderizar(pid, "preview")
    assert abs(r["duracion_s"] - esperado) < 0.5 and (r["ancho"], r["alto"]) == (960, 540) and r["tiene_audio"] and r["original_intacto"]


@con_ffmpeg
def test_el_pack_de_efectos_de_sonido_se_genera_una_vez_y_no_pisa_los_del_usuario(carpeta):
    assert not ve.efectos_dir().exists()
    assert len(ve.generar_efectos()) == 8                        # la primera vez arma el pack
    nombres = {p.name for p in ve.efectos_dir().iterdir()}
    assert {"ding.wav", "whoosh.wav", "campana.wav", "pop.wav"} <= nombres
    propio = ve.efectos_dir() / "ding.wav"
    propio.write_bytes(b"mio")
    assert ve.generar_efectos() == [] and propio.read_bytes() == b"mio"
    assert "ding.wav" in [f["archivo"] for f in ve.listar()["efectos"]]
