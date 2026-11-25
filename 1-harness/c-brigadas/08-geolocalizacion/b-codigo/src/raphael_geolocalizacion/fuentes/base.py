"""Las fuentes de datos: una sola lógica (armar la consulta, leer la respuesta) y dos transportes enchufables.

`Fuentes` sabe a qué URL pedir y cómo leer cada respuesta. El transporte (`http`) es lo que cambia:
- `FuentesReales` (`real.py`): internet, con caché y fail-soft.
- `FuentesSimuladas` (`simulado.py`): respuestas fijas con el MISMO formato que las APIs reales, sin red ni claves.
Los tests corren con la simulada, así que prueban también el parseo de las respuestas reales.

Todo resultado es un dict con `ok`, `fuente` (de dónde salió: regla de la brigada) y, si algo faltó, `aviso` en español.
Sin clave o sin red: `ok: False`, lista vacía y el aviso. Nunca se inventa un dato.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from collections.abc import Callable, Mapping

from .. import claves, validar

#: transporte: (url, ttl=, timeout=, data=, headers=) -> texto de la respuesta, o None si falló
Http = Callable[..., "str | None"]

CAPAS = ("terremotos", "noticias", "iss", "satelites", "datacenters", "cables", "vuelos", "barcos", "incendios",
         "camaras", "clima", "antenas")
#: nombres viejos de JarvisRemote -> los de ahora
ALIAS = {"earthquakes": "terremotos", "news": "noticias", "satellites": "satelites", "infra": "datacenters",
         "flights": "vuelos", "ships": "barcos", "fires": "incendios", "webcams": "camaras", "weather": "clima"}
LIBRES = ("terremotos", "noticias", "iss", "satelites", "datacenters", "cables", "vuelos")   # sin clave
OVERPASS = "https://overpass-api.de/api/interpreter"
GRANDES_CIUDADES = ("3435910,3448439,5128581,2643743,2988507,1850147,524901,1816670,1273294,"
                    "360630,2332459,2147714,3530597,5368361,3117735,2950159,745044,292223,1880252,6167865")


def ok(fuente: str, **datos) -> dict:
    return {"ok": True, "fuente": fuente, **datos}


def fallo(fuente: str, aviso: str, **vacio) -> dict:
    return {"ok": False, "fuente": fuente, "aviso": aviso, **vacio}


def _json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        out = json.loads(raw)
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def punto(lat, lon, label, **extra) -> dict | None:
    c = validar.coordenadas(lat, lon)
    if c is None:
        return None
    return {"lat": c[0], "lon": c[1], "label": validar.limpiar(label, 120) or "punto", **extra}


def ais_a_puntos(mensajes: list[dict]) -> list[dict]:
    """Última posición de cada barco (por MMSI) a partir de mensajes PositionReport de AISStream."""
    ultimos: dict[str, dict] = {}
    for m in mensajes:
        md = (m or {}).get("MetaData") or {}
        mmsi = md.get("MMSI")
        if mmsi is None:
            continue
        p = punto(md.get("latitude"), md.get("longitude"), (md.get("ShipName") or "").strip() or f"MMSI {mmsi}",
                  mmsi=str(mmsi))
        if p:
            ultimos[str(mmsi)] = p
    return list(ultimos.values())[:4000]


class Fuentes:
    simulado = False

    def __init__(self, env: Mapping[str, str] | None = None, http: Http | None = None) -> None:
        self.env: Mapping[str, str] = os.environ if env is None else env
        self._http: Http = http or self._sin_transporte

    @staticmethod
    def _sin_transporte(*_a, **_k) -> str | None:
        return None

    # --- claves
    def clave(self, fuente: str) -> str:
        return claves.clave(self.env, fuente)

    def estado_claves(self) -> dict[str, str]:
        return claves.estado(self.env)

    def _requiere(self, fuente: str, nombre: str) -> dict | None:
        """None si se puede seguir; si falta la clave, el resultado de aviso (en simulado nunca falta)."""
        if self.simulado or self.clave(fuente):
            return None
        var, donde = claves.CLAVES[fuente]
        return fallo(nombre, f"Falta {var} (se saca en {donde}). Sin ella no hay datos de {fuente}.", puntos=[])

    # --- IP y dominios
    def ip(self, objetivo: str) -> dict:
        campos = "status,message,query,country,regionName,city,lat,lon,timezone,isp,org,as,reverse"
        d = _json(self._http(f"http://ip-api.com/json/{urllib.parse.quote(objetivo)}?fields={campos}", ttl=3600))
        if d is None:
            return fallo("ip-api.com", "No pude consultar la geolocalización (sin red o la fuente no respondió).")
        if d.get("status") != "success":
            motivo = validar.limpiar(d.get("message") or "desconocido", 80)
            return fallo("ip-api.com", f"ip-api no devolvió datos: {motivo}.")
        return ok("ip-api.com", objetivo=d.get("query", objetivo), pais=d.get("country"), region=d.get("regionName"),
                  ciudad=d.get("city"), lat=d.get("lat"), lon=d.get("lon"), zona_horaria=d.get("timezone"),
                  isp=d.get("isp"), org=d.get("org"), asn=d.get("as"), dns_inverso=d.get("reverse"))

    def shodan(self, consulta: str) -> dict:
        falta = self._requiere("shodan", "Shodan")
        if falta:
            return {**falta, "hosts": []}
        key = urllib.parse.quote(self.clave("shodan") or "simulada")
        d = _json(self._http(f"https://api.shodan.io/shodan/host/search?key={key}&query={urllib.parse.quote(consulta)}",
                             ttl=600))
        if d is None:
            return fallo("Shodan", "Shodan no respondió (clave inválida, sin créditos o sin red).", hosts=[])
        hosts = []
        for m in (d.get("matches") or [])[:100]:
            loc = m.get("location") or {}
            hosts.append({"ip": validar.limpiar(m.get("ip_str"), 45), "puerto": m.get("port"),
                          "org": validar.limpiar(m.get("org"), 80), "pais": validar.limpiar(loc.get("country_name"), 60),
                          "producto": validar.limpiar(m.get("product"), 60), "lat": loc.get("latitude"),
                          "lon": loc.get("longitude")})
        return ok("Shodan", total=d.get("total"), hosts=hosts)

    # --- cripto
    def cripto(self, direccion: str, cadena: str) -> dict:
        if cadena == "ethereum":
            d = _json(self._http(f"https://api.blockchair.com/ethereum/dashboards/address/{direccion}", ttl=300))
            a = (((d or {}).get("data") or {}).get(direccion.lower()) or {}).get("address") or {}
            if not a:
                return fallo("blockchair.com", "No encontré datos para esa dirección ETH (o la fuente no respondió).")

            def eth(k: str) -> float:
                return round(int(a.get(k, 0) or 0) / 1e18, 8)
            return ok("blockchair.com", cadena="ethereum", direccion=direccion, balance_eth=eth("balance"),
                      recibido_eth=eth("received"), enviado_eth=eth("spent"), transacciones=a.get("transaction_count"))
        d = _json(self._http(f"https://blockchain.info/rawaddr/{direccion}?limit=0", ttl=300))
        if d is None:
            return fallo("blockchain.info", "No pude rastrear la dirección BTC (sin red o la fuente no respondió).")

        def btc(k: str) -> float:
            return round((d.get(k, 0) or 0) / 1e8, 8)
        return ok("blockchain.info", cadena="bitcoin", direccion=direccion, balance_btc=btc("final_balance"),
                  recibido_btc=btc("total_received"), enviado_btc=btc("total_sent"), transacciones=d.get("n_tx"))

    # --- capas del globo
    def capa(self, nombre: str, **params) -> dict:
        nombre = ALIAS.get(nombre, nombre)
        if nombre not in CAPAS:
            return fallo("capas", f"No conozco la capa «{validar.limpiar(nombre, 30)}». Capas: {', '.join(CAPAS)}.", puntos=[])
        return getattr(self, f"_capa_{nombre}")(**params)

    def _puntos(self, fuente: str, raw: str | None, hacer: Callable[[dict], list[dict | None]], *, clave_json: str,
                vacio: str) -> dict:
        d = _json(raw)
        if d is None:
            return fallo(fuente, f"No pude leer {fuente} (sin red o la fuente no respondió).", puntos=[])
        pts = [p for el in (d.get(clave_json) or []) if isinstance(el, dict) for p in hacer(el) if p]
        return ok(fuente, puntos=pts) if pts else {**ok(fuente, puntos=[]), "aviso": vacio}

    def _capa_terremotos(self) -> dict:
        raw = self._http("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", ttl=300)

        def hacer(f):
            c = (f.get("geometry") or {}).get("coordinates") or []
            p = f.get("properties") or {}
            return [punto(c[1], c[0], f"M{p.get('mag')} · {p.get('place', '')}", val=p.get("mag"))] if len(c) >= 2 else []
        return self._puntos("USGS", raw, hacer, clave_json="features", vacio="No hubo terremotos en las últimas 24 h.")

    def _capa_noticias(self, consulta: str = "(protest OR attack OR cyberattack OR earthquake OR conflict)") -> dict:
        url = ("https://api.gdeltproject.org/api/v2/geo/geo?query=" + urllib.parse.quote(consulta)
               + "&format=GeoJSON&timespan=1d&maxrows=300")

        def hacer(f):
            c = (f.get("geometry") or {}).get("coordinates") or []
            p = f.get("properties") or {}
            return [punto(c[1], c[0], p.get("name") or "noticia")] if len(c) >= 2 else []
        return self._puntos("GDELT", self._http(url, ttl=600), hacer, clave_json="features",
                            vacio="GDELT no devolvió noticias geolocalizadas.")

    def _capa_iss(self) -> dict:
        d = _json(self._http("http://api.open-notify.org/iss-now.json", ttl=10))
        p = (d or {}).get("iss_position") or {}
        pt = punto(p.get("latitude"), p.get("longitude"), "ISS (Estación Espacial)")
        return ok("open-notify.org", puntos=[pt]) if pt else fallo("open-notify.org", "No pude ubicar la ISS.", puntos=[])

    def _capa_satelites(self) -> dict:
        raw = self._http("https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle", ttl=3600)
        if not raw:
            return fallo("celestrak.org", "No pude bajar los TLE de satélites.", tle="")
        return ok("celestrak.org", tle=raw, cantidad=len([ln for ln in raw.splitlines() if ln.startswith("1 ")]))

    def _capa_datacenters(self) -> dict:
        q = '[out:json][timeout:25];(node["telecom"="data_center"];node["office"="data_center"];);out 1500;'
        raw = self._http(OVERPASS, ttl=86400, timeout=30, data=("data=" + urllib.parse.quote(q)).encode())

        def hacer(el):
            if el.get("type") == "way":
                return []
            return [punto(el.get("lat"), el.get("lon"), (el.get("tags") or {}).get("name") or "datacenter")]
        return self._puntos("OpenStreetMap (Overpass)", raw, hacer, clave_json="elements", vacio="Sin datacenters.")

    def _capa_cables(self) -> dict:
        q = ('[out:json][timeout:60];(way["man_made"="cable"]["submarine"="yes"];way["submarine"="yes"]["man_made"="pipeline"];'
             'way["communication:submarine_cable"];);out geom 500;')
        d = _json(self._http(OVERPASS, ttl=86400, timeout=45, data=("data=" + urllib.parse.quote(q)).encode()))
        if d is None:
            return fallo("OpenStreetMap (Overpass)", "No pude bajar los cables submarinos.", lineas=[])
        lineas = []
        for el in d.get("elements") or []:
            pts = [[g["lat"], g["lon"]] for g in (el.get("geometry") or []) if isinstance(g, dict) and g.get("lat") is not None]
            if len(pts) >= 2:
                lineas.append(pts)
        return ok("OpenStreetMap (Overpass)", lineas=lineas, aviso="La cobertura de OSM es parcial (licencia ODbL).")

    def _capa_vuelos(self, maximo: int = 2000) -> dict:
        d = _json(self._http("https://opensky-network.org/api/states/all", ttl=15, timeout=12))
        if d is None:
            return fallo("OpenSky", "No pude leer OpenSky (límite anónimo o sin red).", puntos=[])
        pts = []
        for s in d.get("states") or []:
            try:
                if s[5] is None or s[6] is None or s[8]:
                    continue
                p = punto(s[6], s[5], (s[1] or "").strip() or "vuelo", pais=validar.limpiar(s[2], 40), alt=s[7], vel=s[9])
            except (IndexError, TypeError):
                continue
            if p:
                pts.append(p)
            if len(pts) >= maximo:
                break
        return ok("OpenSky", puntos=pts)

    def _capa_barcos(self, segundos: float = 8.0) -> dict:
        falta = self._requiere("barcos", "AISStream")
        if falta:
            return falta
        try:
            mensajes = self._ais(segundos)
        except RuntimeError as exc:
            return fallo("AISStream", str(exc), puntos=[])
        return ok("AISStream", puntos=ais_a_puntos(mensajes), aviso=f"Muestra de {segundos:g} s del stream mundial.")

    def _ais(self, segundos: float) -> list[dict]:
        raise RuntimeError("No hay transporte AIS.")

    def _capa_incendios(self) -> dict:
        falta = self._requiere("incendios", "NASA FIRMS")
        if falta:
            return falta
        k = urllib.parse.quote(self.clave("incendios") or "simulada")
        raw = self._http(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{k}/VIIRS_SNPP_NRT/world/1", ttl=1800,
                         timeout=25)
        if not raw:
            return fallo("NASA FIRMS", "NASA FIRMS no respondió.", puntos=[])
        lineas = raw.strip().splitlines()
        if len(lineas) < 2:
            return ok("NASA FIRMS", puntos=[])
        hdr = [h.strip() for h in lineas[0].split(",")]
        if "latitude" not in hdr or "longitude" not in hdr:
            return fallo("NASA FIRMS", "NASA FIRMS devolvió un formato que no entiendo.", puntos=[])
        ila, ilo = hdr.index("latitude"), hdr.index("longitude")
        ifrp = hdr.index("frp") if "frp" in hdr else None
        pts = []
        for ln in lineas[1:3001]:
            c = ln.split(",")
            try:
                p = punto(c[ila], c[ilo], "incendio activo", val=float(c[ifrp]) if ifrp is not None and c[ifrp] else None)
            except (IndexError, ValueError):
                continue
            if p:
                pts.append(p)
        return ok("NASA FIRMS", puntos=pts)

    def _capa_camaras(self) -> dict:
        """Solo cámaras que su dueño publicó (tránsito, turismo, clima). Nunca cámaras privadas."""
        falta = self._requiere("camaras", "Windy Webcams")
        if falta:
            return falta
        raw = self._http("https://api.windy.com/webcams/api/v3/webcams?limit=500&include=location,images,urls", ttl=3600,
                         headers={"x-windy-api-key": self.clave("camaras") or "simulada"})

        def hacer(w):
            loc = w.get("location") or {}
            return [punto(loc.get("latitude"), loc.get("longitude"), w.get("title") or "cámara",
                          url=validar.limpiar((w.get("urls") or {}).get("detail"), 200))]
        return self._puntos("Windy Webcams", raw, hacer, clave_json="webcams", vacio="Sin cámaras.")

    def _capa_clima(self) -> dict:
        falta = self._requiere("clima", "OpenWeather")
        if falta:
            return falta
        k = urllib.parse.quote(self.clave("clima") or "simulada")
        raw = self._http(f"https://api.openweathermap.org/data/2.5/group?id={GRANDES_CIUDADES}&units=metric&appid={k}",
                         ttl=900)

        def hacer(c):
            co = c.get("coord") or {}
            t = (c.get("main") or {}).get("temp")
            desc = ((c.get("weather") or [{}])[0]).get("description", "")
            return [punto(co.get("lat"), co.get("lon"), f"{c.get('name', '')}: {t}°C · {desc}", val=t)]
        return self._puntos("OpenWeather", raw, hacer, clave_json="list", vacio="Sin clima.")

    def _capa_antenas(self, bbox: str = "") -> dict:
        falta = self._requiere("antenas", "OpenCelliD")
        if falta:
            return falta
        bbox = bbox or (self.env.get("OPENCELLID_BBOX") or "").strip()
        if not bbox:
            return fallo("OpenCelliD", "Falta el área: pasá bbox (lat_sur,lon_oeste,lat_norte,lon_este) o cargá "
                         "OPENCELLID_BBOX. Su API no es global.", puntos=[])
        k = urllib.parse.quote(self.clave("antenas") or "simulada")
        raw = self._http(f"https://opencellid.org/cell/getInArea?key={k}&BBOX={urllib.parse.quote(bbox)}&format=json&limit=1000",
                         ttl=86400)

        def hacer(c):
            return [punto(c.get("lat"), c.get("lon"), f"{c.get('radio', '')} cell {c.get('cellid', '')}")]
        return self._puntos("OpenCelliD", raw, hacer, clave_json="cells", vacio="Sin antenas en esa área.")
