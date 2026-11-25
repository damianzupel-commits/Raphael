"""Lo que comparten los cocineros: la fuente de datos elegida por config y el armado de respuestas en español.

Todo lo que viene de afuera (títulos de noticias, nombres de cámaras o barcos) entra a las respuestas como DATO entre
comillas y ya limpio (`validar.limpiar`): nunca como instrucción.
"""

from __future__ import annotations

from raphael_core import Cook

from .. import fuentes


class CocineroGeo(Cook):
    version = "1.0.0"

    def __init__(self) -> None:
        self._fuentes = None
        self._modo = None

    def fuentes(self, ctx):
        modo = (ctx.config.get("modo") or "real") if isinstance(ctx.config, dict) else "real"
        if self._fuentes is None or modo != self._modo:
            self._fuentes, self._modo = fuentes.elegir(ctx.config), modo
        return self._fuentes


def resumen_puntos(res: dict, unidad: str = "puntos", ejemplos: int = 3) -> str:
    """Una línea para el chat: cuántos puntos, tres de ejemplo y la fuente. Marca lo simulado."""
    nota = " (DATOS DE MUESTRA, modo simulado)" if res.get("simulado") else ""
    if not res.get("ok"):
        return f"{res.get('aviso', 'No pude obtener datos.')} Fuente: {res.get('fuente')}."
    pts = res.get("puntos") or []
    if not pts and "tle" not in res and "lineas" not in res:
        return f"{res.get('aviso') or 'Sin datos.'} Fuente: {res.get('fuente')}.{nota}"
    if "tle" in res:
        return f"{res.get('cantidad', 0)} satélites visibles (TLE para propagar órbitas). Fuente: {res.get('fuente')}.{nota}"
    if "lineas" in res:
        return f"{len(res['lineas'])} tendidos de cable submarino. Fuente: {res.get('fuente')}.{nota}"
    muestra = "; ".join(f"«{p['label']}» ({p['lat']}, {p['lon']})" for p in pts[:ejemplos])
    return f"{len(pts)} {unidad}. Por ejemplo: {muestra}. Fuente: {res.get('fuente')}.{nota}"
