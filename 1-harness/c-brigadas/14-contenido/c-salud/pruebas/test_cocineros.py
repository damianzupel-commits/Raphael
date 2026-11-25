"""Los seis cocineros montados por el harness, con todo simulado: publicar pide aprobación, los trabajos pesados se encolan,
sin modelo ni claves cae a reglas y avisa, y nada sale al mundo por su cuenta."""

from __future__ import annotations

import pytest
from kit import System
from raphael_core import ActionError

from raphael_contenido.video import edicion as ve


@pytest.fixture
def x(tmp_path):
    s = System(tmp_path)
    ve.asegurar_carpetas()
    (ve.entrada_dir() / "a.mp4").write_bytes(b"video")
    return s


# --- video --------------------------------------------------------------------------------------------------------------
def test_editar_video_se_encola_y_deja_un_archivo_nuevo_sin_tocar_el_original(x):
    r = x.act("video", "editar_video", {"op": "recortar", "args": {"archivo": "a.mp4", "inicio": 0, "fin": 5}})
    assert r["state"] == "executed" and "trabajo #1" in r["text"]
    x.drain("video")
    [job] = x.cmd("video", "trabajos")
    assert job["estado"] == "listo" and job["resultado"]["original_intacto"] is True
    assert (ve.entrada_dir() / "a.mp4").read_bytes() == b"video"
    assert job["resultado"]["path"].startswith(str(ve.salida_dir()))
    x.tick()
    assert [d["tipo"] for _, d in x.events("video.listo")] == ["video"]


def test_operacion_o_argumentos_invalidos_se_rechazan_antes_de_encolar(x):
    assert "No conozco" in x.act("video", "editar_video", {"op": "borrar_todo"})["error"]
    assert "argumentos que no existen" in x.act("video", "editar_video", {"op": "recortar", "args": {"archivo": "a.mp4", "inicio": 0, "fin": 3, "rm": 1}})["error"]
    assert x.cmd("video", "trabajos") == []


def test_un_archivo_fuera_de_la_carpeta_falla_en_el_trabajo_y_avisa(x):
    x.act("video", "editar_video", {"op": "recortar", "args": {"archivo": "../../etc/passwd", "inicio": 0, "fin": 3}})
    x.drain("video")
    [job] = x.cmd("video", "trabajos")
    assert job["estado"] == "error" and "carpeta de video" in job["error"]
    x.tick()
    assert x.events("contenido.trabajo_fallido")


def test_proyecto_crear_editar_y_renderizar(x):
    t = x.act("video", "proyecto_crear", {"nombre": "Demo"})["text"]
    pid = t.split("id ")[1].split(",")[0]
    r = x.act("video", "proyecto_editar", {"proyecto": pid, "operaciones": [{"op": "agregar_clip", "archivo": "a.mp4", "fin": 8}]})
    assert r["state"] == "executed" and "revisión 2" in r["text"]
    assert x.cmd("video", "proyecto", {"proyecto": pid})["pistas"]["V1"]
    x.act("video", "proyecto_renderizar", {"proyecto": pid, "calidad": "preview"})
    x.drain("video")
    assert x.cmd("video", "trabajos")[-1]["estado"] == "listo", x.cmd("video", "trabajos")[-1].get("error")
    assert x.act("video", "proyecto_editar", {"proyecto": pid, "deshacer": True})["state"] == "executed"


def test_grabar_pantalla_pide_aprobacion_y_en_la_nube_no_se_ejecuta(tmp_path):
    p = System(tmp_path / "p")
    r = p.act("video", "grabar_pantalla", {"duracion": 5, "ventana": "Excel"})
    assert r["state"] == "pending" and r["level"] == "aprobacion"
    c = System(tmp_path / "c", edition="cloud", autonomy={"contenido.grabar_pantalla": "automatico"})
    assert "nunca en la nube" in c.act("video", "grabar_pantalla", {"duracion": 5, "ventana": "Excel"})["error"]


# --- instagram ----------------------------------------------------------------------------------------------------------
def prep(x, texto="Nuevo vestido 👗 #moda"):
    return x.act("instagram", "preparar_publicacion", {"archivo": "a.mp4", "texto": texto})


def test_preparar_no_publica_y_deja_la_aprobacion_pendiente(x):
    r = prep(x)
    assert "NO se publicó nada" in r["text"]
    [p] = x.pending("publicar_instagram")
    assert p["level"] == "aprobacion"
    assert x.cook("instagram").ig.published == []
    assert [e for e, _ in x.events("revision.pedida")]


def test_aprobar_publica_una_vez_y_queda_marcado_simulado(x):
    prep(x)
    x.approve(x.pending("publicar_instagram")[0]["id"])
    x.drain("instagram")
    [pub] = x.cmd("instagram", "publicaciones")
    assert pub["estado"] == "publicada" and pub["simulado"] is True and len(x.cook("instagram").ig.published) == 1
    x.tick()
    assert x.events("publicacion.publicada")


