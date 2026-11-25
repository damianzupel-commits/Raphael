"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Las de lectura llaman al `command` del cocinero dueño del dato (mismo código, mismos resultados). Las tres que guardan algo
(`contenido_guardar_copy`, `contenido_agendar_post`, `contenido_crear_borrador_anuncio`) hacen lo mismo que sus acciones
automáticas: dejan un BORRADOR o una fecha, nada sale al mundo ni gasta plata. Publicar en Instagram, subir o activar una
campaña y grabar la pantalla NO son tools: siguen siendo las acciones con aprobación de sus cocineros, a pedido de la persona.
"""

from __future__ import annotations

from datetime import date, datetime

from raphael_core import ActionError

from . import entorno
from .comun import need_str, new_id
from .config import contenido_config
from .cooks.analitica import Analitica
from .cooks.campanas import Campanas
from .cooks.contenido import TIPOS, Contenido, _cap, _hashtags
from .cooks.imagen import Imagen
from .cooks.instagram import Instagram
from .cooks.video import Video


class _ToolCtx:
    """Lo que usan los cocineros de contenido del contexto para leer y guardar borradores (todo en `shared`)."""

    def __init__(self, setup_ctx) -> None:
        self.config, self.shared = setup_ctx.config, setup_ctx.shared

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @staticmethod
    def today() -> date:
        return date.today()

    @staticmethod
    def has_ai(*_a, **_k) -> bool:
        return False


def make_tools(ctx) -> dict:
    tc = _ToolCtx(ctx)
    cfg = contenido_config(ctx.config)
    contenido, campanas = Contenido(), Campanas()
    contenido.cfg = campanas.cfg = cfg          # lo que sus `start` arman (sin conectar adaptadores: las tools no publican)

    def _leer(cook, name: str, data: dict | None = None):
        try:
            return cook.command(name, data or {}, tc)
        except ActionError as exc:
            return {"ok": False, "motivo": str(exc)}

    def _video():
        entorno.video_setup(cfg, entorno.build(cfg))
        return Video()

    def contenido_copys(tipo: str = "") -> list[dict]:
        """Borradores de copys, guiones y carruseles guardados; filtra por tipo (copy, guion, carrusel)."""
        return _leer(contenido, "copys", {"tipo": tipo or None})

    def contenido_copy(id: str) -> dict:
        """Un borrador de copy por su id."""
        return _leer(contenido, "copy", {"id": id})

    def contenido_guardar_copy(tipo: str, tema: str, texto: str, hashtags: list | None = None) -> dict:
        """Guarda un borrador de copy, guion o carrusel (tipo: copy, guion o carrusel) ya redactado. No publica nada."""
        if tipo not in TIPOS:
            return {"ok": False, "motivo": f"«tipo» es uno de: {', '.join(TIPOS)}."}
        try:
            texto = need_str({"texto": texto}, "texto", max_len=5000)
            tema = need_str({"tema": tema}, "tema", max_len=300)
        except ActionError as exc:
            return {"ok": False, "motivo": str(exc)}
        if any(w.lower() in texto.lower() for w in cfg.brand.avoid):
            return {"ok": False, "motivo": "el texto usa una palabra que la marca no dice (config `brand.avoid`): reescribilo"}
        tags = _hashtags(cfg.brand, hashtags if isinstance(hashtags, list) else None, cfg.instagram.max_hashtags)
        cuerpo = _cap(texto, cfg.instagram.max_caption - (sum(len(h) + 2 for h in tags) + 2))
        if tags and tipo == "copy":
            cuerpo += "\n\n" + " ".join(f"#{h}" for h in tags)
        rec = {"id": new_id(), "tipo": tipo, "tema": tema, "origen": "ia", "creado": tc.now().isoformat(timespec="seconds"),
               "hashtags": tags, "texto": cuerpo}
        tc.shared.put("copys", rec["id"], rec)
        return {"ok": True, "id": rec["id"], "tipo": tipo, "guardado": "borrador: no se publicó nada", "texto": cuerpo}

    def contenido_calendario(desde: str = "", hasta: str = "") -> list[dict]:
        """El calendario editorial entre dos fechas (AAAA-MM-DD, ambas opcionales)."""
        return _leer(contenido, "calendario", {"desde": desde or None, "hasta": hasta or None})

    def contenido_proponer_calendario(dias: int = 14, por_semana: int = 3) -> dict:
        """Propone fechas libres para publicar (por reglas); no guarda nada."""
        return _leer(contenido, "proponer_calendario", {"dias": dias, "por_semana": por_semana})

    def contenido_agendar_post(fecha: str, hora: str = "19:00", copy_id: str = "", nota: str = "") -> dict:
        """Pone una fecha (AAAA-MM-DD) y una hora (HH:MM) en el calendario editorial. Es solo una fecha: publicar pide aprobación."""
        try:
            return {"ok": True, "resultado": contenido._schedule(
                {"fecha": fecha, "hora": hora, "copy_id": copy_id or None, "nota": nota}, tc)}
        except ActionError as exc:
            return {"ok": False, "motivo": str(exc)}

    def contenido_publicaciones(estado: str = "") -> list[dict]:
        """Las publicaciones de Instagram (preparadas, pendientes, publicadas, con fallo); filtra por estado."""
        return _leer(Instagram(), "publicaciones", {"estado": estado or None})

    def contenido_publicacion(id: str) -> dict:
        """Una publicación por su id."""
        return _leer(Instagram(), "publicacion", {"id": id})

    def contenido_borradores_anuncio(estado: str = "") -> list[dict]:
        """Los borradores de anuncios; filtra por estado."""
        return _leer(campanas, "borradores", {"estado": estado or None})

    def contenido_borrador_anuncio(id: str) -> dict:
        """Un borrador de anuncio por su id."""
        return _leer(campanas, "borrador", {"id": id})

    def contenido_crear_borrador_anuncio(nombre: str, presupuesto_diario: float, dias: int, texto: str = "", copy_id: str = "",
                                         objetivo: str = "", destino_url: str = "", publico: dict | None = None) -> dict:
        """Arma un borrador de anuncio (presupuesto diario con el tope de la instalación, días, público). No se sube ni se gasta."""
        d = {"nombre": nombre, "presupuesto_diario": presupuesto_diario, "dias": dias, "texto": texto or None,
             "copy_id": copy_id or None, "destino_url": destino_url, "publico": publico or {}}
        if objetivo:
            d["objetivo"] = objetivo
        try:
            return {"ok": True, "resultado": campanas._draft(d, tc)}
        except (ActionError, ValueError, TypeError) as exc:
            return {"ok": False, "motivo": str(exc)}

    def contenido_exportar_anuncio(id: str) -> dict:
        """El borrador listo para cargar a mano en el Administrador de anuncios de Meta."""
        return _leer(campanas, "exportar", {"id": id})

    def contenido_metricas_resumen() -> dict:
        """Resumen de la última foto de métricas de Instagram. Sin métricas sincronizadas lo dice."""
        return _leer(Analitica(), "resumen")

    def contenido_metricas_recomendaciones() -> dict:
        """Qué conviene repetir según las métricas (por reglas)."""
        return _leer(Analitica(), "recomendaciones")

    def contenido_metricas_historial() -> list[dict]:
        """Las fotos de métricas guardadas, de la más vieja a la más nueva."""
        return _leer(Analitica(), "historial")

    def contenido_generados() -> list[dict]:
        """Las imágenes y videos generados con ComfyUI (los últimos 50)."""
        return _leer(Imagen(), "generados")

    def contenido_video_listar() -> list[dict]:
        """Los archivos de la carpeta de video."""
        return _leer(_video(), "listar")

    def contenido_video_info(archivo: str) -> dict:
        """Datos de un archivo de video, audio o imagen de la carpeta de video (duración, formato, tamaño)."""
        return _leer(_video(), "info", {"archivo": archivo})

    def contenido_video_proyectos() -> list[dict]:
        """Los proyectos de edición."""
        return _leer(_video(), "proyectos")

    def contenido_video_proyecto(proyecto: str) -> dict:
        """Un proyecto de edición con su línea de tiempo."""
        return _leer(_video(), "proyecto", {"proyecto": proyecto})

    def contenido_video_operaciones() -> dict:
        """Las operaciones de edición de video disponibles."""
        return _leer(_video(), "operaciones")

    return {f.__name__: f for f in (
        contenido_copys, contenido_copy, contenido_guardar_copy, contenido_calendario, contenido_proponer_calendario,
        contenido_agendar_post, contenido_publicaciones, contenido_publicacion, contenido_borradores_anuncio,
        contenido_borrador_anuncio, contenido_crear_borrador_anuncio, contenido_exportar_anuncio, contenido_metricas_resumen,
        contenido_metricas_recomendaciones, contenido_metricas_historial, contenido_generados, contenido_video_listar,
        contenido_video_info, contenido_video_proyectos, contenido_video_proyecto, contenido_video_operaciones)}
