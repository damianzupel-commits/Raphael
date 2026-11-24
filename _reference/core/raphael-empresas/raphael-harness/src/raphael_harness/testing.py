"""Ayudas para que cada repo de brigada pruebe su pieza sola, sin las demás."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .contrato import Brigada, Orquestador
from .harness import Harness
from .perfil import perfil_de

PERFIL_MINIMO: dict[str, Any] = {
    "empresa": {"nombre": "Taller Ejemplo", "duena": "Ana"},
    "plan": "basico",
    "brigadas": [],
    "informacion": {"horarios": "Lunes a sábado de 10 a 19", "envios": "Enviamos a todo el país por correo",
                    "medios_pago": ["transferencia", "efectivo"], "ubicacion": "Rosario, zona centro"},
    "cobros": {"sena_pct": 50, "alias": "taller.ejemplo", "titular": "Ana Pérez"},
    "encargos": {"precios": [{"prenda": "vestido", "base": 150000, "dias": 30}],
                 "recargos": [{"palabra": "largo", "tipo": "pct", "valor": 20}]},
    "agenda": {"recordatorio_dias_antes": 3, "franjas": ["jueves 16 a 19", "sábado 10 a 13"]},
}


class Reloj:
    """Reloj controlable para pruebas."""

    def __init__(self, inicio: datetime | None = None) -> None:
        self.ahora = inicio or datetime(2026, 11, 18, 10, 0)

    def __call__(self) -> datetime:
        return self.ahora


def armar(*brigadas: Brigada, orquestador: Orquestador | None = None, perfil: dict | None = None,
          reloj: Reloj | None = None, **kw: Any) -> Harness:
    datos = {**PERFIL_MINIMO, **(perfil or {})}
    datos["brigadas"] = [b.nombre for b in brigadas]
    return Harness(perfil_de(datos), brigadas=list(brigadas), orquestador=orquestador, reloj=reloj or Reloj(),
                   config_modelos=kw.pop("config_modelos", {}), **kw)