def test_si_el_video_cambia_despues_de_preparar_no_se_publica(x):
    prep(x)
    (ve.entrada_dir() / "a.mp4").write_bytes(b"otro video")
    res = x.approve(x.pending("publicar_instagram")[0]["id"])
    assert res["state"] == "error" and "cambiaron" in res["error"]
    assert x.cook("instagram").ig.published == []


def test_rechazar_descarta_la_publicacion(x):
    prep(x)
    x.reject(x.pending("publicar_instagram")[0]["id"], "no me gusta")
    assert x.cmd("instagram", "publicaciones")[0]["estado"] == "descartada"


def test_falla_se_intenta_una_sola_vez_y_el_motivo_queda(x):
    from raphael_contenido.adapters import InstagramMock
    prep(x)
    x.cook("instagram").ig = InstagramMock(fail_with="Instagram respondió 400")
    x.approve(x.pending("publicar_instagram")[0]["id"])
    x.drain("instagram")
    [pub] = x.cmd("instagram", "publicaciones")
    assert pub["estado"] == "fallo" and "400" in pub["motivo"]
    again = x.act("instagram", "publicar_instagram", {"id": pub["id"]})
    assert again["state"] == "pending"          # el harness pide aprobación de nuevo
    assert "solo se aprueba una pendiente" in x.approve(again["id"])["error"]


def test_texto_demasiado_largo_o_con_demasiados_hashtags(x):
    assert "2200" in prep(x, "a" * 2201)["error"]
    assert "hashtags" in prep(x, " ".join(f"#t{i}" for i in range(31)))["error"]
    assert "Falta el texto" in prep(x, "  ")["error"]


def test_sin_clave_se_prepara_pero_no_se_publica(tmp_path, monkeypatch):
    for v in ("IG_USER_ID", "IG_ACCESS_TOKEN", "CONTENIDO_MODO"):
        monkeypatch.delenv(v, raising=False)
    s = System(tmp_path, {"mode": "auto"})
    ve.asegurar_carpetas()
    (ve.entrada_dir() / "a.mp4").write_bytes(b"v")
    assert s.cook("instagram").ig.mode == "sin_clave"
    r = s.act("instagram", "publicar_instagram", {"id": "no-existe"})
    assert r["state"] == "pending" and "No existe" in s.approve(r["id"])["error"]


# --- imagen -------------------------------------------------------------------------------------------------------------
def test_generar_imagen_simulada_copia_a_entrada_y_se_marca(x):
    x.act("imagen", "generar_imagen", {"prompt": "a red dress on a mannequin", "width": 512, "height": 512})
    x.drain("imagen")
    [g] = x.cmd("imagen", "generados")
    assert g["simulado"] is True and (ve.entrada_dir() / g["archivo"]).is_file()
    assert "256 y 1536" in x.act("imagen", "generar_imagen", {"prompt": "x", "width": 99})["error"]
    assert "entre 1 y 5" in x.act("imagen", "generar_video", {"prompt": "x", "seconds": 9})["error"]


# --- contenido ----------------------------------------------------------------------------------------------------------
def test_copy_sin_modelo_usa_plantilla_avisa_y_no_inventa(x):
    r = x.act("contenido", "redactar_copy", {"tipo": "copy", "tema": "vestidos de fiesta"})
    assert "sin modelo" in r["text"] and "[completar:" in r["text"] and "#moda" in r["text"]
    [c] = x.cmd("contenido", "copys")
    assert c["origen"] == "reglas"


@pytest.mark.parametrize("tipo,clave", [("guion", "escenas"), ("carrusel", "slides")])
def test_guion_y_carrusel(x, tipo, clave):
    x.act("contenido", "redactar_copy", {"tipo": tipo, "tema": "telas", "puntos": ["lino", "seda"]})
    rec = x.cmd("contenido", "copy", {"id": x.cmd("contenido", "copys")[0]["id"]})
    assert rec[clave] and "lino" in rec["texto"]


def test_calendario_agenda_valida_y_propone(x):
    assert "ya pasó" in x.act("contenido", "agendar_post", {"fecha": "2026-11-01"})["error"]
    assert "AAAA-MM-DD" in x.act("contenido", "agendar_post", {"fecha": "mañana"})["error"]
    x.act("contenido", "agendar_post", {"fecha": "2026-11-27", "hora": "19:00", "nota": "vestidos"})
    [e] = x.cmd("contenido", "calendario")
    assert e["fecha"] == "2026-11-27"
    prop = x.cmd("contenido", "proponer_calendario", {"dias": 14, "por_semana": 3})["propuesta"]
    assert prop and all(p["fecha"] != "2026-11-27" for p in prop) and len(x.cmd("contenido", "calendario")) == 1
    x.act("contenido", "quitar_del_calendario", {"id": e["id"]})
    assert x.cmd("contenido", "calendario") == []


