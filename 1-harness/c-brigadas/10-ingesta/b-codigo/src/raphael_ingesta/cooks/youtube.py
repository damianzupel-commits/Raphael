"""YouTube: ingiere un video o una lista, y vigila listas para ingerir solos los videos nuevos.

Portado de `youtube_playlist.py` y `playlist_watcher.py` (JarvisRemote). Cambios: un video por acción y la lista se
encola (antes una corrida hacía todo junta); el vigilante es `tick` + `vigilar` en vez de una tarea suelta; el LLM, el
vault y yt-dlp son piezas enchufables; el resumen cae a reglas sin modelo."""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Message, Reply
from raphael_core.text_es import normalize

from ..adapters.youtube import is_list_url, video_id_of
from ..base import Ingester
from ..model import SourceError

URL = re.compile(r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/\S+", re.I)
WATCH = re.compile(r"\b(vigila\w*|segui\w*|monitorea\w*|cada vez que)\b")


class YouTube(Ingester):
    source = "youtube"
    name = "youtube"
    version = "2.0.0"
    description = "Ingiere videos y listas de YouTube al vault (con su transcripción) y vigila listas."

    def wants(self, text: str) -> float:
        return 0.9 if URL.search(text or "") else 0.0

    def handle(self, msg: Message, ctx):
        m = URL.search(msg.text or "")
        if m is None or self.interest(msg, ctx) == 0:
            return None
        url = m.group(0)
        if is_list_url(url):
            if WATCH.search(normalize(msg.text)):
                return Reply(
                    "Dale. Si la vigilo, cada tanto la reviso y sumo sola los videos nuevos; lo apruebo con vos primero.",
                    [Action("vigilar", {"ref": url}, f"Vigilar la lista de YouTube {url}")],
                )
            return Reply(
                "Dale, miro la lista y encolo los videos que todavía no tengo.",
                [Action("ingerir_lista", {"url": url}, f"Ingerir la lista de YouTube {url}")],
            )
        if video_id_of(url):
            return Reply("Dale, lo ingiero.", [Action("ingerir_video", {"ref": url}, f"Ingerir el video de YouTube {url}")])
        return Reply("Ese link de YouTube no lo entiendo: pasame un video o una lista.")

    def check_ref(self, ref: str) -> str:
        if not is_list_url(ref):
            raise ActionError("solo se vigilan listas o canales de YouTube")
        return ref.strip()

    def fetch_ref(self, ctx, ref: str):
        return self.get_adapter(ctx).fetch_video(ref)

    async def scan(self, ctx, ref: str):
        import asyncio

        entries = await asyncio.to_thread(self.get_adapter(ctx).list_playlist, ref)
        return self.enqueue(ctx, entries, self.cfg(ctx).max_per_list)

    async def execute_source(self, action: Action, ctx):
        d = action.data
        if action.type == "ingerir_video":
            vid = video_id_of(str(d.get("ref", "")))
            if vid is None:
                raise ActionError("no es un video de YouTube")
            return await self.ingest_now(ctx, vid, vid, lambda: self.get_adapter(ctx).fetch_video(vid), bool(d.get("force")))
        if action.type == "ingerir_lista":
            url = str(d.get("url", ""))
            if not is_list_url(url):
                raise ActionError("no es una lista ni un canal de YouTube")
            try:
                queued, known, waiting = await self.scan(ctx, url)
            except SourceError as exc:
                return f"No pude leer la lista: {exc.reason}."
            return (
                f"Encolé {queued} videos nuevos (ya tenía {known}, {waiting} ya esperaban). Los voy procesando de a pocos."
                if queued
                else f"No hay videos nuevos (ya tenía {known})."
            )
        return await super().execute_source(action, ctx)
