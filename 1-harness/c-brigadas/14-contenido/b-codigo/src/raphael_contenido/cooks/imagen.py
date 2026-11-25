"""Imagen generativa: imágenes (Flux.1 Schnell) y videos cortos (Wan 2.2) con ComfyUI en la GPU de la PC.

Portado de `app/tools/image_gen.py`, `video_gen.py` y `_comfyui_shared.py` de JarvisRemote. Lo generado se copia a la carpeta de
trabajo de video (`entrada/`, con nombre nuevo: nunca pisa nada) para poder editarlo. Usa la GPU de la persona y no gasta plata,
por eso es automático. En modo simulado deja archivos chicos marcados como simulados. Los prompts son datos de la persona.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from raphael_core import Action, ActionError, Health

from .. import entorno
from ..adapters import ServicioError
from ..comun import CocineroConTrabajos, need_str, short
from ..config import contenido_config
from ..video import edicion as ve


def import_to_folder(src: Path, tag: str) -> Path:
    """Copia lo generado a `entrada/` con un nombre nuevo. Nunca pisa."""
    ve.asegurar_carpetas()
    for n in range(1, 1000):
        dst = ve.entrada_dir() / f"gen-{tag}-{n}{src.suffix.lower()}"
        if not dst.exists():
            shutil.copy2(src, dst)
            return dst
    raise ServicioError("Demasiados archivos generados con el mismo nombre en la carpeta de entrada.")


class Imagen(CocineroConTrabajos):
    name = "imagen"
    version = "2.0.0"
    description = "Genera imágenes y videos cortos con ComfyUI (Flux y Wan) en la GPU de la PC."
    commands = {**CocineroConTrabajos.commands, "generados": "Lo generado hasta ahora", "estado": "¿Está prendido ComfyUI? ¿Real o simulado?"}

    def start(self, ctx) -> None:
        super().start(ctx)
        cfg = contenido_config(ctx.config)
        self.adapters = entorno.build(cfg)
        self.comfy = self.adapters.comfyui
        entorno.video_setup(cfg, self.adapters)

    async def execute(self, action: Action, ctx) -> str | None:
        t, d = action.type, action.data
        prompt = need_str(d, "prompt", max_len=1000)
        space = ctx.shared
        if t == "generar_imagen":
            w, h = d.get("width", 512), d.get("height", 512)
            if any(isinstance(x, bool) or not isinstance(x, int) or not 256 <= x <= 1536 for x in (w, h)):
                raise ActionError("width y height tienen que ser enteros entre 256 y 1536.")

            def make() -> dict:
                r = self.comfy.image(prompt, w, h)
                return self._store(space, "imagen", prompt, r)
            return self.enqueue(ctx, "generar_imagen", f"imagen «{short(prompt, 40)}»", make)
        if t == "generar_video":
            sec = d.get("seconds", 1.0)
            if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not 1 <= sec <= 5:
                raise ActionError("seconds tiene que estar entre 1 y 5.")

            def make_v() -> dict:
                r = self.comfy.video(prompt, float(sec))
                return self._store(space, "video", prompt, r)
            return self.enqueue(ctx, "generar_video", f"video «{short(prompt, 40)}»", make_v)
        raise ActionError(f"imagen no ejecuta '{t}'")

    @staticmethod
    def _store(space, kind: str, prompt: str, r: dict) -> dict:
        src = Path(r["path"])
        if not src.is_file():
            raise ServicioError("ComfyUI terminó pero no encuentro el archivo generado (revisá COMFYUI_OUTPUT_DIR).")
        dst = import_to_folder(src, kind[:3])
        out = {"tipo": kind, "archivo": dst.name, "path": str(dst), "prompt": prompt, "simulado": bool(r.get("simulado"))}
        space.put("generados", str(space.next("generados")), out)
        return out

    def command(self, name: str, data: dict, ctx):
        if name == "generados":
            return ctx.shared.list("generados")[-50:]
        if name == "estado":
            return {"modo": self.comfy.mode, "prendido": self.comfy.up()}
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True, {"real": "ComfyUI configurado", "mock": "ComfyUI SIMULADO",
                             "sin_clave": "ComfyUI sin configurar (COMFYUI_OUTPUT_DIR): no se generan imágenes"}[self.comfy.mode])