def test_copy_con_modelo_y_palabra_prohibida_cae_a_la_plantilla(tmp_path):
    s = System(tmp_path, {"brand": {"avoid": ["barato"]}})
    c = s.cook("contenido")
    ctx = s.rt.context("contenido", "contenido")
    ctx.has_ai = lambda role: True
    ctx.ai = lambda role, msgs, **kw: "Vestidos baratos, ¡aprovechá!"
    d = c._ai_draft(ctx, "copy", c.cfg.brand, "vestidos", [], "")
    assert d is None
    ctx.ai = lambda role, msgs, **kw: "Vestidos a medida, hechos con cariño."
    assert c._ai_draft(ctx, "copy", c.cfg.brand, "vestidos", [], "")["texto"].startswith("Vestidos a medida")


# --- campañas -----------------------------------------------------------------------------------------------------------
BORRADOR = {"nombre": "Primavera", "presupuesto_diario": 5000, "dias": 7, "texto": "Vestidos a medida 💌",
            "publico": {"edad_min": 25, "edad_max": 45, "ubicaciones": ["Rosario"]}}


def test_borrador_valida_tope_y_no_sube_nada(x):
    r = x.act("campanas", "crear_borrador_anuncio", BORRADOR)
    assert "total 35000" in r["text"] and "No se subió ni se gastó" in r["text"]
    assert x.cook("campanas").ads.campaigns == {}
    assert "entre 1 y 20000" in x.act("campanas", "crear_borrador_anuncio", {**BORRADOR, "presupuesto_diario": 99999})["error"]
    assert "edad" in x.act("campanas", "crear_borrador_anuncio", {**BORRADOR, "publico": {"edad_min": 10}})["error"]
    assert "https" in x.act("campanas", "crear_borrador_anuncio", {**BORRADOR, "destino_url": "http://x"})["error"]


def test_subir_y_activar_piden_aprobacion_cada_uno_y_en_orden(x):
    x.act("campanas", "crear_borrador_anuncio", BORRADOR)
    [b] = x.cmd("campanas", "borradores")
    activar = x.act("campanas", "activar_campana", {"id": b["id"]})
    assert activar["state"] == "pending"
    assert "solo se activa una campaña ya subida" in x.approve(activar["id"])["error"]
    sub = x.act("campanas", "subir_campana_pausada", {"id": b["id"]})
    assert sub["state"] == "pending"
    assert "EN PAUSA" in x.approve(sub["id"])["text"]
    assert x.cook("campanas").ads.campaigns["sim-camp-1"]["status"] == "PAUSED"
    act2 = x.act("campanas", "activar_campana", {"id": b["id"]})
    assert "ACTIVADA" in x.approve(act2["id"])["text"]
    assert x.cook("campanas").ads.campaigns["sim-camp-1"]["status"] == "ACTIVE"


def test_gasto_nunca_baja_solo_a_automatico(tmp_path):
    s = System(tmp_path, {}, autonomy={})
    s.act("campanas", "crear_borrador_anuncio", BORRADOR)
    bid = s.cmd("campanas", "borradores")[0]["id"]
    for _ in range(12):   # aprobar muchas veces no la deja en automático
        s.act("campanas", "activar_campana", {"id": bid})
    assert all(p["level"] == "aprobacion" for p in s.pending("activar_campana"))


def test_exportar_borrador(x):
    x.act("campanas", "crear_borrador_anuncio", BORRADOR)
    e = x.cmd("campanas", "exportar", {"id": x.cmd("campanas", "borradores")[0]["id"]})
    assert e["conjunto"]["presupuesto_diario"] == 5000 and e["anuncio"]["texto"]


# --- analítica ----------------------------------------------------------------------------------------------------------
def test_metricas_simuladas_vienen_marcadas_y_las_recomendaciones_dicen_cuantos_datos(x):
    assert "Todavía no hay métricas" in str(pytest.raises(ActionError, x.cmd, "analitica", "resumen").value)
    r = x.act("analitica", "sincronizar_metricas")
    assert "SIMULADOS" in r["text"]
    rec = x.cmd("analitica", "recomendaciones")
    assert rec["simulado"] is True and rec["datos"] == 3 and rec["origen"] == "reglas"
    assert any("es poco para hablar" in t for t in rec["recomendaciones"])
    assert x.cmd("analitica", "resumen")["mejores"][0]["id"] == "sim-2"


# --- legales ------------------------------------------------------------------------------------------------------------
def test_pide_revision_de_legales_antes_de_publicar(x):
    prep(x, "Oferta solo hoy")
    x.approve(x.pending("publicar_instagram")[0]["id"])
    evs = [d for _, d in x.events("revision.pedida")]
    assert len(evs) == 2 and all(d["texto"] == "Oferta solo hoy" and d["origen"] == "contenido" for d in evs)
