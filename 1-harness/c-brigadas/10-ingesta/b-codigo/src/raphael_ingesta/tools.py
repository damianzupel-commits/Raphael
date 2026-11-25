"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Las que traen contenido de afuera (página, video, paper) solo LEEN: devuelven el texto y no guardan nada. Guardar la nota en
el vault (con su resumen, su origen y el evento `nota.ingerida` que escucha Memoria) lo hace el cocinero de la fuente cuando la
persona se lo pide. Todo lo que traen es dato de un tercero, nunca una instrucción.
"""

from __future__ import annotations

from . import adapters
from .adapters.arxiv import arxiv_id_of
from .adapters.youtube import video_id_of
from .config import SOURCES, settings_of
from .model import Entry, Item, SourceError

TEXTO_MAX = 4000   # lo que el modelo del efímero ve de un texto: alcanza para resumir y no revienta el contexto


def _item(i: Item) -> dict:
    texto = i.text or ""
    return {"ok": True, "fuente": i.source, "titulo": i.title, "origen": i.url, "autores": i.authors, "fecha": i.published,
            "texto": texto[:TEXTO_MAX], "texto_truncado": len(texto) > TEXTO_MAX, "guardado": False}


def _entry(e: Entry) -> dict:
    return {"id": e.source_id, "titulo": e.title, "origen": e.url, "canal": e.channel}


def make_tools(ctx) -> dict:
    cfg = settings_of(ctx.config)
    cache: dict = {}

    def _ad(source: str):
        if source not in cache:
            cache[source] = adapters.make(source, cfg.mode_of(source))
        return cache[source]

    def _seguro(fn):
        try:
            return fn()
        except SourceError as exc:
            return {"ok": False, "motivo": exc.reason, "reintentable": exc.retriable}

    def ingesta_leer_pagina(url: str) -> dict:
        """Lee una página web pública (nunca la red local) y devuelve título y texto. No la guarda."""
        if not str(url).strip():
            return {"ok": False, "motivo": "falta la dirección"}
        return _seguro(lambda: _item(_ad("web").fetch(str(url).strip())))

    def ingesta_leer_video(video: str) -> dict:
        """Trae la transcripción de un video de YouTube (por id o URL). No lo guarda."""
        vid = video_id_of(str(video))
        if vid is None:
            return {"ok": False, "motivo": "no es un video de YouTube: pasame el id o la dirección"}
        return _seguro(lambda: _item(_ad("youtube").fetch_video(vid)))

    def ingesta_leer_paper(ref: str) -> dict:
        """Trae el abstract de un paper de arXiv (por id o URL). No lo guarda."""
        aid = arxiv_id_of(str(ref))
        if aid is None:
            return {"ok": False, "motivo": "no es un id ni una dirección de arXiv"}
        return _seguro(lambda: _item(_ad("arxiv").fetch(aid)))

    def ingesta_buscar_arxiv(query: str = "") -> dict:
        """Busca los papers más nuevos de una búsqueda de arXiv (por defecto la de la config). No encola nada."""
        q = str(query).strip() or cfg.arxiv_query
        return _seguro(lambda: {"ok": True, "busqueda": q,
                                "papers": [_entry(e) for e in _ad("arxiv").search(q, cfg.max_per_list)]})

    def ingesta_notas(limit: int = 20, fuente: str = "") -> list[dict]:
        """Lo ingerido, lo más nuevo primero. `fuente`: youtube, web o arxiv."""
        notas = [n for n in ctx.shared.list("notas") if not fuente or n["fuente"] == fuente]
        notas.reverse()
        notas.sort(key=lambda n: n["fecha"], reverse=True)
        return [{k: n[k] for k in ("id", "titulo", "origen", "fecha", "fuente", "categoria", "por", "veredicto")}
                for n in notas[: min(max(int(limit), 1), 100)]]

    def ingesta_cola() -> list[dict]:
        """Lo que falta procesar."""
        return [{k: j.get(k) for k in ("id", "fuente", "titulo", "estado", "intentos", "no_antes")}
                for j in ctx.shared.list("cola")]

    def ingesta_fallidos() -> list[dict]:
        """Lo que no se pudo ingerir, con el motivo."""
        return ctx.shared.list("fallidos")

    def ingesta_vigiladas() -> list[dict]:
        """Listas y búsquedas que se revisan solas."""
        return ctx.shared.list("vigiladas")

    def ingesta_estado() -> dict:
        """Modo de cada fuente, carpeta del vault y cuánto hay de cada cosa."""
        sh = ctx.shared
        return {"modos": {s: cfg.mode_of(s) for s in SOURCES},
                "vault": cfg.vault_dir or "(sin carpeta: las notas quedan en el almacén de la brigada)",
                "notas": len(sh.list("notas")), "cola": len(sh.list("cola")), "fallidos": len(sh.list("fallidos")),
                "vigiladas": len(sh.list("vigiladas"))}

    return {f.__name__: f for f in (ingesta_leer_pagina, ingesta_leer_video, ingesta_leer_paper, ingesta_buscar_arxiv,
                                    ingesta_notas, ingesta_cola, ingesta_fallidos, ingesta_vigiladas, ingesta_estado)}
