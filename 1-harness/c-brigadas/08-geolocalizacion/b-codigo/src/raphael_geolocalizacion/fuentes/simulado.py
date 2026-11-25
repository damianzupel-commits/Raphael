"""Transporte simulado: respuestas fijas en el MISMO formato que las APIs reales. Sin red, sin claves.

Sirve para los tests y para ver el globo con datos de muestra antes de cargar ninguna clave. Todo lo que sale de acá va
marcado `simulado: True` en los resultados de la brigada, así nadie lo confunde con un dato real.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from .base import Fuentes

RESPUESTAS: dict[str, object] = {
    "ip-api.com": {"status": "success", "query": "8.8.8.8", "country": "Estados Unidos", "regionName": "Virginia",
                   "city": "Ashburn", "lat": 39.03, "lon": -77.5, "timezone": "America/New_York", "isp": "Google LLC",
                   "org": "Google Public DNS", "as": "AS15169 Google LLC", "reverse": "dns.google"},
    "api.shodan.io": {"total": 2, "matches": [
        {"ip_str": "203.0.113.10", "port": 443, "org": "Ejemplo SA", "product": "nginx",
         "location": {"country_name": "Argentina", "latitude": -32.95, "longitude": -60.64}},
        {"ip_str": "203.0.113.11", "port": 80, "org": "Ejemplo SA", "product": "Apache httpd",
         "location": {"country_name": "Chile", "latitude": -33.45, "longitude": -70.66}}]},
    "blockchain.info": {"final_balance": 150000000, "total_received": 300000000, "total_sent": 150000000, "n_tx": 7},
    "earthquake.usgs.gov": {"features": [
        {"geometry": {"coordinates": [-70.1, -33.4, 10]}, "properties": {"mag": 4.7, "place": "cerca de Santiago (muestra)"}},
        {"geometry": {"coordinates": [140.2, 35.6, 30]}, "properties": {"mag": 5.1, "place": "cerca de Tokio (muestra)"}}]},
    "api.gdeltproject.org": {"features": [
        {"geometry": {"coordinates": [-58.4, -34.6]}, "properties": {"name": "Noticia de muestra en Buenos Aires"}}]},
    "api.open-notify.org": {"iss_position": {"latitude": "12.5", "longitude": "-45.25"}},
    "overpass-api.de": {"elements": [
        {"type": "node", "lat": 50.1, "lon": 8.6, "tags": {"name": "Datacenter de muestra"}},
        {"type": "way", "geometry": [{"lat": 10.0, "lon": -30.0}, {"lat": 20.0, "lon": -40.0}], "tags": {"submarine": "yes"}}]},
    "opensky-network.org": {"states": [
        ["abc123", "ARG1234 ", "Argentina", 0, 0, -58.5, -34.8, 10000, False, 230],
        ["def456", "EN TIERRA", "Chile", 0, 0, -70.7, -33.4, 0, True, 0]]},
    "api.windy.com": {"webcams": [{"title": "Cámara pública de muestra", "location": {"latitude": -32.9, "longitude": -60.7},
                                   "urls": {"detail": "https://example.org/cam"}}]},
    "api.openweathermap.org": {"list": [{"name": "Rosario", "coord": {"lat": -32.95, "lon": -60.64},
                                         "main": {"temp": 24.5}, "weather": [{"description": "cielo claro"}]}]},
    "opencellid.org": {"cells": [{"lat": -32.94, "lon": -60.65, "radio": "LTE", "cellid": 1234}]},
}
TLE = ("ISS (ZARYA)\n1 25544U 98067A   24001.00000000  .00010000  00000-0  10000-3 0  9990\n"
       "2 25544  51.6400 100.0000 0005000  50.0000  30.0000 15.50000000  1000\n")
FIRMS = "latitude,longitude,frp\n-30.5,-60.1,12.5\n-31.0,-61.0,8.0\n"
AIS = [{"MetaData": {"MMSI": 701000001, "ShipName": "BARCO DE MUESTRA ", "latitude": -34.5, "longitude": -57.9}},
       {"MetaData": {"MMSI": 701000002, "ShipName": "", "latitude": -38.0, "longitude": -57.5}}]


def http_simulado(url: str, **_kw) -> str | None:
    if "celestrak.org" in url:
        return TLE
    if "firms.modaps" in url:
        return FIRMS
    if "api.blockchair.com" in url:   # responde por cualquier dirección ETH
        direccion = url.rsplit("/", 1)[1].lower()
        return json.dumps({"data": {direccion: {"address": {
            "balance": "2500000000000000000", "received": "5000000000000000000", "spent": "2500000000000000000",
            "transaction_count": 12}}}})
    for host, cuerpo in RESPUESTAS.items():
        if host in url:
            return json.dumps(cuerpo)
    return None


class FuentesSimuladas(Fuentes):
    simulado = True

    def __init__(self, env: Mapping[str, str] | None = None, http=None) -> None:
        super().__init__(env if env is not None else {}, http or http_simulado)

    def _ais(self, segundos: float) -> list[dict]:
        return list(AIS)

    def ip(self, objetivo: str) -> dict:
        return {**super().ip(objetivo), "simulado": True}

    def shodan(self, consulta: str) -> dict:
        return {**super().shodan(consulta), "simulado": True}

    def cripto(self, direccion: str, cadena: str) -> dict:
        return {**super().cripto(direccion, cadena), "simulado": True}

    def capa(self, nombre: str, **params) -> dict:
        return {**super().capa(nombre, **params), "simulado": True}
