"""Analítica: métricas de Instagram y recomendaciones de qué repetir. Solo lectura de la cuenta; nada sale al mundo.

`sincronizar_metricas` (automático: solo lee) guarda una foto de la cuenta y de las últimas publicaciones. Las recomendaciones son
POR REGLAS sobre esos números (tasa de interacción = (me gusta + comentarios + guardados + compartidos) / alcance, formato que
mejor rinde, mejor día y hora) y dicen cuántos datos hay detrás: con pocas publicaciones avisan que es poco para concluir.
Sin cuenta conectada (`IG_*`) no hay nada que leer y lo dice; los datos simulados vienen marcados como tales.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from raphael_core import Action, ActionError, Cook, Health

from .. import entorno
from ..adapters import ServicioError
from ..config import contenido_config

MIN_PARA_CONCLUIR = 5
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def engagement(p: dict) -> float | None:
    reach = p.get("reach")
    if not reach:
        return None
    total = sum(p.get(k) or 0 for k in ("like_count", "comments_count", "saved", "shares"))
    return round(total / reach, 4)


def _when(p: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(p["timestamp"]).replace("Z", "+00:00").replace("+0000", "+00:00"))
    except (KeyError, ValueError):
        return None


def summarize(snap: dict) -> dict:
    rows = []
    for p in snap.get("publicaciones", []):
        rows.append({**{k: p.get(k) for k in ("id", "permalink", "media_product_type", "timestamp", "like_count", "comments_count",
                                                "reach", "saved", "shares")}, "interaccion": engagement(p)})
    con = [r for r in rows if r["interaccion"] is not None]
    mean = round(sum(r["interaccion"] for r in con) / len(con), 4) if con else None
    return {"cuenta": snap.get("cuenta"), "publicaciones": len(rows), "con_alcance": len(con), "interaccion_media": mean,
            "mejores": sorted(con, key=lambda r: r["interaccion"], reverse=True)[:3],
            "simulado": bool(snap.get("simulado"))}


def recommend(snap: dict) -> dict:
    posts = [p for p in snap.get("publicaciones", []) if engagement(p) is not None]
    out: list[str] = []
    if not posts:
        return {"recomendaciones": ["Todavía no hay publicaciones con alcance medido: sincronizá las métricas después de publicar."],
                "datos": 0, "origen": "reglas", "simulado": bool(snap.get("simulado"))}
    fmt: dict[str, list[float]] = {}
    for p in posts:
        fmt.setdefault(p.get("media_product_type") or p.get("media_type") or "?", []).append(engagement(p))
    ranking = sorted(((sum(v) / len(v), k, len(v)) for k, v in fmt.items()), reverse=True)
    top = max(posts, key=engagement)
    out.append(f"Lo que mejor funcionó: {top.get('permalink') or top['id']} (interacción {engagement(top):.1%}). Repetí ese estilo.")
    if len(ranking) > 1:
        out.append(f"Por formato, rinde más {ranking[0][1]} ({ranking[0][0]:.1%} de media, {ranking[0][2]} publicaciones) "
                   f"que {ranking[-1][1]} ({ranking[-1][0]:.1%}).")
    if len(posts) >= MIN_PARA_CONCLUIR:
        by_day: dict[int, list[float]] = {}
        for p in posts:
            w = _when(p)
            if w:
                by_day.setdefault(w.weekday(), []).append(engagement(p))
        if by_day:
            best = max(by_day.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
            out.append(f"El mejor día fue el {DIAS[best[0]]} ({sum(best[1]) / len(best[1]):.1%} de media).")
    else:
        out.append(f"Hay {len(posts)} publicaciones medidas: es poco para hablar de mejores días u horarios (hacen falta {MIN_PARA_CONCLUIR} o más).")
    return {"recomendaciones": out, "datos": len(posts), "origen": "reglas", "simulado": bool(snap.get("simulado"))}


class Analitica(Cook):
    name = "analitica"
    version = "2.0.0"
    description = "Métricas de Instagram y recomendaciones de qué repetir (por reglas, con la cantidad de datos a la vista)."
    commands = {"resumen": "Resumen de la última foto de métricas", "recomendaciones": "Qué repetir, según las métricas",
                "historial": "Fotos de métricas guardadas"}

    def start(self, ctx) -> None:
        self.cfg = contenido_config(ctx.config)
        self.met = entorno.build(self.cfg).metricas

    async def execute(self, action: Action, ctx) -> str | None:
        if action.type != "sincronizar_metricas":
            raise ActionError(f"analitica no ejecuta '{action.type}'")
        limit = action.data.get("limite", 25)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ActionError("«limite» entre 1 y 100.")
        try:
            snap = await asyncio.to_thread(self.met.snapshot, limit)
        except ServicioError as exc:
            raise ActionError(str(exc)) from None
        key = ctx.now().isoformat(timespec="seconds")
        ctx.shared.put("fotos", key, {"cuando": key, **snap})
        ctx.publish("metricas.sincronizadas", {"cuando": key, "publicaciones": len(snap["publicaciones"]), "simulado": bool(snap.get("simulado"))})
        notas = f" Avisos de Meta: {'; '.join(snap['avisos'])}." if snap.get("avisos") else ""
        sim = " (DATOS SIMULADOS, no son de tu cuenta)" if snap.get("simulado") else ""
        return f"Métricas sincronizadas{sim}: {len(snap['publicaciones'])} publicaciones.{notas}"

    def _last(self, ctx) -> dict:
        fotos = ctx.shared.list("fotos")
        if not fotos:
            raise ActionError("Todavía no hay métricas guardadas: pedí «sincronizar_metricas» primero.")
        return max(fotos, key=lambda f: f["cuando"])

    def command(self, name: str, data: dict, ctx):
        if name == "resumen":
            return summarize(self._last(ctx))
        if name == "recomendaciones":
            return recommend(self._last(ctx))
        if name == "historial":
            return [{"cuando": f["cuando"], "publicaciones": len(f["publicaciones"]), "simulado": bool(f.get("simulado"))}
                    for f in sorted(ctx.shared.list("fotos"), key=lambda f: f["cuando"])][-30:]
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True, {"real": "métricas conectadas", "mock": "métricas SIMULADAS",
                             "sin_clave": "sin cuenta de Instagram: no hay métricas que leer"}[self.met.mode])
