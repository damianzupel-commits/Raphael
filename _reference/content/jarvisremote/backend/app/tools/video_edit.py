"""Tools de EDICIÓN DE VIDEO (brigada de Video): envoltorios de `app/video_edit.py`.

Todas trabajan SOLO dentro de la carpeta fija de video (`VIDEO_EDIT_DIR`), nunca modifican ni borran el original y dejan
el resultado como archivo nuevo en `salida/`. Esas reglas las hace cumplir el núcleo, no el prompt. Un error (archivo fuera
de la carpeta, ffmpeg no instalado, tiempos inválidos) sale como excepción con un mensaje claro: el ayudante lo reporta."""

from __future__ import annotations

from typing import Any, Callable

from .. import audit_log, video_edit, video_proyecto
from . import register_tool

_ARCHIVO = {"type": "string", "description": "Nombre del archivo dentro de la carpeta de video (ej. 'charla.mp4'). Se busca en entrada/ y en salida/."}
_TIEMPO = "en segundos (90) o como mm:ss / hh:mm:ss (1:30)"


def _correr(tool: str, argumentos: dict, fn: Callable[[], Any]) -> Any:
    try:
        resultado = fn()
    except (video_edit.VideoError, video_proyecto.ProyectoError) as exc:
        audit_log.log_tool_call(target="pc", tool=tool, arguments=argumentos, error=str(exc))
        raise
    audit_log.log_tool_call(target="pc", tool=tool, arguments=argumentos, result=resultado)
    return resultado


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


@register_tool(name="video_listar", description="Lista los videos, audios y subtítulos que hay en la carpeta de video (entrada/ y salida/). Solo lee.",
               parameters=_obj({}, []))
def video_listar() -> dict:
    return _correr("video_listar", {}, video_edit.listar)


@register_tool(name="video_info", description="Duración, resolución, fps y pistas de un archivo de la carpeta de video. Solo lee.",
               parameters=_obj({"archivo": _ARCHIVO}, ["archivo"]))
def video_info(archivo: str) -> dict:
    return _correr("video_info", {"archivo": archivo}, lambda: video_edit.info(video_edit.resolver(archivo, video_edit.VIDEO_EXT | video_edit.AUDIO_EXT)))


@register_tool(
    name="video_recortar",
    description=("Recorta un tramo de un video (de `inicio` a `fin`) y lo guarda como archivo NUEVO en salida/. Por defecto no "
                 "recodifica (rápido y liviano; el corte puede correrse hasta el cuadro clave más cercano). `preciso=true` corta "
                 "exacto pero recodifica: más lento y más carga para la PC; usalo solo si Damian pide precisión."),
    parameters=_obj({"archivo": _ARCHIVO, "inicio": {"type": "string", "description": f"Inicio del tramo, {_TIEMPO}."},
                     "fin": {"type": "string", "description": f"Fin del tramo, {_TIEMPO}."},
                     "preciso": {"type": "boolean", "description": "Corte exacto recodificando (default false)."}}, ["archivo", "inicio", "fin"]))
def video_recortar(archivo: str, inicio: Any, fin: Any, preciso: bool = False) -> dict:
    return _correr("video_recortar", {"archivo": archivo, "inicio": inicio, "fin": fin, "preciso": preciso},
                   lambda: video_edit.recortar(archivo, inicio, fin, bool(preciso)))


@register_tool(name="video_unir", description="Une varios videos, en el orden dado, en un archivo NUEVO en salida/. Si tienen el mismo formato no recodifica.",
               parameters=_obj({"archivos": {"type": "array", "items": {"type": "string"}, "description": "De 2 a 20 nombres de archivo, en orden."}}, ["archivos"]))
def video_unir(archivos: list) -> dict:
    return _correr("video_unir", {"archivos": archivos}, lambda: video_edit.unir(archivos))


@register_tool(
    name="video_convertir",
    description="Convierte un video a otro formato o resolución (o extrae solo el audio) en un archivo NUEVO en salida/. Recodifica.",
    parameters=_obj({"archivo": _ARCHIVO, "formato": {"type": "string", "enum": sorted(video_edit.FORMATOS_SALIDA), "description": "mp4/mov/mkv (video) o mp3/wav/m4a (solo audio). Default mp4."},
                     "alto": {"type": "integer", "description": "Alto en píxeles (ej. 720, 1080); el ancho se ajusta solo. Omitir para conservar la resolución."}}, ["archivo"]))
