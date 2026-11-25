"""Barcos y capas del globo: terremotos, noticias, ISS, satélites, datacenters, cables, vuelos, barcos y más, más los pines.

Capas libres (sin clave): terremotos, noticias, iss, satelites, datacenters, cables, vuelos. Con clave: barcos
(AISSTREAM_KEY), incendios, cámaras públicas, clima y antenas. Sin la clave la capa avisa cuál falta y devuelve vacío.
Borrar los pines es la acción `borrar_pines` (aprobación, irreversible).
Portado de `geo_layers.py`, `geo_ships.py` y `geo_intel.fetch_flights` de JarvisRemote.
"""

from __future__ import annotations

from raphael_core import Action, ActionError, Message, Reply
from raphael_core.text_es import normalize

from .. import fuentes, pines
from ..claves import CLAVES
from .comun import CocineroGeo, resumen_puntos

#: palabras del mensaje -> capa
PALABRAS = {"terremoto": "terremotos", "sismo": "terremotos", "temblor": "terremotos", "noticias": "noticias",
            "estacion espacial": "iss", " iss": "iss", "satelite": "satelites", "datacenter": "datacenters",
            "data center": "datacenters", "cable submarino": "cables", "cables": "cables", "vuelos": "vuelos",
            "aviones": "vuelos", "barcos": "barcos", "buques": "barcos", "incendios": "incendios", "camaras": "camaras",
            "clima": "clima", "antenas": "antenas", "torres de celular": "antenas"}
TOPE_PUNTOS = 3000


def capa_en(texto: str) -> str | None:
    t = " " + normalize(texto)
    return next((capa for clave, capa in PALABRAS.items() if clave in t), None)


class Capas(CocineroGeo):
    name = "capas"
    description = "Capas del mapa (terremotos, vuelos, barcos, satélites…) y los pines guardados del globo."
    commands = {"capa": "datos de una capa {'name': 'terremotos'}", "capas": "las capas y si necesitan clave",
                "pines": "los pines guardados {'kind': 'ip', 'limit': 100}"}

    def interest(self, msg: Message, ctx) -> float:
        t = normalize(msg.text)
        if capa_en(msg.text):
            return 0.8
        if "pines" in t or ("mapa" in t and "borra" in t):
            return 0.8
        return 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        t = normalize(msg.text)
        if ("pines" in t or "pins" in t) and any(w in t for w in ("borra", "elimina", "limpia", "vacia")):
            n = len(pines.listar(ctx, limite=10**6))
            return Reply(f"Voy a borrar los {n} pines del globo. No se puede deshacer, así que espera tu OK.",
                         [Action("borrar_pines", {}, f"Borrar los {n} pines del globo")])
        if "pines" in t or "pins" in t:
            p = pines.listar(ctx, limite=5)
            if not p:
                return Reply("El globo no tiene pines todavía.")
            return Reply("Últimos pines: " + "; ".join(f"«{x['label']}» ({x['lat']}, {x['lon']})" for x in p) + ".")
        capa = capa_en(msg.text)
        if capa is None:
            return None
        return Reply(resumen_puntos(self.fuentes(ctx).capa(capa)))

    def execute(self, action: Action, ctx) -> str | None:
        if action.type != "borrar_pines":
            raise ActionError(f"capas no ejecuta '{action.type}'")
        return f"Listo: borré {pines.borrar(ctx, action.data.get('kind'))} pines del globo."

    def command(self, name: str, data: dict, ctx):
        if name == "capa":
            r = self.fuentes(ctx).capa(str(data.get("name", "")))
            if len(r.get("puntos") or []) > TOPE_PUNTOS:
                r["puntos"] = r["puntos"][:TOPE_PUNTOS]
            return r
        if name == "capas":
            f = self.fuentes(ctx)
            est = f.estado_claves()
            return [{"capa": c, "necesita_clave": c in CLAVES,
                     "estado": "libre" if c not in CLAVES else ("lista" if f.simulado or est[c] == "cargada" else est[c])}
                    for c in fuentes.CAPAS]
        if name == "pines":
            return pines.listar(ctx, data.get("kind"), int(data.get("limit", 100)))
        return super().command(name, data, ctx)
