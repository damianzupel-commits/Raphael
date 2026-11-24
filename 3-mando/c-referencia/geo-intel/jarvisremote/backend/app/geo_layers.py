"""Capas públicas del globo (2026-10-13) — "panorama del mundo", estilo God's Eye View.

SOLO fuentes 🟢 GRATIS Y SIN API KEY (batch verde). Todo se trae SERVER-SIDE (evita CORS en
el navegador) y se cachea para no pegarle de más. Cada capa es best-effort: si la fuente falla,
devuelve lo cacheado o vacío, nunca rompe. Datos públicos de infraestructura/eventos del mundo
— nada de vigilancia de personas.

Capas:
  - earthquakes : terremotos de las últimas 24h (USGS GeoJSON).
  - news        : noticias geolocalizadas (GDELT GEO 2.0).
  - iss         : posición de la Estación Espacial (open-notify).
  - satellites  : TLEs de satélites visibles (CelesTrak) — el globo los propaga con satellite.js.
  - infra       : datacenters (OpenStreetMap vía Overpass).
Los vuelos (ADS-B / OpenSky) viven aparte en geo_intel.fetch_flights (/api/geo/flights).
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_UA = "JarvisRemote-Globo/1.0"
_cache: dict[str, dict] = {}


def _get(url: str, ttl: float, timeout: float = 15.0, data: bytes | None = None, headers: dict | None = None):
    now = time.time()
    c = _cache.get(url)
    if c and now - c["ts"] < ttl:
        return c["data"]
    try:
        hdrs = {"User-Agent": _UA}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- URLs fijas públicas
            raw = resp.read().decode("utf-8", "replace")
        _cache[url] = {"ts": now, "data": raw}
        return raw
    except Exception:  # noqa: BLE001 -- best-effort
        return c["data"] if c else None


def earthquakes() -> list[dict]:
    raw = _get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", ttl=300)
    out: list[dict] = []
    if not raw:
        return out
    try:
        for f in json.loads(raw).get("features", []):
            coords = (f.get("geometry") or {}).get("coordinates") or []
            props = f.get("properties") or {}
            if len(coords) >= 2:
                out.append({"lat": coords[1], "lon": coords[0], "val": props.get("mag"),
                            "label": f"M{props.get('mag')} · {props.get('place', '')}"})
    except Exception:  # noqa: BLE001
        pass
    return out


def news(query: str = "(protest OR attack OR cyberattack OR earthquake OR conflict)") -> list[dict]:
    url = ("https://api.gdeltproject.org/api/v2/geo/geo?query="
           + urllib.parse.quote(query) + "&format=GeoJSON&timespan=1d&maxrows=300")
    raw = _get(url, ttl=600)
    out: list[dict] = []
    if not raw:
        return out
    try:
        for f in json.loads(raw).get("features", []):
            coords = (f.get("geometry") or {}).get("coordinates") or []
            props = f.get("properties") or {}
            if len(coords) >= 2:
                out.append({"lat": coords[1], "lon": coords[0], "label": (props.get("name") or props.get("html") or "noticia")[:120]})
    except Exception:  # noqa: BLE001
        pass
    return out


def iss() -> list[dict]:
    raw = _get("http://api.open-notify.org/iss-now.json", ttl=10)
    if not raw:
        return []
    try:
        p = json.loads(raw).get("iss_position") or {}
        return [{"lat": float(p["latitude"]), "lon": float(p["longitude"]), "label": "🛰 ISS (Estación Espacial)"}]
    except Exception:  # noqa: BLE001
        return []


def satellites_tle() -> str:
    """TLEs de satélites visibles (CelesTrak). El globo los propaga a posición con satellite.js."""
    raw = _get("https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle", ttl=3600)
    return raw or ""


def infra() -> list[dict]:
    """Datacenters del mundo (OpenStreetMap vía Overpass). Cacheado fuerte (dato casi estático)."""
    q = '[out:json][timeout:25];(node["telecom"="data_center"];node["office"="data_center"];);out 1500;'
    raw = _get("https://overpass-api.de/api/interpreter", ttl=86400, timeout=30,
               data=("data=" + urllib.parse.quote(q)).encode("utf-8"))
    out: list[dict] = []
    if not raw:
        return out
    try:
        for el in json.loads(raw).get("elements", []):
            if el.get("lat") is not None and el.get("lon") is not None:
                name = (el.get("tags") or {}).get("name") or "datacenter"
                out.append({"lat": el["lat"], "lon": el["lon"], "label": name[:80]})
    except Exception:  # noqa: BLE001
        pass
    return out


# --- Capas con API key (batch amarillo). Vacío = capa apagada, nunca rompe. ---------------
def fires(key: str) -> list[dict]:
    """Incendios activos del mundo (NASA FIRMS, VIIRS, últimas 24h). CSV."""
    if not key:
        return []
    raw = _get(f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/world/1", ttl=1800, timeout=25)
    out: list[dict] = []
    if not raw:
        return out
    try:
        lines = raw.strip().splitlines()
        if len(lines) < 2:
            return out
        hdr = [h.strip() for h in lines[0].split(",")]
        ila, ilo = hdr.index("latitude"), hdr.index("longitude")
        ifrp = hdr.index("frp") if "frp" in hdr else None
        for ln in lines[1:3001]:
            cols = ln.split(",")
            if len(cols) <= max(ila, ilo):
                continue
            try:
                out.append({"lat": float(cols[ila]), "lon": float(cols[ilo]),
                            "val": float(cols[ifrp]) if ifrp is not None and cols[ifrp] else None,
                            "label": "incendio activo"})
            except ValueError:
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


def webcams(key: str) -> list[dict]:
    """Cámaras PÚBLICAS (Windy Webcams API v3). Solo cámaras que su dueño publicó — tránsito,
    turismo, clima. NUNCA cámaras privadas sin seguridad."""
    if not key:
        return []
    raw = _get("https://api.windy.com/webcams/api/v3/webcams?limit=500&include=location,images,urls",
               ttl=3600, headers={"x-windy-api-key": key})
    out: list[dict] = []
    if not raw:
        return out
    try:
        for w in json.loads(raw).get("webcams", []):
            loc = w.get("location") or {}
            if loc.get("latitude") is not None and loc.get("longitude") is not None:
                out.append({
                    "lat": loc["latitude"], "lon": loc["longitude"],
                    "label": (w.get("title") or "cámara")[:100],
                    "meta": {"url": ((w.get("urls") or {}).get("detail") or ""),
                             "img": (((w.get("images") or {}).get("current") or {}).get("preview") or "")},
                })
    except Exception:  # noqa: BLE001
        pass
    return out


def shodan(key: str, query: str) -> list[dict]:
    """Hosts expuestos a internet que matchean `query` (Shodan). OSINT de INFRAESTRUCTURA pública
    (servicios que responden en internet) — no personas. Devuelve hasta 100 (1 página gratis)."""
    if not key:
        return []
    import urllib.parse as _u

    raw = _get(f"https://api.shodan.io/shodan/host/search?key={_u.quote(key)}&query={_u.quote(query)}", ttl=600)
    out: list[dict] = []
    if not raw:
        return out
    try:
        for m in json.loads(raw).get("matches", []):
            loc = m.get("location") or {}
            la, lo = loc.get("latitude"), loc.get("longitude")
            if la is not None and lo is not None:
                out.append({"lat": la, "lon": lo,
                            "label": f"{m.get('ip_str','')}:{m.get('port','')} {m.get('org') or ''}".strip()})
    except Exception:  # noqa: BLE001
        pass
    return out


# Ciudades grandes para la capa de clima (OpenWeather group: hasta 20 IDs por llamada).
_WEATHER_CITY_IDS = ("3435910,3448439,5128581,2643743,2988507,1850147,524901,1816670,1273294,"
                     "360630,2332459,2147714,3530597,5368361,3117735,2950159,745044,292223,1880252,6167865")


def weather(key: str) -> list[dict]:
    """Clima actual de las ciudades grandes del mundo (OpenWeather). `val` = temperatura °C."""
    if not key:
        return []
    raw = _get(f"https://api.openweathermap.org/data/2.5/group?id={_WEATHER_CITY_IDS}&units=metric&appid={key}", ttl=900)
    out: list[dict] = []
    if not raw:
        return out
    try:
        for c in json.loads(raw).get("list", []):
            coord = c.get("coord") or {}
            if coord.get("lat") is not None:
                temp = (c.get("main") or {}).get("temp")
                desc = ((c.get("weather") or [{}])[0]).get("description", "")
                out.append({"lat": coord["lat"], "lon": coord["lon"], "val": temp,
                            "label": f"{c.get('name','')}: {temp}°C · {desc}"})
    except Exception:  # noqa: BLE001
        pass
    return out


def opencellid(key: str, bbox: str) -> list[dict]:
    """Torres de celular en un ÁREA (OpenCelliD getInArea; su API no es global — ver bbox)."""
    if not key or not bbox:
        return []
    raw = _get(f"https://opencellid.org/cell/getInArea?key={key}&BBOX={bbox}&format=json&limit=1000", ttl=86400)
    out: list[dict] = []
    if not raw:
        return out
    try:
        for c in json.loads(raw).get("cells", []):
            if c.get("lat") is not None and c.get("lon") is not None:
                out.append({"lat": c["lat"], "lon": c["lon"], "label": f"{c.get('radio','')} cell {c.get('cellid','')}"})
    except Exception:  # noqa: BLE001
        pass
    return out


def cables() -> list[list[list[float]]]:
    """Cables submarinos (OpenStreetMap vía Overpass) — reemplazo LIBRE del dataset de
    TeleGeography (que es no-comercial). Devuelve líneas: [[[lat,lon],...], ...]. La cobertura
    de OSM es parcial pero es de licencia abierta (ODbL)."""
    q = ('[out:json][timeout:60];('
         'way["man_made"="cable"]["submarine"="yes"];'
         'way["submarine"="yes"]["man_made"="pipeline"];'
         'way["communication:submarine_cable"];'
         ');out geom 500;')
    raw = _get("https://overpass-api.de/api/interpreter", ttl=86400, timeout=45,
               data=("data=" + urllib.parse.quote(q)).encode("utf-8"))
    out: list[list[list[float]]] = []
    if not raw:
        return out
    try:
        for el in json.loads(raw).get("elements", []):
            pts = [[g["lat"], g["lon"]] for g in (el.get("geometry") or []) if g.get("lat") is not None]
            if len(pts) >= 2:
                out.append(pts)
    except Exception:  # noqa: BLE001
        pass
    return out


def get(name: str) -> dict:
    """Dispatch. Devuelve {points:[...]}, {lines:[...]} (cables) o {tle:"..."} (satélites)."""
    if name == "cables":
        return {"lines": cables()}
    if name in ("fires", "webcams", "shodan", "weather", "opencellid", "ships"):
        from .config import settings

        if name == "fires":
            return {"points": fires(settings.firms_map_key)}
        if name == "webcams":
            return {"points": webcams(settings.windy_webcams_key)}
        if name == "shodan":
            return {"points": shodan(settings.shodan_key, settings.shodan_query)}
        if name == "weather":
            return {"points": weather(settings.openweather_key)}
        if name == "opencellid":
            return {"points": opencellid(settings.opencellid_key, settings.opencellid_bbox)}
        if name == "ships":
            from . import geo_ships

            return {"points": geo_ships.points()}
    if name == "earthquakes":
        return {"points": earthquakes()}
    if name == "news":
        return {"points": news()}
    if name == "iss":
        return {"points": iss()}
    if name == "infra":
        return {"points": infra()}
    if name == "satellites":
        return {"tle": satellites_tle()}
    return {"points": []}