def video_convertir(archivo: str, formato: str = "mp4", alto: int | None = None) -> dict:
    return _correr("video_convertir", {"archivo": archivo, "formato": formato, "alto": alto}, lambda: video_edit.convertir(archivo, formato, alto))


@register_tool(
    name="video_quitar_silencios",
    description="Detecta los silencios de un video y arma un archivo NUEVO sin ellos. Recodifica. Devuelve cuántos segundos sacó.",
    parameters=_obj({"archivo": _ARCHIVO, "umbral_db": {"type": "number", "description": "Volumen por debajo del cual es silencio (default -35)."},
                     "min_silencio": {"type": "number", "description": "Duración mínima de un silencio para cortarlo, en segundos (default 0.6)."},
                     "margen": {"type": "number", "description": "Aire que se deja a cada lado para no cortar palabras (default 0.15)."}}, ["archivo"]))
def video_quitar_silencios(archivo: str, umbral_db: float = -35.0, min_silencio: float = 0.6, margen: float = 0.15) -> dict:
    return _correr("video_quitar_silencios", {"archivo": archivo, "umbral_db": umbral_db, "min_silencio": min_silencio, "margen": margen},
                   lambda: video_edit.quitar_silencios(archivo, umbral_db, min_silencio, margen))


@register_tool(
    name="video_audio",
    description=("Mejora el audio de un video en un archivo NUEVO: normaliza el volumen, reduce ruido de fondo y/o agrega música "
                 "de fondo (un audio de la carpeta de video). La imagen se copia tal cual (no recodifica el video)."),
    parameters=_obj({"archivo": _ARCHIVO, "normalizar": {"type": "boolean", "description": "Emparejar el volumen (default true)."},
                     "reducir_ruido": {"type": "boolean", "description": "Reducir ruido de fondo (default false)."},
                     "musica": {"type": "string", "description": "Nombre de un audio de la carpeta de video para poner de fondo (opcional)."},
                     "volumen_musica": {"type": "number", "description": "Volumen de la música, 0.01 a 1.0 (default 0.15)."}}, ["archivo"]))
def video_audio(archivo: str, normalizar: bool = True, reducir_ruido: bool = False, musica: str | None = None, volumen_musica: float = 0.15) -> dict:
    return _correr("video_audio", {"archivo": archivo, "normalizar": normalizar, "reducir_ruido": reducir_ruido, "musica": musica, "volumen_musica": volumen_musica},
                   lambda: video_edit.audio(archivo, bool(normalizar), bool(reducir_ruido), musica or None, volumen_musica))


@register_tool(
    name="video_transcribir",
    description=("Transcribe el audio de un video con Whisper EN ESTA PC (no sale a la nube) y guarda un .srt NUEVO en salida/. "
                 "Devuelve el texto y los `momentos` (frases con su inicio y fin en segundos), que sirven para elegir qué tramos "
                 "recortar. Es lenta en videos largos."),
    parameters=_obj({"archivo": _ARCHIVO, "idioma": {"type": "string", "description": "Código de dos letras (default 'es')."}}, ["archivo"]))
def video_transcribir(archivo: str, idioma: str = "es") -> dict:
    return _correr("video_transcribir", {"archivo": archivo, "idioma": idioma}, lambda: video_edit.transcribir(archivo, idioma))


@register_tool(
    name="video_subtitular",
    description=("Le pone a un video los subtítulos de un .srt (el que dejó video_transcribir) en un archivo NUEVO. `quemar=true` "
                 "(default) los dibuja sobre la imagen (recodifica; se ven en cualquier red); `quemar=false` los agrega como pista."),
    parameters=_obj({"archivo": _ARCHIVO, "subtitulos": {"type": "string", "description": "Nombre del .srt en la carpeta de video."},
                     "quemar": {"type": "boolean", "description": "Dibujarlos sobre la imagen (default true)."}}, ["archivo", "subtitulos"]))
