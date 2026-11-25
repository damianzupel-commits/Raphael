"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Las consultas no guardan pines (el cocinero `ip-infra` sí, cuando lo pide la persona por chat): son de solo lectura sobre
fuentes públicas. La búsqueda en Shodan gasta cupo de la cuenta de Damián: es una tool con aprobación por corrida.
"""

from __future__ import annotations

from . import fuentes, pines, validar
from .claves import CLAVES

TOPE_PUNTOS = 200   # lo que el modelo ve de una capa: el resto es ruido para él (el globo ya recibe todo por el cocinero)


def make_tools(ctx) -> dict:
    def _f():
        return fuentes.elegir(ctx.config)

    def geo_ip(target: str) -> dict:
        """Geolocaliza una IP pública o un dominio. Una IP privada se rechaza. No guarda pin."""
        objetivo, motivo = validar.objetivo_ip(target)
        if objetivo is None:
            return {"ok": False, "fuente": "validación", "aviso": motivo}
        return _f().ip(objetivo)

    def geo_cripto(address: str) -> dict:
        """Balance y actividad de una dirección Bitcoin (1…/3…/bc1…) o Ethereum (0x…) en la blockchain pública."""
        direccion, cadena = validar.direccion_cripto(address)
        if direccion is None:
            return {"ok": False, "fuente": "validación",
                    "aviso": "No reconozco el formato (¿Bitcoin 1…/3…/bc1… o Ethereum 0x…?)."}
        return _f().cripto(direccion, cadena)

    def geo_capa(name: str) -> dict:
        """Datos de una capa del globo (terremotos, noticias, iss, satelites, datacenters, cables, vuelos, barcos…)."""
        r = _f().capa(str(name))
        pts = r.get("puntos") or []
        if len(pts) > TOPE_PUNTOS:
            r = {**r, "puntos": pts[:TOPE_PUNTOS], "total_puntos": len(pts)}
        return r

    def geo_capas() -> list[dict]:
        """Las capas disponibles y si necesitan clave."""
        f = _f()
        est = f.estado_claves()
        return [{"capa": c, "necesita_clave": c in CLAVES,
                 "estado": "libre" if c not in CLAVES else ("lista" if f.simulado or est[c] == "cargada" else est[c])}
                for c in fuentes.CAPAS]

    def geo_fuentes() -> dict:
        """Si la brigada corre con datos reales o simulados y qué claves hay cargadas (nunca su valor)."""
        f = _f()
        return {"modo": "simulado" if f.simulado else "real", "claves": f.estado_claves()}

    def geo_pines(kind: str = "", limit: int = 20) -> list[dict]:
        """Los pines guardados del globo, el más nuevo primero."""
        return pines.listar(ctx, kind or None, min(max(int(limit), 1), 100))

    def geo_shodan(query: str) -> dict:
        """Busca hosts expuestos en Shodan. Gasta cupo de la cuenta de Damián: cada corrida pide su aprobación."""
        consulta = validar.limpiar(query, 200)
        if not consulta:
            return {"ok": False, "fuente": "validación", "aviso": "Falta la consulta de Shodan."}
        return _f().shodan(consulta)

    return {"geo_ip": geo_ip, "geo_cripto": geo_cripto, "geo_capa": geo_capa, "geo_capas": geo_capas,
            "geo_fuentes": geo_fuentes, "geo_pines": geo_pines, "geo_shodan": geo_shodan}
