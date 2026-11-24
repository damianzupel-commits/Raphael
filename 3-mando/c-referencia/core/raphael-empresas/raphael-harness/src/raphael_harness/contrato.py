"""El contrato que cumple cada pieza de Raphael (brigadas y orquestador).

Es lo único que una brigada necesita conocer del harness. Las brigadas NUNCA se importan
entre sí: se hablan a través del harness (eventos, consultas y acciones). Así cada una vive
en su propio repo, con su versión y sus tests, y se puede actualizar sin tocar las demás.

Si este archivo cambia de forma incompatible, se sube `CONTRATO` y el harness deja de cargar
las piezas que declaren otro número.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .harness import Contexto

CONTRATO = 1


class Nivel(str, Enum):
    """Quién decide una acción."""

    AUTO = "automatico"        # la brigada la ejecuta y queda registrada
    APROBACION = "aprobacion"  # queda pendiente con un botón para la dueña
    HUMANO = "humano"          # el bot se retira: la resuelve una persona

    @property
    def peso(self) -> int:
        return {"automatico": 0, "aprobacion": 1, "humano": 2}[self.value]


@dataclass(frozen=True)
class Mensaje:
    """Un mensaje que llega de un cliente por un canal."""

    canal: str            # whatsapp | instagram | prueba
    quien: str            # id del cliente en ese canal
    texto: str
    nombre: str = ""      # nombre del perfil del canal, si lo hay
    adjunto: bool = False  # foto, audio, documento
    cuando: datetime | None = None

    @property
    def contacto(self) -> str:
        return f"{self.canal}:{self.quien}"


@dataclass
class Accion:
    """Algo que una brigada quiere hacer y que pasa por el Policy Engine."""

    tipo: str
    datos: dict[str, Any] = field(default_factory=dict)
    resumen: str = ""                  # lo que ve la dueña en el panel
    destino: str | None = None         # contacto "canal:quien" al que va el mensaje que resulte

    def a_dict(self) -> dict:
        return {"tipo": self.tipo, "datos": self.datos, "resumen": self.resumen, "destino": self.destino}

    @classmethod
    def de_dict(cls, d: dict) -> "Accion":
        return cls(tipo=d["tipo"], datos=dict(d.get("datos") or {}), resumen=d.get("resumen", ""), destino=d.get("destino"))


@dataclass
class Respuesta:
    """Lo que contesta una brigada a un mensaje."""

    texto: str | None = None
    acciones: list[Accion] = field(default_factory=list)


class ErrorDeAccion(RuntimeError):
    """La acción no se puede ejecutar así (falta un dato, choca con otra). El mensaje va a la dueña."""


class Pieza:
    """Lo común a brigadas y orquestador."""

    nombre: str = ""
    version: str = "0.0.0"
    contrato: int = CONTRATO
    descripcion: str = ""


class Brigada(Pieza):
    """Base de toda brigada. Se sobreescribe solo lo que la brigada usa."""

    #: acciones que la brigada puede pedir, con su nivel por defecto
    acciones: dict[str, Nivel] = {}
    #: eventos del bus que escucha ("*" = todos)
    eventos: tuple[str, ...] = ()
    #: comandos que ofrece al panel de la dueña: nombre -> descripción
    comandos: dict[str, str] = {}

    def iniciar(self, ctx: "Contexto") -> None:
        """Se llama una vez al arrancar el harness."""

    def interes(self, msg: Mensaje, ctx: "Contexto") -> float:
        """0 a 1: qué tan suyo es este mensaje. Lo usa el orquestador para ordenar."""
        return 0.0

    def en_curso(self, msg: Mensaje, ctx: "Contexto") -> bool:
        """¿Tiene una conversación abierta con este contacto?"""
        return False

    def atender(self, msg: Mensaje, ctx: "Contexto") -> Respuesta | None:
        """La respuesta, o None si este mensaje no es para esta brigada."""
        return None

    def ejecutar(self, accion: Accion, ctx: "Contexto") -> str | None:
        """Ejecuta una acción ya permitida. Devuelve el texto a mandarle al cliente, si hay."""
        raise ErrorDeAccion(f"{self.nombre} no sabe ejecutar '{accion.tipo}'")

    def al_evento(self, evento: str, datos: dict, ctx: "Contexto") -> None:
        """Reacciona a un evento del bus."""

    def comando(self, nombre: str, datos: dict, ctx: "Contexto") -> Any:
        """Una orden del panel de la dueña (cambiar un estado, listar…)."""
        raise ErrorDeAccion(f"{self.nombre} no tiene el comando '{nombre}'")

    def tick(self, ahora: datetime, ctx: "Contexto") -> None:
        """Tareas programadas (recordatorios). El harness lo llama periódicamente."""


@dataclass
class Charla:
    """Lo que el orquestador le contesta a la dueña cuando ella le habla (modo secretario)."""

    texto: str
    sugerencias: list[str] = field(default_factory=list)   # frases cortas para tocar ("¿Cuál primero?")
    tareas: list[dict] = field(default_factory=list)        # lista numerada del día, si corresponde
    ficha: dict | None = None                               # detalle de una tarea: contexto y opciones

    def a_dict(self) -> dict:
        return {"texto": self.texto, "sugerencias": self.sugerencias, "tareas": self.tareas, "ficha": self.ficha}


class Orquestador(Pieza):
    """Decide qué brigadas ven cada mensaje y en qué orden. Opcionalmente también atiende a la dueña."""

    def elegir(self, msg: Mensaje, ctx: "Contexto", brigadas: list[Brigada]) -> list[Brigada]:
        raise NotImplementedError

    def atender_duena(self, texto: str, ctx: "Contexto") -> Charla | None:
        """La dueña le habla al orquestador (qué hay para hoy, qué hago primero…). None = este orquestador no sabe."""
        return None