def video_subtitular(archivo: str, subtitulos: str, quemar: bool = True) -> dict:
    return _correr("video_subtitular", {"archivo": archivo, "subtitulos": subtitulos, "quemar": quemar},
                   lambda: video_edit.subtitular(archivo, subtitulos, bool(quemar)))


@register_tool(
    name="video_vertical",
    description=("Arma un clip VERTICAL 9:16 (1080x1920, para Reels/Shorts/TikTok) recortando el centro del cuadro, en un archivo "
                 "NUEVO. Con `inicio` y `fin` saca solo ese tramo (máximo 180 s). Recodifica."),
    parameters=_obj({"archivo": _ARCHIVO, "inicio": {"type": "string", "description": f"Inicio del clip, {_TIEMPO} (opcional)."},
                     "fin": {"type": "string", "description": f"Fin del clip, {_TIEMPO} (opcional)."}}, ["archivo"]))
def video_vertical(archivo: str, inicio: Any = None, fin: Any = None) -> dict:
    return _correr("video_vertical", {"archivo": archivo, "inicio": inicio, "fin": fin}, lambda: video_edit.vertical(archivo, inicio, fin))


# --- segunda tanda: transiciones, títulos, velocidad, color, capas ----------------------------------------------------------
_N = {"type": "number"}
_S = {"type": "string"}


@register_tool(
    name="video_transicion",
    description=("Une de 2 a 8 clips, en orden, con una TRANSICIÓN entre cada par (fundido, barrido, deslizamiento...) en un archivo "
                 "NUEVO. Recodifica. Para unir sin transición usá video_unir."),
    parameters=_obj({"archivos": {"type": "array", "items": _S, "description": "Nombres de los clips, en orden."},
                     "tipo": {"type": "string", "enum": list(video_edit.TRANSICIONES), "description": "Tipo de transición (default fade)."},
                     "duracion": {**_N, "description": "Duración de cada transición en segundos, 0.2 a 3 (default 1)."}}, ["archivos"]))
def video_transicion(archivos: list, tipo: str = "fade", duracion: float = 1.0) -> dict:
    return _correr("video_transicion", {"archivos": archivos, "tipo": tipo, "duracion": duracion}, lambda: video_edit.transicion(archivos, tipo, duracion))


@register_tool(name="video_velocidad", description="Cámara lenta (factor menor a 1) o rápida (mayor a 1) en un archivo NUEVO; el audio acompaña sin cambiar de tono. Recodifica.",
               parameters=_obj({"archivo": _ARCHIVO, "factor": {**_N, "description": "0.25 a 4 (0.5 = mitad de velocidad, 2 = el doble)."}}, ["archivo", "factor"]))
def video_velocidad(archivo: str, factor: float) -> dict:
    return _correr("video_velocidad", {"archivo": archivo, "factor": factor}, lambda: video_edit.velocidad(archivo, factor))


@register_tool(
    name="video_color",
    description="Ajusta brillo, contraste y saturación y/o aplica un filtro de color (blanco y negro, sepia, cálido, frío, vintage) en un archivo NUEVO. Recodifica.",
    parameters=_obj({"archivo": _ARCHIVO, "brillo": {**_N, "description": "-0.5 a 0.5 (default 0)."}, "contraste": {**_N, "description": "0.5 a 2 (default 1)."},
                     "saturacion": {**_N, "description": "0 a 3 (default 1; 0 = sin color)."},
                     "filtro": {"type": "string", "enum": list(video_edit.FILTROS_COLOR), "description": "Filtro de color (default ninguno)."}}, ["archivo"]))
def video_color(archivo: str, brillo: float = 0.0, contraste: float = 1.0, saturacion: float = 1.0, filtro: str = "ninguno") -> dict:
    return _correr("video_color", {"archivo": archivo, "brillo": brillo, "contraste": contraste, "saturacion": saturacion, "filtro": filtro},
                   lambda: video_edit.color(archivo, brillo, contraste, saturacion, filtro))


