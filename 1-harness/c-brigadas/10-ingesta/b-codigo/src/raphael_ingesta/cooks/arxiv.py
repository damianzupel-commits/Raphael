"""arXiv: ingiere un paper por id o URL, o busca los más nuevos de unas categorías (y los vigila).

Portado de `arxiv_source.py` (JarvisRemote). La búsqueda ya trae el abstract: no hay un pedido por paper."""

from __future__ import annotations

import asyncio
import re

from raphael_core import Action, ActionError, Message, Reply
from raphael_core.text_es import normalize

from ..adapters.arxiv import arxiv_id_of
from ..base import Ingester
from ..model import SourceError

URL = re.compile(r"(?:https?://)?arxiv\.org/\S+|\barxiv:\s*\d{4}\.\d{4,5}\b", re.I)
SEARCH = re.compile(r"\b(papers?|articulos?)\b.*\barxiv\b|\barxiv\b.*\b(nuevos|ultimos|busca\w*)\b")
WATCH = re.compile(r"\b(vigila\w*|segui\w*|cada dia|todos los dias)\b")


class Arxiv(Ingester):
    source = "arxiv"
    name = "arxiv"
    version = "2.0.0"
    description = "Ingiere papers de arXiv (por id o por búsqueda de categorías) y vigila búsquedas."

    def wants(self, text: str) -> float:
        t = normalize(text or "")
        return 0.9 if URL.search(text or "") else 0.7 if SEARCH.search(t) or ("arxiv" in t and WATCH.search(t)) else 0.0

    def handle(self, msg: Message, ctx):
        if self.interest(msg, ctx) == 0:
            return None
        m = URL.search(msg.text or "")
        aid = arxiv_id_of(m.group(0).rstrip(").,;")) if m else None
        if aid:
            return Reply("Dale, traigo el paper.", [Action("ingerir_paper", {"ref": aid}, f"Ingerir el paper arXiv {aid}")])
        query = self.cfg(ctx).arxiv_query
        if WATCH.search(normalize(msg.text)):
            return Reply(
                "Dale. Si la vigilo, cada tanto busco y sumo sola los papers nuevos; lo apruebo con vos primero.",
                [Action("vigilar", {"ref": query}, f"Vigilar arXiv: {query}")],
            )
        return Reply(
            "Dale, busco los más nuevos de tus categorías.",
            [Action("buscar_arxiv", {"query": query}, f"Buscar en arXiv: {query}")],
        )

    def check_ref(self, ref: str) -> str:
        if not ref.strip():
            raise ActionError("falta la búsqueda")
        return ref.strip()

    def fetch_ref(self, ctx, ref: str):
        return self.get_adapter(ctx).fetch(ref)

    async def scan(self, ctx, ref: str):
        cfg = self.cfg(ctx)
        entries = await asyncio.to_thread(self.get_adapter(ctx).search, ref, cfg.max_per_list)
        return self.enqueue(ctx, entries, cfg.max_per_list)

    async def execute_source(self, action: Action, ctx):
        d = action.data
        if action.type == "ingerir_paper":
            aid = arxiv_id_of(str(d.get("ref", "")))
            if aid is None:
                raise ActionError("no es un id ni una dirección de arXiv")
            return await self.ingest_now(ctx, aid, aid, lambda: self.get_adapter(ctx).fetch(aid), bool(d.get("force")))
        if action.type == "buscar_arxiv":
            try:
                queued, known, waiting = await self.scan(ctx, str(d.get("query") or self.cfg(ctx).arxiv_query))
            except SourceError as exc:
                return f"No pude buscar en arXiv: {exc.reason}."
            return (
                f"Encolé {queued} papers nuevos (ya tenía {known}, {waiting} ya esperaban)."
                if queued
                else f"No hay papers nuevos (ya tenía {known})."
            )
        return await super().execute_source(action, ctx)
