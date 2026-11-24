"""Tools de lookups OSINT — capacidades inspiradas en Horus (6abd/horus), pero
REIMPLEMENTADAS desde cero (NO se copió código: Horus es GPL-3.0 y copiarlo
obligaría a todo este repo a ser GPL — las ideas/capacidades no tienen licencia,
el código sí). Agregado 2026-09-28 a pedido de Damian ("robá lo que haga falta").

Dos lookups de datos PÚBLICOS, sin API key, sobre INFRAESTRUCTURA/dinero (no
sobre personas):
- `ip_geolocate`: IP → ubicación aproximada + ASN/ISP (ip-api.com).
- `crypto_address_trace`: dirección BTC/ETH → balance + actividad (explorers públicos).

Encajan con el módulo de investigación de Raphael. Ética/scope (mismo criterio que
el resto del OSINT del proyecto): datos públicos, NADA de deanonimizar, acosar o
geolocalizar a una PERSONA — geolocalizar una IP/servidor o seguir una dirección
de cripto es OSINT estándar de infraestructura, no vigilancia de individuos.

Usan urllib de la stdlib (cero dependencias nuevas). Defensivas: si la red falla o
la API responde raro, devuelven un error claro sin romper el backend.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from . import register_tool

_TIMEOUT = 12
_UA = "JarvisRemote-OSINT/1.0"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 -- URLs fijas de APIs públicas
        return json.loads(resp.read().decode("utf-8", "replace"))


@register_tool(
    name="ip_geolocate",
    description=(
        "Geolocaliza una dirección IP (o dominio): país, región, ciudad, coordenadas aproximadas, "
        "zona horaria, ISP/organización y ASN. Datos PÚBLICOS vía ip-api.com, sin API key. Útil para "
        "investigación/OSINT de INFRAESTRUCTURA (de dónde sale un servidor, a qué ISP/hosting pertenece "
        "una IP de un log). NO es para geolocalizar ni rastrear a una persona — solo infraestructura pública."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "IP (v4/v6) o dominio a geolocalizar."},
        },
        "required": ["target"],
    },
)
def ip_geolocate(target: str) -> dict:
    target = (target or "").strip()
    if not target:
        return {"error": "falta la IP o dominio."}
    # ip-api: campos elegidos explícitamente (bitmask por nombre)
    fields = "status,message,query,country,regionName,city,lat,lon,timezone,isp,org,as,reverse"
    try:
        data = _get_json(f"http://ip-api.com/json/{urllib.parse.quote(target)}?fields={fields}")
    except Exception as exc:  # noqa: BLE001
        return {"error": f"no pude consultar la geolocalización: {exc!r}"}
    if data.get("status") != "success":
        return {"error": f"ip-api falló: {data.get('message', 'desconocido')}", "target": target}
    result = {
        "target": data.get("query", target),
        "pais": data.get("country"), "region": data.get("regionName"), "ciudad": data.get("city"),
        "lat": data.get("lat"), "lon": data.get("lon"), "timezone": data.get("timezone"),
        "isp": data.get("isp"), "org": data.get("org"), "asn": data.get("as"),
        "reverse_dns": data.get("reverse"),
    }
    # Mapa de inteligencia (2026-10-13): cae como pin en el globo de Raphael (/globo). Best-effort.
    try:
        from ..geo_intel import add_point

        ciudad = result.get("ciudad") or ""
        pais = result.get("pais") or ""
        etiqueta = f"{result['target']} · {ciudad}{', ' if ciudad and pais else ''}{pais}".strip(" ·")
        add_point(
            result.get("lat"), result.get("lon"), etiqueta, kind="ip",
            meta={"isp": result.get("isp"), "asn": result.get("asn"), "reverse": result.get("reverse_dns")},
        )
    except Exception:  # noqa: BLE001
        pass
    return result


_BTC_RE = re.compile(r"^(bc1[0-9a-z]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
_ETH_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


@register_tool(
    name="crypto_address_trace",
    description=(
        "Rastrea una dirección de criptomoneda pública (Bitcoin o Ethereum): balance actual, total "
        "recibido/enviado y cantidad de transacciones. Datos PÚBLICOS de la blockchain (blockchain.info "
        "para BTC, blockchair para ETH), sin API key. Útil para seguir el rastro del dinero en una "
        "investigación. Detecta solo la cadena por el formato de la dirección; devolvé lo que encuentre."
    ),
    parameters={
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Dirección BTC (1.../3.../bc1...) o ETH (0x...)."},
        },
        "required": ["address"],
    },
)
def crypto_address_trace(address: str) -> dict:
    address = (address or "").strip()
    if not address:
        return {"error": "falta la dirección."}

    if _ETH_RE.match(address):
        try:
            data = _get_json(f"https://api.blockchair.com/ethereum/dashboards/address/{address}")
            addr = (data.get("data", {}).get(address.lower(), {}) or {}).get("address", {})
            if not addr:
                return {"error": "no encontré datos para esa dirección ETH.", "address": address}
            wei = int(addr.get("balance", 0) or 0)
            return {
                "chain": "ethereum", "address": address,
                "balance_eth": round(wei / 1e18, 8),
                "recibido_eth": round(int(addr.get("received", 0) or 0) / 1e18, 8),
                "enviado_eth": round(int(addr.get("spent", 0) or 0) / 1e18, 8),
                "transacciones": addr.get("transaction_count"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"no pude rastrear la dirección ETH: {exc!r}", "address": address}

    if _BTC_RE.match(address):
        try:
            data = _get_json(f"https://blockchain.info/rawaddr/{address}?limit=0")
            return {
                "chain": "bitcoin", "address": address,
                "balance_btc": round((data.get("final_balance", 0) or 0) / 1e8, 8),
                "recibido_btc": round((data.get("total_received", 0) or 0) / 1e8, 8),
                "enviado_btc": round((data.get("total_sent", 0) or 0) / 1e8, 8),
                "transacciones": data.get("n_tx"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"no pude rastrear la dirección BTC: {exc!r}", "address": address}

    return {"error": "no reconozco el formato (¿BTC 1/3/bc1 o ETH 0x...?).", "address": address}


@register_tool(
    name="shodan_host_search",
    description=(
        "Busca en Shodan hosts/servicios EXPUESTOS a internet que matchean una query (ej. "
        "'apache country:AR', 'product:nginx port:443', 'org:\"Some ISP\"'). OSINT de INFRAESTRUCTURA "
        "pública (servicios que responden en internet), estándar en seguridad — NO sirve ni se usa para "
        "rastrear personas. Requiere SHODAN_KEY (se pone en Configuración → Fuentes del mapa). Devuelve "
        "los hosts (IP, puerto, organización, país) y los deja como pines en el mapa de inteligencia (/globo)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Query de Shodan (filtros: product, port, country, org, etc.)."},
        },
        "required": ["query"],
    },
)
def shodan_host_search(query: str) -> dict:
    from ..config import settings

    if not settings.shodan_key:
        return {"error": "falta SHODAN_KEY — ponela en Configuración → Fuentes del mapa."}
    query = (query or "").strip()
    if not query:
        return {"error": "falta la query."}
    try:
        data = _get_json(
            f"https://api.shodan.io/shodan/host/search?key={urllib.parse.quote(settings.shodan_key)}"
            f"&query={urllib.parse.quote(query)}"
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Shodan falló: {exc!r}"}
    hosts = []
    for m in data.get("matches", [])[:100]:
        loc = m.get("location") or {}
        host = {
            "ip": m.get("ip_str"), "port": m.get("port"), "org": m.get("org"),
            "pais": loc.get("country_name"), "lat": loc.get("latitude"), "lon": loc.get("longitude"),
            "producto": m.get("product"),
        }
        hosts.append(host)
        if host["lat"] is not None and host["lon"] is not None:
            try:
                from ..geo_intel import add_point

                add_point(host["lat"], host["lon"], f"{host['ip']}:{host['port']} {host.get('org') or ''}".strip(),
                          kind="shodan", meta={"org": host.get("org"), "producto": host.get("producto")})
            except Exception:  # noqa: BLE001
                pass
    return {"total": data.get("total"), "mostrados": len(hosts), "hosts": hosts}