@register_tool(
    name="video_texto",
    description="Pone un título o texto sobre el video (con contorno y fundido suave) en un archivo NUEVO. Recodifica.",
    parameters=_obj({"archivo": _ARCHIVO, "texto": {**_S, "description": "El texto (hasta 300 caracteres)."},
                     "posicion": {"type": "string", "enum": ["arriba", "centro", "abajo"], "description": "Default abajo."},
                     "inicio": {**_S, "description": f"Desde cuándo se ve, {_TIEMPO} (default: desde el principio)."},
                     "fin": {**_S, "description": f"Hasta cuándo, {_TIEMPO} (default: hasta el final)."},
                     "tamano": {"type": "integer", "description": "Tamaño de letra, 12 a 200 (default 48)."},
                     "color": {"type": "string", "enum": list(video_edit.COLORES), "description": "Default blanco."}}, ["archivo", "texto"]))
def video_texto(archivo: str, texto: str, posicion: str = "abajo", inicio: Any = None, fin: Any = None, tamano: int = 48, color: str = "blanco") -> dict:
    return _correr("video_texto", {"archivo": archivo, "texto": texto, "posicion": posicion, "inicio": inicio, "fin": fin, "tamano": tamano, "color": color},
                   lambda: video_edit.texto(archivo, texto, posicion, inicio, fin, tamano, color))


@register_tool(
    name="video_superponer",
    description=("Pone un logo, marca de agua o un segundo video ENCIMA del video (imagen en imagen) en un archivo NUEVO. La capa es "
                 "una imagen (png/jpg) o un video de la carpeta de video. Recodifica."),
    parameters=_obj({"archivo": _ARCHIVO, "capa": {**_S, "description": "Nombre de la imagen o video que va encima."},
                     "posicion": {"type": "string", "enum": list(video_edit.POSICIONES), "description": "Default abajo_derecha."},
                     "escala": {**_N, "description": "Ancho de la capa respecto del video, 0.03 a 1 (default 0.2)."},
                     "opacidad": {**_N, "description": "0.05 a 1 (default 1)."},
                     "inicio": {**_S, "description": f"Desde cuándo se ve, {_TIEMPO} (opcional)."}, "fin": {**_S, "description": f"Hasta cuándo, {_TIEMPO} (opcional)."}},
                    ["archivo", "capa"]))
def video_superponer(archivo: str, capa: str, posicion: str = "abajo_derecha", escala: float = 0.2, opacidad: float = 1.0, inicio: Any = None, fin: Any = None) -> dict:
    return _correr("video_superponer", {"archivo": archivo, "capa": capa, "posicion": posicion, "escala": escala, "opacidad": opacidad, "inicio": inicio, "fin": fin},
                   lambda: video_edit.superponer(archivo, capa, posicion, escala, opacidad, inicio, fin))


@register_tool(name="video_fundidos", description="Fundido desde negro al empezar y/o a negro al terminar (imagen y sonido) en un archivo NUEVO. Recodifica.",
               parameters=_obj({"archivo": _ARCHIVO, "entrada": {**_N, "description": "Segundos del fundido inicial, 0 a 5 (default 1)."},
                                "salida": {**_N, "description": "Segundos del fundido final, 0 a 5 (default 1)."}}, ["archivo"]))
def video_fundidos(archivo: str, entrada: float = 1.0, salida: float = 1.0) -> dict:
    return _correr("video_fundidos", {"archivo": archivo, "entrada": entrada, "salida": salida}, lambda: video_edit.fundidos(archivo, entrada, salida))


@register_tool(name="video_rotar", description="Gira (90, 180, 270 grados) o espeja un video en un archivo NUEVO. Recodifica.",
               parameters=_obj({"archivo": _ARCHIVO, "giro": {"type": "string", "enum": ["90", "180", "270", "espejo", "voltear"],
                                                              "description": "Grados en sentido horario, 'espejo' (horizontal) o 'voltear' (vertical)."}}, ["archivo", "giro"]))
def video_rotar(archivo: str, giro: str) -> dict:
    return _correr("video_rotar", {"archivo": archivo, "giro": giro}, lambda: video_edit.rotar(archivo, str(giro)))


@register_tool(
    name="video_encuadrar",
    description="Recorta el CUADRO de un video (zoom a una zona) en un archivo NUEVO. Los valores son porcentajes del cuadro original. Recodifica.",
    parameters=_obj({"archivo": _ARCHIVO, "x": {**_N, "description": "Borde izquierdo de la zona, 0 a 100."}, "y": {**_N, "description": "Borde superior, 0 a 100."},
                     "ancho": {**_N, "description": "Ancho de la zona, 10 a 100."}, "alto": {**_N, "description": "Alto de la zona, 10 a 100."}}, ["archivo", "x", "y", "ancho", "alto"]))
