"""El contrato v1 (raphael-harness 0.4, Raphael Empresas), con sus nombres en castellano, sobre el harness v2.

Las brigadas de Empresas lo usan tal cual: `Brigada`, `Accion`, `Mensaje`, `Respuesta`, `Nivel`, `Charla`,
`Orquestador`, `ErrorDeAccion`. `ErrorDeAccion` ES el `ActionError` del v2, así el harness lo reconoce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from ...contract import ActionError

if TYPE_CHECKING:  # pragma: no cover
    from .harness import Contexto

CONTRATO = 1
ErrorDeAccion = ActionError


class Nivel(str, Enum):  # noqa: UP042 - igual que en v1 (str + Enum)
    AUTO = "automatico"
    APROBACION = "aprobacion"
    HUMANO = "humano"

    @property
    def peso(self) -> int:
        return {"automatico": 0, "aprobacion": 1, "humano": 2}[self.value]


@dataclass(frozen=True)
class Mensaje:
    canal: str
    quien: str
    texto: str
    nombre: str = ""
    adjunto: bool = False
    cuando: datetime | None = None

    @property
    def contacto(self) -> str:
        return f"{self.canal}:{self.quien}"


@dataclass
class Accion:
    tipo: str
    datos: dict[str, Any] = field(default_factory=dict)
    resumen: str = ""
    destino: str | None = None

    def a_dict(self) -> dict:
        return {"tipo": self.tipo, "datos": self.datos, "resumen": self.resumen, "destino": self.destino}

    @classmethod
    def de_dict(cls, d: dict) -> Accion:
        return cls(tipo=d["tipo"], datos=dict(d.get("datos") or {}), resumen=d.get("resumen", ""), destino=d.get("destino"))


@dataclass
class Respuesta:
    texto: str | None = None
    acciones: list[Accion] = field(default_factory=list)


class Pieza:
    nombre: str = ""
    version: str = "0.0.0"
    contrato: int = CONTRATO
    descripcion: str = ""


class Brigada(Pieza):
    acciones: dict[str, Nivel] = {}  # noqa: RUF012
    eventos: tuple[str, ...] = ()
    comandos: dict[str, str] = {}  # noqa: RUF012

    def iniciar(self, ctx: Contexto) -> None:
        """Se llama una vez al arrancar el harness."""

    def interes(self, msg: Mensaje, ctx: Contexto) -> float:
        return 0.0

    def en_curso(self, msg: Mensaje, ctx: Contexto) -> bool:
        return False

    def atender(self, msg: Mensaje, ctx: Contexto) -> Respuesta | None:
        return None

    def ejecutar(self, accion: Accion, ctx: Contexto) -> str | None:
        raise ErrorDeAccion(f"{self.nombre} no sabe ejecutar '{accion.tipo}'")

    def al_evento(self, evento: str, datos: dict, ctx: Contexto) -> None:
        """Reacciona a un evento del bus."""

    def comando(self, nombre: str, datos: dict, ctx: Contexto) -> Any:
        raise ErrorDeAccion(f"{self.nombre} no tiene el comando '{nombre}'")

    def tick(self, ahora: datetime, ctx: Contexto) -> None:
        """Tareas programadas."""


@dataclass
class Charla:
    texto: str
    sugerencias: list[str] = field(default_factory=list)
    tareas: list[dict] = field(default_factory=list)
    ficha: dict | None = None

    def a_dict(self) -> dict:
        return {"texto": self.texto, "sugerencias": self.sugerencias, "tareas": self.tareas, "ficha": self.ficha}


class Orquestador(Pieza):
    def elegir(self, msg: Mensaje, ctx: Contexto, brigadas: list[Brigada]) -> list[Brigada]:
        raise NotImplementedError

    def atender_duena(self, texto: str, ctx: Contexto) -> Charla | None:
        return None
