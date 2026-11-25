"""Consolidador y destilador: consolida la memoria («el sueño»), destila lo capturado en episodios y recibe lo que las
otras brigadas quieren que Cerebro recuerde (por evento: ellas NO leen el vault, solo le escriben).

Todo es aditivo y reversible menos `olvidar`, que pide aprobación. Sin modelo local no escribe síntesis y lo avisa.
"""

from __future__ import annotations

from pathlib import Path

from raphael_core import Action, ActionError, Cook, Origin

from .. import actions
from ..brain import Brain
from ..episodes import recall_auto, recall_query, render


def _inside(root, ruta) -> bool:
    try:
        Path(str(ruta)).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


class Consolidator(Cook):
    name = "consolidador"
    version = "2.0.0"
    description = "Consolida la memoria, destila episodios y guarda lo que capturan las otras brigadas."
    commands = {
        "consolidar_vista": "Qué consolidaría, sin escribir nada",
        "consolidar": "Consolidar notas relacionadas (escribe síntesis; pide aprobación) {'max_clusters'}",
        "guardar": "Guardar una nota {'title', 'content', 'tags', 'category'}",
        "reindexar": "Recalcular los embeddings de todas las notas",
        "episodios": "Episodios recientes {'tema', 'max'}",
        "verificar_registro": "Verificar la cadena de hashes del registro de memoria",
        "olvidar": "Olvidar un episodio o una nota {'kind': 'episodio'|'nota', 'id'} (pide aprobación)",
        "exportar": "Exportar el vault a un .zip {'destino'} (pide aprobación)"}

    def on_event(self, event: str, data: dict, ctx) -> None:
        if event == "memoria.captura":
            # contenido de terceros: es DATO; se guarda como nota (firmada jarvis, con su brigada de origen), no se interpreta
            if isinstance(data, dict) and data.get("title") and data.get("content"):
                ctx.request(Action("guardar_nota", {k: data.get(k) for k in ("title", "content", "tags", "source")}
                                   | {"brigade": data.get("brigada") or "desconocida"},
                                   f"Guardar captura de {data.get('brigada') or 'una brigada'}: {str(data['title'])[:80]}",
                                   origin=Origin.THIRD_PARTY))
        elif event == "nota.ingerida" and isinstance(data, dict):
            # Ingesta (pieza 10) avisa de cada nota. Si ya cayó en el vault compartido solo se indexa; si no, se guarda
            # una copia con su origen. El contenido es DATO de terceros.
            brain = Brain.from_ctx(ctx)
            ruta = data.get("ruta")
            if ruta and _inside(brain.vault.root, ruta):
                ctx.request(Action("reindexar", {"ruta": str(ruta)}, f"Indexar nota ingerida: {str(data.get('titulo') or ruta)[:80]}",
                                   origin=Origin.THIRD_PARTY))
            else:
                title, content = data.get("titulo") or data.get("title"), data.get("contenido") or data.get("content")
                if title and content:
                    ctx.request(Action("guardar_nota", {"title": title, "content": content, "brigade": "ingesta",
                                                        "source": data.get("fuente") or data.get("origen"),
                                                        "tags": [str(data["categoria"])] if data.get("categoria") else []},
                                       f"Guardar nota ingerida: {str(title)[:80]}", origin=Origin.THIRD_PARTY))
        elif event == "memoria.turno":
            cfg = Brain.from_ctx(ctx).cfg
            if cfg.episodes.enabled and isinstance(data, dict) and data.get("history"):
                ctx.request(Action("registrar_episodio", {k: data.get(k) for k in ("conv_id", "history", "dominio")},
                                   "Registrar el turno en la memoria episódica", origin=Origin.SYSTEM))

    def command(self, name: str, data: dict, ctx):
        if name == "consolidar_vista":
            return Brain.from_ctx(ctx).consolidate(dry_run=True, max_clusters=data.get("max_clusters"))
        if name == "consolidar":
            return actions.request(ctx, "consolidar", {"max_clusters": data.get("max_clusters")},
                                   "Consolidar notas relacionadas (escribe notas de síntesis)")
        if name == "guardar":
            return actions.request(ctx, "guardar_nota", {k: data.get(k) for k in ("title", "content", "tags", "category", "author")},
                                   f"Guardar la nota «{str(data.get('title'))[:80]}»")
        if name == "reindexar":
            return actions.request(ctx, "reindexar", {}, "Recalcular los embeddings del vault")
        if name == "episodios":
            brain = Brain.from_ctx(ctx)
            eps = brain.episodes.list()
            if data.get("tema"):
                chosen = recall_query(eps, str(data["tema"]), int(data.get("max", 8)))
            else:
                chosen = recall_auto(eps, ctx.now(), hours=brain.cfg.episodes.recall_window_hours,
                                     max_items=int(data.get("max", 12)))
            return {"texto": render(chosen), "episodios": [e.to_dict() for e in chosen]}
        if name == "verificar_registro":
            return Brain.from_ctx(ctx).episodes.verify()
        if name == "olvidar":
            return actions.request(ctx, "olvidar", {"kind": data.get("kind"), "id": data.get("id")},
                                   f"Olvidar {data.get('kind')} {data.get('id')}")
        if name == "exportar":
            if not data.get("destino"):
                raise ActionError("falta 'destino' (ruta del .zip)")
            return actions.request(ctx, "exportar_vault", {"destino": data["destino"]}, "Exportar el vault a un .zip")
        return super().command(name, data, ctx)

    def execute(self, action, ctx):
        return actions.execute(ctx, action)
