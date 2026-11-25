"""Video: edición con ffmpeg (carpeta fija, original intacto, un trabajo a la vez) y proyectos con línea de tiempo.

Portado de `brigades/video.py`, `app/video_edit.py`, `app/video_proyecto.py` y `app/tools/video_edit.py` de JarvisRemote. Antes
eran los "modos" de una brigada con ayudantes; ahora son acciones de un cocinero:
  - `editar_video`        una operación sobre un archivo (recortar, unir, subtítulos, vertical…) -> archivo NUEVO en salida/ (automático)
  - `proyecto_crear` / `proyecto_editar` / `proyecto_renderizar`   el editor de proyectos (pistas, capas, texto, audio) (automático)
  - `grabar_pantalla`     solo en la PC y con aprobación: puede mostrar datos privados
Las operaciones pesadas se encolan (`trabajos`). Whisper y ffmpeg se inyectan: sin ellos instalados, el cocinero avisa qué falta.
"""

from __future__ import annotations

import asyncio
import inspect

from raphael_core import Action, ActionError, Health

from .. import entorno
from ..comun import CocineroConTrabajos, edition_of, need_str, short
from ..config import contenido_config
from ..video import edicion as ve
from ..video import proyecto as vp

OPS = {name: getattr(ve, name) for name in (
    "recortar", "unir", "convertir", "quitar_silencios", "audio", "transcribir", "subtitular", "vertical", "transicion", "velocidad",
    "color", "texto", "superponer", "fundidos", "rotar", "encuadrar", "estabilizar", "pantalla_verde", "escenas", "gif", "captura",
    "reversa")}


def _bind(fn, args: dict, what: str) -> dict:
    """Valida los argumentos contra la firma de la operación: ni de más ni de menos."""
    sig = inspect.signature(fn)
    extra = sorted(set(args) - set(sig.parameters))
    if extra:
        raise ActionError(f"{what}: argumentos que no existen: {', '.join(extra)}. Admite: {', '.join(sig.parameters)}.")
    try:
        sig.bind(**args)
    except TypeError as exc:
        raise ActionError(f"{what}: {exc}") from None
    return args


class Video(CocineroConTrabajos):
    name = "video"
    version = "2.0.0"
    description = "Edita video con ffmpeg (carpeta fija, original intacto), arma proyectos con línea de tiempo y graba la pantalla (solo en la PC)."
    commands = {**CocineroConTrabajos.commands, "listar": "Archivos de la carpeta de video", "info": "Datos de un archivo {'archivo'}",
                "proyectos": "Proyectos de edición", "proyecto": "Un proyecto {'proyecto'}", "operaciones": "Operaciones de edición disponibles"}

    def start(self, ctx) -> None:
        super().start(ctx)
        cfg = contenido_config(ctx.config)
        self.adapters = entorno.build(cfg)
        entorno.video_setup(cfg, self.adapters)

    # --- acciones ------------------------------------------------------------------------------------------------------
    async def execute(self, action: Action, ctx) -> str | None:
        d = action.data
        t = action.type
        if t == "editar_video":
            op = need_str(d, "op", max_len=40)
            if op not in OPS:
                raise ActionError(f"No conozco la operación «{op}». Disponibles: {', '.join(sorted(OPS))}.")
            args = _bind(OPS[op], dict(d.get("args") or {}), op)
            return self.enqueue(ctx, "video", f"{op}: {short(args.get('archivo') or args.get('archivos') or '')}", lambda: OPS[op](**args))
        if t == "proyecto_crear":
            r = await asyncio.to_thread(self._proj, vp.crear, need_str(d, "nombre", max_len=80), d.get("formato", "vertical"))
            return f"Proyecto «{r['nombre']}» creado (id {r['id']}, formato {r.get('formato')})."
        if t == "proyecto_editar":
            pid = need_str(d, "proyecto", max_len=60)
            por = "ia" if action.origin.value != "owner" else "usuario"
            if d.get("deshacer"):
                r = await asyncio.to_thread(self._proj, vp.deshacer, pid, por)
            elif d.get("rehacer"):
                r = await asyncio.to_thread(self._proj, vp.rehacer, pid, por)
            else:
                ops = d.get("operaciones")
                if not isinstance(ops, list) or not ops:
                    raise ActionError("Faltan las «operaciones» (una lista) o «deshacer»/«rehacer».")
                r = await asyncio.to_thread(self._proj, vp.aplicar, pid, ops, por, d.get("rev_base"))
            p = r.get("proyecto", r)
            return f"Proyecto {pid} actualizado (revisión {p.get('rev')})."
        if t == "proyecto_renderizar":
            pid = need_str(d, "proyecto", max_len=60)
            calidad = d.get("calidad", "final")
            if calidad not in ("final", "preview"):
                raise ActionError("«calidad» es final o preview.")
            return self.enqueue(ctx, "proyecto", f"render {pid} ({calidad})", lambda: vp.renderizar(pid, calidad))
        if t == "grabar_pantalla":
            if edition_of(ctx) != "personal":
                raise ActionError("Grabar la pantalla solo se hace en la PC de la persona (edición personal), nunca en la nube.")
            args = {k: d[k] for k in ("duracion", "nombre", "ventana", "escritorio_completo") if k in d}
            _bind(ve.grabar_pantalla, args, "grabar_pantalla")
            return self.enqueue(ctx, "video", "grabar pantalla", lambda: ve.grabar_pantalla(**args))
        raise ActionError(f"video no ejecuta '{t}'")

    @staticmethod
    def _proj(fn, *args):
        try:
            return fn(*args)
        except (vp.ProyectoError, ve.VideoError) as exc:
            raise ActionError(str(exc)) from None

    # --- lectura -------------------------------------------------------------------------------------------------------
    def command(self, name: str, data: dict, ctx):
        try:
            if name == "listar":
                return ve.listar()
            if name == "info":
                return ve.info(ve.resolver(need_str(data, "archivo", max_len=300), ve.VIDEO_EXT | ve.AUDIO_EXT | ve.IMG_EXT))
            if name == "proyectos":
                return vp.listar()
            if name == "proyecto":
                return vp.leer(need_str(data, "proyecto", max_len=60))
            if name == "operaciones":
                return {n: str(inspect.signature(f)) for n, f in sorted(OPS.items())}
        except (vp.ProyectoError, ve.VideoError) as exc:
            raise ActionError(str(exc)) from None
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        if not self.adapters.ffmpeg.available():
            return Health(True, "ffmpeg no está instalado: las ediciones van a avisar (VIDEO_FFMPEG_PATH o winget install Gyan.FFmpeg)")
        return Health(True, f"ffmpeg {'simulado' if not self.adapters.ffmpeg.real else 'listo'}")