def video_encuadrar(archivo: str, x: float, y: float, ancho: float, alto: float) -> dict:
    return _correr("video_encuadrar", {"archivo": archivo, "x": x, "y": y, "ancho": ancho, "alto": alto}, lambda: video_edit.encuadrar(archivo, x, y, ancho, alto))


@register_tool(name="video_estabilizar", description="Reduce el temblor de cámara de un video en un archivo NUEVO. Recodifica y es lento.",
               parameters=_obj({"archivo": _ARCHIVO}, ["archivo"]))
def video_estabilizar(archivo: str) -> dict:
    return _correr("video_estabilizar", {"archivo": archivo}, lambda: video_edit.estabilizar(archivo))


@register_tool(
    name="video_pantalla_verde",
    description="Reemplaza el fondo verde (o azul) de un video por una imagen o un video de fondo, en un archivo NUEVO. Recodifica.",
    parameters=_obj({"archivo": _ARCHIVO, "fondo": {**_S, "description": "Imagen o video de la carpeta de video que va de fondo."},
                     "color": {"type": "string", "enum": ["verde", "azul"], "description": "Color del fondo a reemplazar (default verde)."},
                     "tolerancia": {**_N, "description": "Cuánto color parecido se borra, 0.01 a 0.5 (default 0.15)."}}, ["archivo", "fondo"]))
def video_pantalla_verde(archivo: str, fondo: str, color: str = "verde", tolerancia: float = 0.15) -> dict:
    return _correr("video_pantalla_verde", {"archivo": archivo, "fondo": fondo, "color": color, "tolerancia": tolerancia},
                   lambda: video_edit.pantalla_verde(archivo, fondo, color, tolerancia))


@register_tool(name="video_escenas", description="Detecta los cambios de escena de un video y devuelve en qué segundos cambia el plano (sirve para decidir dónde cortar). Solo lee.",
               parameters=_obj({"archivo": _ARCHIVO, "sensibilidad": {**_N, "description": "0.1 (detecta más cambios) a 0.9 (solo los muy marcados); default 0.35."}}, ["archivo"]))
def video_escenas(archivo: str, sensibilidad: float = 0.35) -> dict:
    return _correr("video_escenas", {"archivo": archivo, "sensibilidad": sensibilidad}, lambda: video_edit.escenas(archivo, sensibilidad))


@register_tool(name="video_gif", description="Arma un GIF animado de un tramo corto (hasta 15 s) de un video, en un archivo NUEVO.",
               parameters=_obj({"archivo": _ARCHIVO, "inicio": {**_S, "description": f"Inicio, {_TIEMPO}."}, "fin": {**_S, "description": f"Fin, {_TIEMPO}."},
                                "ancho": {"type": "integer", "description": "Ancho en píxeles, 120 a 800 (default 480)."}}, ["archivo", "inicio", "fin"]))
def video_gif(archivo: str, inicio: Any, fin: Any, ancho: int = 480) -> dict:
    return _correr("video_gif", {"archivo": archivo, "inicio": inicio, "fin": fin, "ancho": ancho}, lambda: video_edit.gif(archivo, inicio, fin, ancho))


@register_tool(name="video_captura", description="Guarda una imagen fija (JPG) de un momento del video, en un archivo NUEVO.",
               parameters=_obj({"archivo": _ARCHIVO, "momento": {**_S, "description": f"El momento, {_TIEMPO}."}}, ["archivo", "momento"]))
def video_captura(archivo: str, momento: Any) -> dict:
    return _correr("video_captura", {"archivo": archivo, "momento": momento}, lambda: video_edit.captura(archivo, momento))


@register_tool(name="video_reversa", description="Pone un clip corto (hasta 30 s) al revés, en un archivo NUEVO. Recodifica.",
               parameters=_obj({"archivo": _ARCHIVO}, ["archivo"]))
def video_reversa(archivo: str) -> dict:
    return _correr("video_reversa", {"archivo": archivo}, lambda: video_edit.reversa(archivo))


