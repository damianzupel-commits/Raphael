"""Web: ingiere una página pública al vault. Solo sitios públicos (nunca la red local ni localhost) y solo lectura.

Portado de la tool `obsidian_ingerir_web` de JarvisRemote (su código no vino en la referencia: se escribió de nuevo con el
mismo contrato: URL y fecha de origen en cada nota)."""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Message, Reply

from ..adapters.web import web_id
from ..base import Ingester

URL = re.compile(r"https?://\S+", re.I)
OTHER = re.compile(r"(youtube\.com|youtu\.be|arxiv\.org)", re.I)


class Web(Ingester):
    source = "web"
    name = "web"
    version = "2.0.0"
    description = "Ingiere páginas web públicas al vault, guardando su origen."

    def wants(self, text: str) -> float:
        m = URL.search(text or "")
        return 0.0 if not m or OTHER.search(m.group(0)) else 0.6

    def handle(self, msg: Message, ctx):
        m = URL.search(msg.text or "")
        if m is None or self.interest(msg, ctx) == 0:
            return None
        url = m.group(0).rstrip(").,;")
        return Reply("Dale, leo la página y la guardo.", [Action("ingerir_pagina", {"url": url}, f"Ingerir la página {url}")])

    def fetch_ref(self, ctx, ref: str):
        return self.get_adapter(ctx).fetch(ref)

    async def execute_source(self, action: Action, ctx):
        if action.type == "ingerir_pagina":
            url = str(action.data.get("url", "")).strip()
            if not url:
                raise ActionError("falta la dirección")
            return await self.ingest_now(
                ctx, web_id(url), url, lambda: self.get_adapter(ctx).fetch(url), bool(action.data.get("force"))
            )
        return await super().execute_source(action, ctx)
