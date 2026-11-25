"""IP e infraestructura: geolocaliza IPs y dominios públicos (ip-api.com) y busca hosts expuestos (Shodan).

Solo infraestructura pública: una IP privada no se geolocaliza, y nada de esto sirve para ubicar a una persona. La búsqueda
en Shodan gasta cupo de la cuenta de Damián: es la acción `buscar_shodan` (aprobación, `spend` y `external`).
Portado de `ip_geolocate` y `shodan_host_search` de JarvisRemote.
"""

from __future__ import annotations

import re

from raphael_core import Action, ActionError, Message, Reply
from raphael_core.text_es import normalize

from .. import pines, validar
from .comun import CocineroGeo

IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{0,4}(?![\w:])")
DOMINIO = re.compile(r"\b(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,24}\b")
SHODAN = re.compile(r"\bshodan\b\s*:?\s*(.+)", re.IGNORECASE | re.DOTALL)
PISTAS = ("ip", "geolocaliz", "donde queda", "donde esta", "de donde", "dominio", "servidor", "host")


def objetivo_en(texto: str) -> str | None:
    for rx in (IPV4, IPV6, DOMINIO):
        m = rx.search(texto)
        if m:
            return m.group(0)
    return None


def linea_ip(r: dict) -> str:
    lugar = ", ".join(x for x in (r.get("ciudad"), r.get("region"), r.get("pais")) if x) or "ubicación desconocida"
    partes = [f"{r['objetivo']}: {lugar} ({r.get('lat')}, {r.get('lon')}, aproximado)"]
    if r.get("isp") or r.get("org"):
        partes.append(f"ISP/organización: {validar.limpiar(r.get('org') or r.get('isp'), 80)}")
    if r.get("asn"):
        partes.append(f"ASN: {validar.limpiar(r['asn'], 60)}")
    nota = " (DATOS DE MUESTRA, modo simulado)" if r.get("simulado") else ""
    return " · ".join(partes) + f". Fuente: {r['fuente']}.{nota}"


class IpInfra(CocineroGeo):
    name = "ip-infra"
    description = "Geolocaliza IPs y dominios públicos y busca hosts expuestos en Shodan."
    commands = {"ip": "geolocaliza una IP o dominio público {'target': '8.8.8.8'} y deja el pin en el globo",
                "fuentes": "qué claves están cargadas (sin mostrar su valor)"}

    def _consultar(self, texto: str, ctx) -> dict:
        objetivo, motivo = validar.objetivo_ip(texto)
        if objetivo is None:
            return {"ok": False, "fuente": "validación", "aviso": motivo}
        r = self.fuentes(ctx).ip(objetivo)
        if r.get("ok"):
            p = pines.agregar(ctx, r.get("lat"), r.get("lon"), f"{r['objetivo']} · {r.get('ciudad') or ''} {r.get('pais') or ''}",
                              "ip", {"isp": r.get("isp"), "asn": r.get("asn"), "simulado": bool(r.get("simulado"))})
            r["pin"] = p["id"] if p else None
        return r

    def interest(self, msg: Message, ctx) -> float:
        t = normalize(msg.text)
        if SHODAN.search(t):
            return 0.9
        if IPV4.search(t) or IPV6.search(msg.text):
            return 0.9
        if DOMINIO.search(msg.text) and any(p in t for p in PISTAS):
            return 0.8
        return 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        if self.interest(msg, ctx) <= 0:
            return None
        m = SHODAN.search(msg.text)
        if m:
            consulta = validar.limpiar(m.group(1), 200)
            if not consulta:
                return Reply("¿Qué busco en Shodan? Ejemplo: «shodan: product:nginx country:AR».")
            return Reply(f"Preparo la búsqueda en Shodan: «{consulta}». Gasta cupo de tu cuenta, así que espera tu OK.",
                         [Action("buscar_shodan", {"consulta": consulta}, f"Buscar en Shodan: {consulta}")])
        objetivo = objetivo_en(msg.text)
        r = self._consultar(objetivo or "", ctx)
        return Reply(linea_ip(r) if r.get("ok") else f"{r.get('aviso')} Fuente: {r.get('fuente')}.")

    def execute(self, action: Action, ctx) -> str | None:
        if action.type != "buscar_shodan":
            raise ActionError(f"ip-infra no ejecuta '{action.type}'")
        r = self.fuentes(ctx).shodan(validar.limpiar(action.data.get("consulta"), 200))
        if not r.get("ok"):
            raise ActionError(r.get("aviso", "Shodan falló."))
        con_pin = 0
        for h in r["hosts"]:
            if pines.agregar(ctx, h["lat"], h["lon"], f"{h['ip']}:{h['puerto']} {h['org']}", "shodan",
                             {"org": h["org"], "producto": h["producto"], "simulado": bool(r.get("simulado"))}):
                con_pin += 1
        nota = " (DATOS DE MUESTRA, modo simulado)" if r.get("simulado") else ""
        return (f"Shodan: {r.get('total')} resultados, {len(r['hosts'])} mostrados, {con_pin} con ubicación (ya están en el "
                f"globo). Fuente: Shodan.{nota}")

    def command(self, name: str, data: dict, ctx):
        if name == "ip":
            r = self._consultar(str(data.get("target", "")), ctx)
            return r
        if name == "fuentes":
            return {"modo": "simulado" if self.fuentes(ctx).simulado else "real", "claves": self.fuentes(ctx).estado_claves()}
        return super().command(name, data, ctx)
