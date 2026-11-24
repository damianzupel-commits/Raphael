"""Brigada de VIDEO: carpeta fija, original intacto, operaciones de edición, spec, ruteo y validación. Sin red ni modelos.
Los tests que editan de verdad usan ffmpeg sobre un video sintético chico; sin ffmpeg en la máquina, se saltean."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import video_edit as v
from brigades import registry, tool_catalog
from brigades import video as vid
from brigades.video_scene import ROUTING, VALIDATION
from orquestador import routing, slim_tools

_hay_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está instalado en esta máquina")


def con_ffmpeg(test):
    """ffmpeg real: se saltea si no está y tiene más margen que el timeout global de 15 s (pytest.ini).
    En Windows estos tests pasaron los 15 s (ffmpeg corre con pocos hilos y prioridad baja a propósito)
    y pytest-timeout corta TODO el proceso, no solo el test."""
    return pytest.mark.timeout(120)(_hay_ffmpeg(test))


def _sintetico(destino: Path, dur: int = 8, fuente: str = "testsrc", tono: int = 440, silencio: bool = True) -> None:
    af = ["-af", "volume='if(between(t,3,5.5),0,1)':eval=frame"] if silencio else []
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"{fuente}=size=320x180:rate=25:duration={dur}", "-f", "lavfi", "-i",
                    f"sine=frequency={tono}:duration={dur}", *af, "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(destino)], check=True)


@pytest.fixture(scope="module")
def semilla(tmp_path_factory):
    d = tmp_path_factory.mktemp("semilla")
    _sintetico(d / "prueba.mp4")
    _sintetico(d / "dos.mp4", dur=5, fuente="testsrc2", tono=600, silencio=False)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=100x50:d=1", "-frames:v", "1", str(d / "logo.png")], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=3", str(d / "musica.mp3")], check=True)
    return d


@pytest.fixture
def carpeta(monkeypatch, tmp_path, semilla):
    base = tmp_path / "Videos-Raphael"
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(base))
    v.asegurar_carpetas()
    for f in semilla.iterdir():
        shutil.copyfile(f, v.entrada_dir() / f.name)
    return base


def _huella(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --- carpeta fija y original intacto --------------------------------------------------------------------------------------
def test_la_carpeta_por_defecto_esta_en_documentos_y_se_cambia_por_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VIDEO_EDIT_DIR", raising=False)
    assert v.base_dir() == Path.home() / "Documents" / "Videos-Raphael"
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "x"))
    assert v.entrada_dir() == tmp_path / "x" / "entrada" and v.salida_dir() == tmp_path / "x" / "salida"


@pytest.mark.parametrize("ruta", ["../afuera.mp4", "../../etc/passwd", "/etc/hostname", "entrada/../../afuera.mp4", "", "   ", "noexiste.mp4"])
def test_no_se_lee_nada_fuera_de_la_carpeta(monkeypatch, tmp_path, ruta):
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "base"))
    (tmp_path / "afuera.mp4").write_bytes(b"x")
    with pytest.raises(v.VideoError):
        v.resolver(ruta)


def test_un_enlace_que_apunta_afuera_tambien_se_rechaza(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "base"))
    v.asegurar_carpetas()
    (tmp_path / "secreto.mp4").write_bytes(b"x")
    try:
        (v.entrada_dir() / "trampa.mp4").symlink_to(tmp_path / "secreto.mp4")
    except OSError:
        pytest.skip("este sistema no permite crear enlaces simbólicos")
    with pytest.raises(v.VideoError, match="fuera de la carpeta"):
        v.resolver("trampa.mp4")


def test_la_salida_siempre_es_un_nombre_nuevo_y_saneado(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "base"))
    a = v.nueva_salida("mi video; rm -rf ~.mp4", "recorte 1/2", "MP4")
    assert a.parent == v.salida_dir() and a.name == "mi-video-rm-rf-recorte-1-2.mp4"
    a.write_bytes(b"x")
    b = v.nueva_salida("mi video; rm -rf ~.mp4", "recorte 1/2", "mp4")
    assert b != a and b.name.endswith("-2.mp4")


def test_segundos_acepta_los_formatos_de_tiempo_y_rechaza_el_resto():
    assert [v.segundos(x) for x in (90, "90", "1:30", "01:02:03.5", "0:05", 2.5)] == [90.0, 90.0, 90.0, 3723.5, 5.0, 2.5]
    for malo in ("abc", "-3", "1:2:3:4", True, None, "999999"):
        with pytest.raises(v.VideoError):
            v.segundos(malo)


def test_ffmpeg_se_invoca_sin_shell_sin_sobrescribir_y_con_tope(monkeypatch):
    visto = {}

    def run(cmd, **kw):
        visto.update(cmd=cmd, kw=kw)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(v, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(v.subprocess, "run", run)
    v._ffmpeg(["-i", "a; rm -rf ~", "b.mp4"])
    assert isinstance(visto["cmd"], list) and visto["cmd"][1:4] == ["-hide_banner", "-nostdin", "-n"] and "a; rm -rf ~" in visto["cmd"]
    assert "shell" not in visto["kw"] and visto["kw"]["timeout"] > 0
    monkeypatch.setenv("VIDEO_FFMPEG_THREADS", "2")
    assert v._hilos() == 2 and "-threads" in v._codificar()


def test_sin_ffmpeg_el_error_dice_como_instalarlo(monkeypatch):
    monkeypatch.delenv("VIDEO_FFMPEG_PATH", raising=False)
    monkeypatch.setattr(v.shutil, "which", lambda _x: None)
    monkeypatch.setitem(__import__("sys").modules, "imageio_ffmpeg", None)
    with pytest.raises(v.VideoError, match="ffmpeg no está instalado"):
        v.ffmpeg_exe()


# --- operaciones reales ---------------------------------------------------------------------------------------------------
@con_ffmpeg
def test_recortar_unir_y_transicion_dejan_archivos_nuevos_y_el_original_no_cambia(carpeta):
    original = v.entrada_dir() / "prueba.mp4"
    antes = _huella(original)
    a = v.recortar("prueba.mp4", "0:01", 4, True)
    b = v.recortar("dos.mp4", 1, 4, True)
    assert abs(a["duracion_s"] - 3) < 0.3 and Path(a["path"]).parent == v.salida_dir() and a["original_intacto"] is True
    u = v.unir([a["archivo"], b["archivo"]])
    assert abs(u["duracion_s"] - 6) < 0.5
    t = v.transicion([a["archivo"], b["archivo"]], "slideleft", 1)
    assert abs(t["duracion_s"] - 5) < 0.5 and t["transicion"] == "slideleft"
    rapido = v.recortar("prueba.mp4", 2, 5)  # sin recodificar
    assert "sin recodificar" in rapido["modo"]
    assert _huella(original) == antes and sorted(p.name for p in v.entrada_dir().iterdir()) == ["dos.mp4", "logo.png", "musica.mp3", "prueba.mp4"]
    for malo in (lambda: v.recortar("prueba.mp4", 5, 2), lambda: v.recortar("prueba.mp4", 99, 100), lambda: v.unir(["prueba.mp4"]),
                 lambda: v.transicion(["prueba.mp4", "dos.mp4"], "explosion"), lambda: v.transicion(["prueba.mp4", "dos.mp4"], "fade", 9)):
        with pytest.raises(v.VideoError):
            malo()


@con_ffmpeg
def test_silencios_audio_velocidad_y_conversion(carpeta):
    s = v.quitar_silencios("prueba.mp4")
    assert 5 < s["duracion_s"] < 6.8 and s["segundos_quitados"] > 1.5
    assert v.quitar_silencios("dos.mp4").get("sin_cambios") is True  # sin silencios: no genera nada
    au = v.audio("prueba.mp4", True, True, "musica.mp3", 0.2)
    assert au["tiene_audio"] and (au["ancho"], au["alto"]) == (320, 180) and abs(au["duracion_s"] - 8) < 0.3
    assert abs(v.velocidad("dos.mp4", 2)["duracion_s"] - 2.5) < 0.4 and abs(v.velocidad("dos.mp4", 0.5)["duracion_s"] - 10) < 0.6
    mp3 = v.convertir("dos.mp4", "mp3")
    assert mp3["archivo"].endswith(".mp3") and mp3["tiene_video"] is False
    assert v.convertir("dos.mp4", "mp4", 144)["alto"] == 144
    for malo in (lambda: v.velocidad("dos.mp4", 9), lambda: v.velocidad("dos.mp4", 1), lambda: v.convertir("dos.mp4", "exe"),
                 lambda: v.audio("dos.mp4", False, False), lambda: v.audio("dos.mp4", True, False, "../x.mp3")):
        with pytest.raises(v.VideoError):
            malo()


@con_ffmpeg
def test_imagen_texto_capas_vertical_y_extras(carpeta):
    assert (v.vertical("prueba.mp4", 1, 3)["ancho"], v.vertical("prueba.mp4", 1, 3)["alto"]) == (1080, 1920)
    t = v.texto("dos.mp4", "Título {\\b1}con ñ\ny salto", "arriba", 1, 3, 40, "amarillo")
    assert abs(t["duracion_s"] - 5) < 0.3
    assert v.superponer("dos.mp4", "logo.png", "abajo_derecha", 0.2, 0.7)["ancho"] == 320
    assert abs(v.superponer("prueba.mp4", "dos.mp4", "arriba_izquierda", 0.3, 1.0, 1, 4)["duracion_s"] - 8) < 0.3
    assert v.color("dos.mp4", 0.1, 1.2, 1.3, "sepia")["archivo"] == "dos-color-sepia.mp4"
    assert (v.rotar("dos.mp4", "90")["ancho"], v.encuadrar("dos.mp4", 25, 25, 50, 50)["ancho"]) == (180, 160)
    assert abs(v.fundidos("dos.mp4", 1, 1)["duracion_s"] - 5) < 0.3
    assert v.gif("dos.mp4", 1, 2)["archivo"].endswith(".gif") and v.captura("dos.mp4", 2)["archivo"].endswith(".jpg")
    assert abs(v.reversa("dos.mp4")["duracion_s"] - 5) < 0.3
    union = v.unir(["prueba.mp4", "dos.mp4"])
    assert any(abs(c - 8) < 0.3 for c in v.escenas(union["archivo"])["cambios_de_escena"])
    for malo in (lambda: v.texto("dos.mp4", " "), lambda: v.texto("dos.mp4", "x", "costado"), lambda: v.superponer("dos.mp4", "logo.png", "luna"),
                 lambda: v.color("dos.mp4"), lambda: v.rotar("dos.mp4", "45"), lambda: v.encuadrar("dos.mp4", 80, 0, 50, 50),
                 lambda: v.gif("dos.mp4", 0, 40), lambda: v.vertical("prueba.mp4", 0, 400), lambda: v.fundidos("dos.mp4", 3, 3)):
        with pytest.raises(v.VideoError):
            malo()


@con_ffmpeg
def test_transcribir_y_subtitular_con_un_whisper_simulado(carpeta, monkeypatch):
    monkeypatch.setattr(v, "_whisper", lambda wav, idioma: [{"inicio": 0.5, "fin": 2.0, "texto": "Hola, esto es una prueba."},
                                                            {"inicio": 5.6, "fin": 7.5, "texto": "Segunda frase."}])
    t = v.transcribir("prueba.mp4")
    srt = Path(t["path"]).read_text(encoding="utf-8")
    assert t["segmentos"] == 2 and "00:00:00,500 --> 00:00:02,000" in srt and "Segunda frase." in srt and t["momentos"][1]["inicio"] == 5.6
    assert "quemados" in v.subtitular("prueba.mp4", t["archivo"])["modo"] and "pista" in v.subtitular("prueba.mp4", t["archivo"], False)["modo"]
    monkeypatch.setattr(v, "_whisper", lambda wav, idioma: [])
    with pytest.raises(v.VideoError, match="No se detectó voz"):
        v.transcribir("prueba.mp4")
    with pytest.raises(v.VideoError):
        v.transcribir("prueba.mp4", "español")


# --- tools, catálogo y arranque liviano -------------------------------------------------------------------------------------
def test_las_tools_estan_registradas_corren_en_un_hilo_y_el_orquestador_liviano_las_carga():
    from app import tools

    nombres = {n for n in tools.get_tools() if n.startswith("video_")}
    assert len(nombres) == 30 and vid.SPEC.tool_names() == nombres
    assert "app.tools.video_edit" in tools._BLOCKING_MODULES and "video_edit" in slim_tools.KEEP
    assert tool_catalog.classify("video_listar")["nivel"] == "ok" and tool_catalog.classify("video_escenas")["nivel"] == "ok"
    assert tool_catalog.classify("video_recortar")["nivel"] == "sensible"  # un borrador que las pida las muestra marcadas


@con_ffmpeg
def test_una_tool_devuelve_el_archivo_como_artefacto_y_un_error_como_excepcion(carpeta):
    from app.tools import call_tool
    from brigades import contracts

    r = asyncio.run(call_tool("video_recortar", {"archivo": "dos.mp4", "inicio": "1", "fin": "3"}))
    _f, artefactos = contracts.fuentes_de_traza([{"tool": "video_recortar", "args": {}, "ok": True, "result": r}])
    assert [(a.tipo, Path(a.ref).name) for a in artefactos] == [("archivo", r["archivo"])]
    with pytest.raises(v.VideoError, match="fuera de la carpeta"):
        asyncio.run(call_tool("video_recortar", {"archivo": "../x.mp4", "inicio": "0", "fin": "1"}))


# --- spec, ruteo ------------------------------------------------------------------------------------------------------------
def test_el_spec_es_declarativo_con_menor_privilegio_y_ayudante_pasivo_por_defecto():
    spec = registry.get_spec("video")
    assert spec is vid.SPEC and spec.routing.default == "info" and {a.modo for a in spec.ayudantes} == set(vid.TOOLS)
    assert all(t.startswith("video_") for t in spec.tool_names())
    assert vid.TOOLS["info"] == {"video_listar", "video_info", "video_escenas"}  # el pasivo no puede editar
    assert not (vid.TOOLS["sonido"] & {"video_recortar", "video_texto"}) and "video_transcribir" not in vid.TOOLS["montaje"]
    for a in spec.ayudantes:
        cfg = a.config()
        assert cfg.persistent is False and cfg.tool_names == vid.TOOLS[a.modo] and "NUNCA se modifica ni se borra" in cfg.system_prompt
    assert spec.watch.stall_seconds == 900 and spec.helper_timeout() == 3600 and spec.validation is VALIDATION


@pytest.mark.parametrize("modo", list(ROUTING))
def test_las_reglas_proponen_al_ayudante_correcto(modo):
    for pedido in ROUTING[modo]:
        c = vid.ROUTING.coincidencias(pedido)
        assert (c[0] if c else vid.ROUTING.default) == modo, (pedido, c)


def test_el_orquestador_manda_a_video_solo_con_verbo_de_edicion_y_un_video():
    for p in ("Recortá el video charla.mp4 del 1:00 al 2:00", "Subtitulá charla.mp4", "Sacame clips para redes del video de ayer", "Convertí entrevista.mov a mp4",
              "Uní intro.mp4 y cierre.mp4", "hacé un gif del video", "quiero grabar la pantalla de Raphael 30 segundos",
              "armá un video con las fotos del cumple", "publicá el video en instagram"):
        r = asyncio.run(routing.route(p, llm=None))
        assert (r.brigade, r.via) == ("video", "reglas"), p
    assert asyncio.run(routing.route("/video qué tengo", llm=None)).message == "qué tengo"
    assert asyncio.run(routing.route("lo que sea", brigade="video", llm=None)).via == "override"
    for p, esperada in (("Buscá videos de Rust en la web", "investigacion"), ("¿Qué dicen mis notas del video de Midu?", "cerebro"), ("recortá el presupuesto", "cerebro")):
        assert asyncio.run(routing.route(p, llm=None)).brigade == esperada, p
    assert routing.brigadas_conjuntas("Recortá el video y subtitulalo")[0] == ()  # Video no entra al trabajo conjunto (todavía)


# --- la validación de la brigada (pasos directos, en una carpeta temporal) ------------------------------------------------------
def _ctx(timeout: float = 60):
    return SimpleNamespace(scene=VALIDATION.scene, facts=VALIDATION.facts, metrics={}, shared={}, timeout=timeout, spec=vid.SPEC)


def test_validacion_alcance_y_ruteo_pasan_sin_modelo_ni_ffmpeg(monkeypatch, tmp_path):
    from brigades import chief as chief_mod
    from validation import video as val

    monkeypatch.setattr(chief_mod, "_STATE_DIR", tmp_path)
    for paso in (val.step_alcance, val.step_ruteo):
        st = asyncio.run(paso(_ctx()))
        assert st.passed, [t for ok, t in st.checks if not ok]


@con_ffmpeg
def test_validacion_carpeta_y_operaciones_pasan_con_las_tools_reales(monkeypatch, tmp_path):
    from validation import video as val

    monkeypatch.setenv("VIDEO_EDIT_DIR", str(tmp_path / "aislado" / "videos"))
    ctx = _ctx()
    for paso in (val.step_carpeta, val.step_operaciones):
        st = asyncio.run(paso(ctx))
        assert st.passed, [t for ok, t in st.checks if not ok]
    assert ctx.metrics["carpeta"]["rechazos"] == 15 and "transicion" in ctx.metrics["operaciones"]
    assert asyncio.run(val.prereq_ffmpeg(ctx)) == []


def test_sin_ffmpeg_los_pasos_que_lo_necesitan_quedan_sin_validar(monkeypatch):
    from validation import video as val

    def falta():
        raise v.VideoError("ffmpeg no está instalado en esta PC.")

    monkeypatch.setattr(v, "ffmpeg_exe", falta)
    assert asyncio.run(val.prereq_ffmpeg(_ctx())) == ["ffmpeg no está instalado en esta PC."]
    assert {s.id: bool(s.prereq) for s in VALIDATION.steps} == {"alcance": False, "ruteo": False, "carpeta": True, "operaciones": True, "e2e": True}


# --- grabar pantalla y publicaciones de Instagram ---------------------------------------------------------------------------
def test_grabar_pantalla_exige_elegir_que_grabar_respeta_el_tope_y_deja_un_archivo_nuevo_en_entrada(carpeta, monkeypatch):
    monkeypatch.setattr(v.sys, "platform", "linux")
    with pytest.raises(v.VideoError, match="solo funciona en Windows"):
        v.grabar_pantalla(10, ventana="Raphael")
    monkeypatch.setattr(v.sys, "platform", "win32")
    with pytest.raises(v.VideoError, match="Indicá qué grabar"):
        v.grabar_pantalla(10)                                           # ni ventana ni escritorio: no se asume el escritorio
    with pytest.raises(v.VideoError, match="Indicá qué grabar"):
        v.grabar_pantalla(10, ventana="X", escritorio_completo=True)    # ambas cosas es ambiguo
    with pytest.raises(v.VideoError, match="entre 1 y 300"):
        v.grabar_pantalla(9999, ventana="X")
    with pytest.raises(v.VideoError, match="ventana no es válido"):
        v.grabar_pantalla(10, ventana="x\ny")
    llamadas = []

    def falso(args, **kw):
        llamadas.append(args)
        Path(args[-1]).write_bytes(b"video")
        return ""

    monkeypatch.setattr(v, "_ffmpeg", falso)
    monkeypatch.setattr(v, "info", lambda p: {"archivo": p.name, "duracion_s": 10.0})
    r = v.grabar_pantalla(10, "prueba brigada", ventana="Raphael — Orquestador")
    a = llamadas[0]
    assert a[a.index("-i") + 1] == "title=Raphael — Orquestador" and a[a.index("-t") + 1] == "10.0" and "-an" in a
    assert Path(r["path"]).parent == v.entrada_dir() and r["archivo"].startswith("prueba-brigada-") and r["grabado"].startswith("ventana")
    assert v.grabar_pantalla(5, escritorio_completo=True)["grabado"] == "escritorio completo"
    assert llamadas[1][llamadas[1].index("-i") + 1] == "desktop"


def _pendiente(carpeta, monkeypatch, texto="Probando la brigada de video"):
    from app import publicaciones as pub

    (v.salida_dir()).mkdir(parents=True, exist_ok=True)
    (v.salida_dir() / "demo.mp4").write_bytes(b"contenido del video")
    monkeypatch.setattr(v, "info", lambda p: {"archivo": p.name, "duracion_s": 12.0})
    monkeypatch.setattr(v, "resolver", lambda n, e=None: v.salida_dir() / n)
    return pub, pub.preparar("demo.mp4", texto)


def test_preparar_deja_una_pendiente_y_no_hay_ninguna_tool_que_publique(carpeta, monkeypatch):
    from app import tools

    pub, r = _pendiente(carpeta, monkeypatch)
    assert r["estado"] == "pendiente" and "no se publicó nada" in r["aviso"] and pub.listar()[0]["estado"] == "pendiente"
    publicadoras = {n for n in tools.get_tools() if "public" in n or "instagram" in n}
    assert publicadoras == {"video_preparar_publicacion"} and "aprobar" not in " ".join(tools.get_tools())
    for modo, nombres in vid.TOOLS.items():
        assert not any("public" in n and n != "video_preparar_publicacion" for n in nombres), modo
    with pytest.raises(pub.PublicacionError, match="Falta el texto"):
        pub.preparar("demo.mp4", "  ")
    with pytest.raises(pub.PublicacionError, match="2200"):
        pub.preparar("demo.mp4", "x" * 2201)


class _Meta:
    def __init__(self, estados=("IN_PROGRESS", "FINISHED"), falla_en=None):
        self.llamadas, self.estados, self.falla_en = [], list(estados), falla_en

    def __call__(self, metodo, url, **kw):
        self.llamadas.append((metodo, url, kw))
        if self.falla_en and self.falla_en in url:
            from app.publicaciones import PublicacionError
            raise PublicacionError("Instagram respondió 400: token inválido")
        if url.endswith("/media"):
            return {"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/C1"}
        if "rupload" in url:
            return {"success": True}
        if "status_code" in url:
            return {"status_code": self.estados.pop(0)}
        return {"id": "M9"}


def test_aprobar_publica_en_tres_pasos_una_sola_vez_y_sin_credenciales_sigue_pendiente(carpeta, monkeypatch):
    pub, r = _pendiente(carpeta, monkeypatch)
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_ACCESS_TOKEN", raising=False)
    with pytest.raises(pub.PublicacionError, match="Faltan IG_USER_ID"):
        pub.aprobar_y_publicar(r["id"], http=_Meta())
    assert pub.listar()[0]["estado"] == "pendiente"
    monkeypatch.setenv("IG_USER_ID", "123")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "SECRETO")
    meta = _Meta()
    out = pub.aprobar_y_publicar(r["id"], http=meta, esperar=0)
    pasos = [(m, u.rsplit("/", 1)[-1]) for m, u, _ in meta.llamadas]
    assert out["estado"] == "publicada" and out["media_id"] == "M9" and pasos[0] == ("POST", "media") and pasos[-1] == ("POST", "media_publish")
    assert meta.llamadas[0][2]["data"]["caption"] == "Probando la brigada de video" and meta.llamadas[1][2]["headers"]["file_size"] == str(len(b"contenido del video"))
    with pytest.raises(pub.PublicacionError, match="está publicada"):   # no se publica dos veces
        pub.aprobar_y_publicar(r["id"], http=_Meta())


def test_si_el_video_cambia_o_instagram_falla_no_se_publica_y_el_token_no_se_filtra(carpeta, monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "123")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "SECRETO")
    pub, r = _pendiente(carpeta, monkeypatch)
    (v.salida_dir() / "demo.mp4").write_bytes(b"otro contenido")
    meta = _Meta()
    with pytest.raises(pub.PublicacionError, match="cambiaron"):
        pub.aprobar_y_publicar(r["id"], http=meta)
    assert meta.llamadas == []                                          # ni siquiera se habló con Instagram
    pub2, r2 = _pendiente(carpeta, monkeypatch, "otro texto")
    with pytest.raises(pub.PublicacionError, match="token inválido"):
        pub.aprobar_y_publicar(r2["id"], http=_Meta(falla_en="/media"), esperar=0)
    rec = [p for p in pub.listar() if p["id"] == r2["id"]][0]
    assert rec["estado"] == "fallo" and "SECRETO" not in str(rec)
    with pytest.raises(pub.PublicacionError, match="está fallo"):       # un fallo no se reintenta solo
        pub.aprobar_y_publicar(r2["id"], http=_Meta())


def test_el_ruteo_manda_grabar_pantalla_y_publicar_a_sus_ayudantes_y_aprobar_es_un_endpoint():
    reglas = {r.modo: r for r in vid.ROUTING.reglas}
    import re
    assert re.search(reglas["grabacion"].patron, "quiero capturar la pantalla en pruebas de raphael", re.I) or \
        re.search(reglas["grabacion"].patron, "grabá la pantalla 30 segundos", re.I)
    assert re.search(reglas["redes"].patron, "subilo a instagram", re.I)
    src = (Path(__file__).resolve().parents[1] / "orquestador" / "server.py").read_text(encoding="utf-8")
    assert '"/api/publicaciones/{pid}/aprobar"' in src