@register_tool(
    name="video_grabar_pantalla",
    description=("Graba la pantalla (sin audio) por una duración fija y deja un video NUEVO en entrada/, listo para editar. Hay que elegir "
                 "QUÉ grabar: el título exacto de una ventana (`ventana`, ej. 'Raphael — Orquestador') o `escritorio_completo=true`, que "
                 "puede mostrar claves y datos privados: usalo solo si Damian lo pidió expresamente. Solo Windows."),
    parameters=_obj({"duracion": {"type": "number", "description": "Segundos a grabar (de 1 hasta el tope, 300 por defecto)."},
                     "nombre": {"type": "string", "description": "Nombre corto para el archivo (ej. 'prueba-brigada-video')."},
                     "ventana": {"type": "string", "description": "Título exacto de la ventana a grabar."},
                     "escritorio_completo": {"type": "boolean", "description": "Grabar todo el escritorio (puede mostrar datos privados)."}}, ["duracion"]))
def video_grabar_pantalla(duracion: Any, nombre: str = "grabacion", ventana: str | None = None, escritorio_completo: bool = False) -> dict:
    return _correr("video_grabar_pantalla", {"duracion": duracion, "nombre": nombre, "ventana": ventana, "escritorio_completo": escritorio_completo},
                   lambda: video_edit.grabar_pantalla(duracion, nombre, ventana, bool(escritorio_completo)))


@register_tool(
    name="video_preparar_publicacion",
    description=("Deja un video de salida/ (o entrada/) como publicación PENDIENTE para Instagram, con su texto. NO publica nada: la publicación "
                 "solo sale cuando Damian la aprueba él, desde el panel de publicaciones del orquestador. Devuelve el id de la pendiente."),
    parameters=_obj({"archivo": _ARCHIVO, "texto": {"type": "string", "description": "Descripción de la publicación (hasta 2200 caracteres), tal cual saldrá."}},
                    ["archivo", "texto"]))
def video_preparar_publicacion(archivo: str, texto: str) -> dict:
    from .. import publicaciones
    try:
        resultado = publicaciones.preparar(archivo, texto)
    except (publicaciones.PublicacionError, video_edit.VideoError) as exc:
        audit_log.log_tool_call(target="pc", tool="video_preparar_publicacion", arguments={"archivo": archivo}, error=str(exc))
        raise
    audit_log.log_tool_call(target="pc", tool="video_preparar_publicacion", arguments={"archivo": archivo}, result=resultado)
    return resultado


_PROYECTO = {"type": "string", "description": "Id del proyecto de edición (lo devuelve video_proyecto_crear; está en la lista de proyectos)."}


@register_tool(
    name="video_proyecto_crear",
    description=("Crea un PROYECTO DE EDICIÓN vacío: el documento que el usuario ve y toca en la línea de tiempo del panel de Video y que vos editás "
                 "con video_proyecto_editar. Tiene 5 pistas: V1 (video, clips uno tras otro, con transiciones), O1 (capas: imágenes, GIFs o videos superpuestos donde quieras), T1 (textos), A1 (música/locución) y A2 (efectos de sonido). Devuelve el id."),
    parameters=_obj({"nombre": {"type": "string", "description": "Nombre del proyecto (ej. 'Cumple de Sofi')."},
                     "formato": {"type": "string", "enum": sorted(video_proyecto.FORMATOS), "description": "vertical (1080x1920, reels), horizontal (1920x1080) o cuadrado. Default vertical."}}, ["nombre"]))
def video_proyecto_crear(nombre: str, formato: str = "vertical") -> dict:
    return _correr("video_proyecto_crear", {"nombre": nombre, "formato": formato}, lambda: video_proyecto.crear(nombre, formato))


@register_tool(
    name="video_proyecto_ver",
    description=("Lee un proyecto de edición tal como está AHORA (el usuario pudo haberlo cambiado en el panel): clips de cada pista con su id, "
                 "tiempos y parámetros, duración total y número de revisión (`rev`). Sin `proyecto`, lista los proyectos que hay. Solo lee."),
    parameters=_obj({"proyecto": _PROYECTO}, []))
