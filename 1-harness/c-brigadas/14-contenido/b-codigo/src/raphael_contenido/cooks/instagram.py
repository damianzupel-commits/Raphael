"""Instagram: deja los videos como publicación PENDIENTE con su texto y publica solo tras la aprobación de una persona.

Portado de `app/publicaciones.py` de JarvisRemote. Dos pasos, como allá:
  1. `preparar_publicacion` (automático): guarda video + texto + huella (SHA-256 de los dos) y pide la aprobación (`publicar_instagram`).
     No habla con Instagram.
  2. `publicar_instagram` (aprobación, sale al mundo, sin vuelta atrás): publica como Reel. Si el video o el texto cambiaron después
     de preparar, la huella no coincide y no se publica. Se intenta UNA vez: si falla queda en `fallo` con el motivo (y la clave
     tachada); si se cortó a la mitad, queda `fallo` y hay que mirar en Instagram antes de reintentar (no se duplica solo).
Sin `IG_USER_ID` / `IG_ACCESS_TOKEN` todo anda menos publicar: la publicación queda pendiente y se avisa qué falta.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

from raphael_core import Action, ActionError, Health

from .. import entorno
from ..adapters import ServicioError
from ..comun import CocineroConTrabajos, need_str, new_id, short
from ..config import contenido_config
from ..video import edicion as ve

ESTADOS = ("pendiente", "publicando", "publicada", "fallo", "descartada")


def fingerprint(path: Path, text: str) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    h.update(b"\x00" + text.encode("utf-8"))
    return h.hexdigest()


class Instagram(CocineroConTrabajos):
    name = "instagram"
    version = "2.0.0"
    description = "Prepara publicaciones de Instagram (Reels) y las publica solo con aprobación."
    commands = {**CocineroConTrabajos.commands, "publicaciones": "Publicaciones {'estado'?}", "publicacion": "Una publicación {'id'}",
                "estado": "Modo de la conexión con Instagram (real, simulado o sin clave)"}

    def start(self, ctx) -> None:
        super().start(ctx)
        self.cfg = contenido_config(ctx.config)
        self.adapters = entorno.build(self.cfg)
        self.ig = self.adapters.instagram
        entorno.video_setup(self.cfg, self.adapters)
        for r in ctx.shared.list("publicaciones", estado="publicando"):   # se cortó a la mitad: NO se reintenta solo
            r.update(estado="fallo", motivo="Raphael se reinició mientras se publicaba: mirá en Instagram si salió antes de reintentar.")
            ctx.shared.put("publicaciones", r["id"], r)

    # --- acciones ------------------------------------------------------------------------------------------------------
    async def execute(self, action: Action, ctx) -> str | None:
        t, d = action.type, action.data
        if t == "preparar_publicacion":
            return await self._prepare(d, ctx)
        if t == "publicar_instagram":
            return await self._publish(need_str(d, "id", max_len=40), ctx)
        if t == "descartar_publicacion":
            rec = self._load(need_str(d, "id", max_len=40), ctx)
            if rec["estado"] != "pendiente":
                raise ActionError(f"Solo se descarta una pendiente (esta está {rec['estado']}).")
            rec["estado"] = "descartada"
            ctx.shared.put("publicaciones", rec["id"], rec)
            return f"Publicación {rec['id']} descartada."
        raise ActionError(f"instagram no ejecuta '{t}'")

    async def _prepare(self, d: dict, ctx) -> str:
        text = d.get("texto")
        if not text and d.get("copy_id"):
            copy = ctx.shared.get("copys", str(d["copy_id"]))
            if not copy:
                raise ActionError(f"No existe el copy {d['copy_id']}.")
            text = copy.get("texto")
        if not isinstance(text, str) or not text.strip():
            raise ActionError("Falta el texto (la descripción) de la publicación.")
        text = text.strip()
        if len(text) > self.cfg.instagram.max_caption:
            raise ActionError(f"El texto supera los {self.cfg.instagram.max_caption} caracteres que admite Instagram.")
        tags = re.findall(r"(?<!\w)#\w+", text)
        if len(tags) > self.cfg.instagram.max_hashtags:
            raise ActionError(f"Tiene {len(tags)} hashtags y Instagram admite hasta {self.cfg.instagram.max_hashtags}.")
        try:
            path = ve.resolver(need_str(d, "archivo", max_len=300), {".mp4", ".mov"})
            info = await asyncio.to_thread(ve.info, path)
            if not info.get("duracion_s"):
                raise ve.VideoError("No pude leer la duración del video.")
            fp = await asyncio.to_thread(fingerprint, path, text)
        except ve.VideoError as exc:
            raise ActionError(str(exc)) from None
        rec = {"id": new_id(), "archivo": path.name, "path": str(path), "texto": text, "duracion_s": info["duracion_s"], "huella": fp,
               "estado": "pendiente", "creada": ctx.now().isoformat(timespec="seconds"), "copy_id": d.get("copy_id")}
        ctx.shared.put("publicaciones", rec["id"], rec)
        ctx.publish("publicacion.preparada", {"id": rec["id"], "archivo": rec["archivo"]})
        # Legales (pieza 16) revisa los textos antes de que salgan: se avisa por el bus, sin importar la brigada.
        ctx.publish("revision.pedida", {"texto": text, "origen": "contenido", "tipo": "publicacion_instagram", "id": rec["id"]})
        res = await ctx.arequest(Action("publicar_instagram", {"id": rec["id"]},
                                        f"Publicar en Instagram «{short(text, 70)}» ({path.name}, {info['duracion_s']} s)"))
        if res.get("state") == "pending":
            return (f"Publicación {rec['id']} preparada: NO se publicó nada. Quedó pendiente de aprobación (pendiente #{res['id']}): "
                    f"revisá el video y el texto y aprobala para que salga.")
        if res.get("state") == "error":
            return f"Publicación {rec['id']} preparada, pero no pude pedir la aprobación: {res.get('error')}"
        return f"Publicación {rec['id']} preparada ({res.get('state')})."

    def _load(self, pid: str, ctx) -> dict:
        rec = ctx.shared.get("publicaciones", pid)
        if not rec:
            raise ActionError(f"No existe la publicación {pid}.")
        return rec

    async def _publish(self, pid: str, ctx) -> str:
        rec = self._load(pid, ctx)
        if rec["estado"] != "pendiente":
            raise ActionError(f"La publicación está {rec['estado']}: solo se aprueba una pendiente.")
        path = Path(rec["path"])
        if not path.is_file() or await asyncio.to_thread(fingerprint, path, rec["texto"]) != rec["huella"]:
            raise ActionError("El video o el texto cambiaron después de prepararla: preparala de nuevo.")
        if self.ig.mode == "sin_clave":
            raise ActionError("Faltan IG_USER_ID e IG_ACCESS_TOKEN (cuenta profesional de Instagram). La publicación sigue pendiente.")
        ctx.publish("revision.pedida", {"texto": rec["texto"], "origen": "contenido", "tipo": "publicacion_instagram", "id": pid})
        rec["estado"] = "publicando"
        ctx.shared.put("publicaciones", pid, rec)
        space, clock = ctx.shared, ctx.now

        def job() -> dict:
            cur = space.get("publicaciones", pid) or rec
            try:
                out = self.ig.publish_reel(path, rec["texto"])
            except ServicioError as exc:   # una sola vez: no se reintenta solo
                cur.update(estado="fallo", motivo=str(exc)[:400])
                space.put("publicaciones", pid, cur)
                raise
            cur.update(estado="publicada", publicada=clock().isoformat(timespec="seconds"), media_id=out["media_id"],
                       simulado=bool(out.get("simulado")))
            space.put("publicaciones", pid, cur)
            return {"id": pid, "media_id": out["media_id"], "simulado": bool(out.get("simulado"))}

        note = " (SIMULADO: no salió nada a Instagram)" if self.ig.mode == "mock" else ""
        return self.enqueue(ctx, "publicar", f"publicar {rec['archivo']}", job) + note

    # --- eventos y lectura ---------------------------------------------------------------------------------------------
    def on_event(self, event: str, data: dict, ctx) -> None:
        if event == "pendiente.rechazado" and data.get("type") == "publicar_instagram":
            rec = ctx.shared.get("publicaciones", str((data.get("data") or {}).get("id", "")))
            if rec and rec["estado"] == "pendiente":
                rec.update(estado="descartada", motivo=f"rechazada: {data.get('reason') or 'sin motivo'}")
                ctx.shared.put("publicaciones", rec["id"], rec)

    def command(self, name: str, data: dict, ctx):
        if name == "publicaciones":
            return [{k: r.get(k) for k in ("id", "archivo", "texto", "duracion_s", "estado", "creada", "motivo", "media_id", "simulado")}
                    for r in ctx.shared.list("publicaciones") if not data.get("estado") or r.get("estado") == data["estado"]]
        if name == "publicacion":
            return self._load(need_str(data, "id", max_len=40), ctx)
        if name == "estado":
            return {"modo": self.ig.mode}
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True, {"real": "Instagram conectado", "mock": "Instagram SIMULADO",
                             "sin_clave": "Instagram sin clave: se puede preparar, no publicar"}[self.ig.mode])
