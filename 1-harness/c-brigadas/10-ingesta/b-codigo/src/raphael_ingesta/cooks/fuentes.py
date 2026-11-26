"""Fuentes públicas: papers, noticias y datos de conflicto y economía (OpenAlex, Crossref, GDELT, Fed, FRED, Banco Mundial,
ReliefWeb, UCDP, MIT News, Harvard Gazette). Una búsqueda trae solo título, resumen y metadatos con enlace y crédito, y se vigila
(con aprobación) para que se ingiera sola. Cada pedido es `ficha:consulta`, por ejemplo `openalex:armed conflict`."""

from __future__ import annotations

import asyncio

from raphael_core import Action, ActionError, Message, Reply
from raphael_core.text_es import normalize

from ..base import Ingester
from ..fichas import FICHAS, ficha_de
from ..model import SourceError

_ALIAS = {a: f.id for f in FICHAS.values() if f.listo for a in f.alias}
_WATCH_WORDS = ("vigila", "segui", "cada dia", "todos los dias")


def mentioned(text: str) -> str | None:
    t = f" {normalize(text or '')} "
    for alias, fid in sorted(_ALIAS.items(), key=lambda kv: -len(kv[0])):
        if f" {alias} " in t:
            return fid
    return None


class Fuentes(Ingester):
    source = "fuentes"
    name = "fuentes"
    version = "2.0.0"
    description = "Ingiere fuentes públicas (papers, noticias, datos de conflicto y economía) con su crédito, y las vigila."

    def wants(self, text: str) -> float:
        t = normalize(text or "")
        return (
            0.7
            if mentioned(text) and any(w in t for w in ("busca", "trae", "ingeri", "vigila", "segui", "ultimos", "nuevos"))
            else 0.0
        )

    def query_for(self, ctx, fid: str) -> str:
        return self.cfg(ctx).fuentes_consultas.get(fid) or FICHAS[fid].consulta

    def handle(self, msg: Message, ctx):
        fid = mentioned(msg.text or "")
        if fid is None or self.interest(msg, ctx) == 0:
            return None
        ref = f"{fid}:{self.query_for(ctx, fid)}"
        if any(w in normalize(msg.text) for w in _WATCH_WORDS):
            return Reply(
                f"Dale. Si vigilo {FICHAS[fid].nombre}, cada tanto busco y sumo sola lo nuevo; lo apruebo con vos primero.",
                [Action("vigilar", {"ref": ref}, f"Vigilar {FICHAS[fid].nombre}: {ref.split(':', 1)[1]}")],
            )
        return Reply(
            f"Dale, busco lo más nuevo en {FICHAS[fid].nombre}.",
            [Action("buscar_fuente", {"ref": ref}, f"Buscar en {FICHAS[fid].nombre}: {ref.split(':', 1)[1]}")],
        )

    def check_ref(self, ref: str) -> str:
        try:
            ficha, _ = ficha_de(ref)
        except ValueError as exc:
            raise ActionError(str(exc)) from None
        if not ficha.listo:
            raise ActionError(f"{ficha.nombre} todavía no tiene adaptador")
        return ref.strip()

    async def scan(self, ctx, ref: str):
        cfg = self.cfg(ctx)
        entries = await asyncio.to_thread(self.get_adapter(ctx).search, ref, cfg.max_per_list)
        return self.enqueue(ctx, entries, cfg.max_per_list)

    async def execute_source(self, action: Action, ctx):
        if action.type == "buscar_fuente":
            ref = self.check_ref(str(action.data.get("ref", "")))
            try:
                queued, known, waiting = await self.scan(ctx, ref)
            except SourceError as exc:
                return f"No pude buscar en {ref.split(':', 1)[0]}: {exc.reason}."
            return (
                f"Encolé {queued} ítems nuevos (ya tenía {known}, {waiting} ya esperaban)."
                if queued
                else f"No hay nada nuevo (ya tenía {known})."
            )
        return await super().execute_source(action, ctx)