def video_proyecto_ver(proyecto: str | None = None) -> dict:
    return _correr("video_proyecto_ver", {"proyecto": proyecto}, lambda: video_proyecto.leer(proyecto) if proyecto else {"proyectos": video_proyecto.listar()})


@register_tool(
    name="video_proyecto_editar",
    description=("Modifica un proyecto de edición con una LISTA de operaciones, ATÓMICA (si una falla no se aplica ninguna y el error dice cuál). "
                 "Tiempos en segundos (o mm:ss). Operaciones (campo `op`): "
                 "agregar_clip {pista:V1|A1|A2, archivo, inicio?, fin?, pos? (A1/A2), indice? (V1)} (los efectos de sonido del pack están en efectos/: ding, campana, pop, tic, whoosh, subida, caida, alerta → pista A2); "
                 "agregar_overlay {archivo (imagen, GIF o video), pos, dur?, x? y? (CENTRO de la capa, 0-1 del cuadro; .5/.5 = centro), escala? (0.05-1, ancho relativo), opacidad?, rotacion? (-180..180), fundido_in?, fundido_out?, inicio?/fin? (solo video)}: pone la capa ENCIMA donde y cuando quieras, pueden solaparse; "
                 "agregar_texto {texto, pos, dur, posicion:arriba|centro|abajo, tamano?, color?}; "
                 "recortar {clip, inicio?, fin?} (segundos del ARCHIVO; no en imágenes/GIFs: usá dur); "
                 "dividir {clip, en} (`en` = segundo de la LÍNEA DE TIEMPO; no en capas); "
                 "mover {clip, indice} (V1) o {clip, pos} (resto); borrar {clip}; "
                 "ajustar {clip, ...}: en V1 volumen 0-4, velocidad 0.25-4, brillo -0.5..0.5, contraste 0.5-2, saturacion 0-3, zoom 1-3, fundido_in/out, "
                 "desenfoque 0-20, nitidez 0-2, vineta 0-1, espejo true/false, rotacion 0|90|180|270, filtro (ninguno|bn|sepia|calido|frio|vintage|contraste_fuerte), "
                 "transicion (con la que ENTRA el clip: ninguna|fundido|fundido_negro|fundido_blanco|disolver|deslizar_izq|deslizar_der|deslizar_arriba|deslizar_abajo|limpiar|circulo|zoom|pixelar|radial) y transicion_dur 0.2-3; "
                 "en capas x, y, escala, opacidad, rotacion, pos, dur, fundidos; en audio volumen, pos, fundidos; en texto texto, pos, dur, posicion, tamano, color; "
                 "formato {formato}; renombrar {nombre}. "
                 "Pasá `rev_base` (la `rev` que leíste) para no pisar un cambio del usuario: si cambió, se rechaza y hay que volver a leer."),
    parameters=_obj({"proyecto": _PROYECTO,
                     "operaciones": {"type": "array", "items": {"type": "object", "properties": {"op": {"type": "string", "enum": sorted(video_proyecto.OPERACIONES)}}, "required": ["op"],
                                                                   "additionalProperties": True}, "description": "De 1 a 50 operaciones, en orden."},
                     "rev_base": {"type": "integer", "description": "Revisión del proyecto que leíste."}}, ["proyecto", "operaciones"]))
def video_proyecto_editar(proyecto: str, operaciones: list, rev_base: int | None = None) -> dict:
    return _correr("video_proyecto_editar", {"proyecto": proyecto, "operaciones": operaciones, "rev_base": rev_base},
                   lambda: video_proyecto.aplicar(proyecto, operaciones, "ia", rev_base))


@register_tool(
    name="video_proyecto_renderizar",
    description=("Genera el video del proyecto como archivo NUEVO en salida/ (un solo ffmpeg). `preview` es una versión liviana a mitad de resolución "
                 "para mirar rápido; `final` es la de calidad. Los originales no se tocan."),
    parameters=_obj({"proyecto": _PROYECTO, "calidad": {"type": "string", "enum": ["final", "preview"], "description": "Default final."}}, ["proyecto"]))
def video_proyecto_renderizar(proyecto: str, calidad: str = "final") -> dict:
    return _correr("video_proyecto_renderizar", {"proyecto": proyecto, "calidad": calidad}, lambda: video_proyecto.renderizar(proyecto, calidad))
