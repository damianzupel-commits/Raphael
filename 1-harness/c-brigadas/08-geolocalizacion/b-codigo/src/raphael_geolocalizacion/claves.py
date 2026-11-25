"""Claves de las fuentes: salen SOLO de variables de entorno (nunca de la config ni del repo) y nunca se muestran.

Cada fuente que necesita clave está acá; las demás son públicas y no piden nada. Sin clave la fuente avisa y devuelve
vacío: la brigada no inventa. La plantilla con todas está en `b-codigo/geolocalizacion.env.plantilla`.
"""

from __future__ import annotations

from collections.abc import Mapping

#: capa o búsqueda -> (variable de entorno, dónde se saca)
CLAVES: dict[str, tuple[str, str]] = {
    "shodan": ("SHODAN_KEY", "https://account.shodan.io"),
    "barcos": ("AISSTREAM_KEY", "https://aisstream.io (gratis, con cuenta)"),
    "incendios": ("FIRMS_MAP_KEY", "https://firms.modaps.eosdis.nasa.gov/api/map_key (gratis)"),
    "camaras": ("WINDY_WEBCAMS_KEY", "https://api.windy.com/keys (gratis)"),
    "clima": ("OPENWEATHER_KEY", "https://home.openweathermap.org/api_keys (gratis)"),
    "antenas": ("OPENCELLID_KEY", "https://opencellid.org (gratis, con cuenta)"),
}


def clave(env: Mapping[str, str], fuente: str) -> str:
    var = CLAVES[fuente][0]
    return (env.get(var) or "").strip()


def estado(env: Mapping[str, str]) -> dict[str, str]:
    """Para cada fuente con clave: 'cargada' o 'falta' (con la variable). Nunca el valor."""
    return {f: ("cargada" if clave(env, f) else f"falta {CLAVES[f][0]}") for f in CLAVES}
