"""El contrato que cumple cada pieza montada en el harness (cocineros, jefes y orquestador).

Es lo único que una brigada necesita conocer del harness. Las brigadas NUNCA se importan entre sí:
todo intercambio pasa por el harness (eventos, comandos y acciones) y por el orquestador.

Versionado semántico: `CONTRACT_VERSION` sube el MAJOR solo con un cambio incompatible. Cada
manifiesto declara qué versiones acepta (por ejemplo `">=2.0,<3"`) y el cargador rechaza lo que no
cumpla. Lo de la v1 de Empresas (contrato entero `1`) entra por `raphael_core.compat.v1`.

Los métodos de `Cook` y `Orchestrator` pueden ser comunes o `async`: el harness detecta cuál es.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .context import Context, OrchestratorContext, OwnerContext

CONTRACT_VERSION = "2.1.0"   # 2.1 (22 nov): routing del manifiesto, ganchos y catálogo del orquestador


# --- versiones -------------------------------------------------------------------------------------------------------
_SEMVER = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+.][0-9A-Za-z.-]+)?$")
_CONSTRAINT = re.compile(r"^\s*(>=|<=|==|!=|>|<|\^|~)?\s*(\S+)\s*$")


def parse_version(text: str) -> tuple[int, int, int]:
    """'2', '2.1' o '2.1.3' (con sufijo opcional) -> (2, 1, 3). ValueError si no es una versión."""
    m = _SEMVER.match(str(text).strip())
    if not m:
        raise ValueError(f"versión inválida: {text!r}")
    return int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)


def _check(op: str, have: tuple[int, int, int], want_text: str) -> bool:
    want = parse_version(want_text)
    if op in ("", "=="):
        return have == want if want_text.count(".") >= 2 else have[: want_text.count(".") + 1] == want[: want_text.count(".") + 1]
    if op == "!=":
        return have != want
    if op == ">=":
        return have >= want
    if op == "<=":
        return have <= want
    if op == ">":
        return have > want
    if op == "<":
        return have < want
    if op == "^":  # mismo major, igual o mayor
        return have[0] == want[0] and have >= want
    if op == "~":  # mismo major y minor, igual o mayor
        return have[:2] == want[:2] and have >= want
    raise ValueError(f"operador desconocido: {op}")


def contract_compatible(spec: str, version: str = CONTRACT_VERSION) -> bool:
    """¿La versión cumple la restricción? `spec` admite varias separadas por coma: '>=2.0,<3', '^2.0', '2'.

    ValueError si la restricción está mal escrita (un manifiesto con eso no valida)."""
    have = parse_version(version)
    parts = [p for p in str(spec).split(",") if p.strip()]
    if not parts:
        raise ValueError("restricción de contrato vacía")
    for part in parts:
        m = _CONSTRAINT.match(part)
        if not m:
            raise ValueError(f"restricción inválida: {part!r}")
        if not _check(m.group(1) or "", have, m.group(2)):
            return False
    return True


# --- niveles, confianza y origen -------------------------------------------------------------------------------------
class Level(StrEnum):
    """Quién decide una acción. Los valores quedan en castellano porque los escribe la persona en la config."""

    AUTO = "automatico"        # se ejecuta sola y queda registrada
    APPROVAL = "aprobacion"    # queda pendiente hasta que una persona la apruebe
    HUMAN = "humano"           # la resuelve una persona; el sistema se retira

    @property
    def weight(self) -> int:
        return _WEIGHTS[self]

    def lower(self) -> Level:
        """Un escalón menos estricto (HUMAN -> APPROVAL -> AUTO). AUTO queda igual."""
        return _ORDER[max(0, self.weight - 1)]

    def higher(self) -> Level:
        """Un escalón más estricto (AUTO -> APPROVAL -> HUMAN). HUMAN queda igual."""
        return _ORDER[min(len(_ORDER) - 1, self.weight + 1)]


_ORDER = (Level.AUTO, Level.APPROVAL, Level.HUMAN)
_WEIGHTS = {lvl: i for i, lvl in enumerate(_ORDER)}


class Trust(StrEnum):
    """De dónde sale un contenido. Lo de terceros es DATO, nunca instrucción."""

    TRUSTED = "trusted"        # lo escribió la persona dueña de la instalación
    UNTRUSTED = "untrusted"    # mensajes de clientes, páginas, archivos subidos


class Origin(StrEnum):
    """Qué disparó una acción."""

    OWNER = "owner"              # una orden de la persona dueña
    SYSTEM = "system"            # reglas, tareas programadas, eventos internos
    THIRD_PARTY = "third_party"  # el procesamiento de contenido de terceros


# --- mensajes, acciones y respuestas ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Message:
    """Un mensaje que llega por un canal. Por defecto es de un tercero: no confiable."""

    channel: str              # whatsapp | instagram | prueba | panel
    sender: str               # id de quien escribe en ese canal
    text: str
    name: str = ""            # nombre del perfil del canal, si lo hay
    attachment: bool = False  # foto, audio, documento
    at: datetime | None = None
    trust: Trust = Trust.UNTRUSTED

    @property
    def contact(self) -> str:
        return f"{self.channel}:{self.sender}"


@dataclass
class Action:
    """Algo que un cocinero quiere hacer y que pasa por el Policy Engine."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""                  # lo que ve la persona en el panel
    target: str | None = None          # contacto "canal:id" al que va el mensaje que resulte
    origin: Origin = Origin.SYSTEM

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data, "summary": self.summary, "target": self.target,
                "origin": self.origin.value}

    @classmethod
    def from_dict(cls, d: dict) -> Action:
        return cls(type=d["type"], data=dict(d.get("data") or {}), summary=d.get("summary", ""), target=d.get("target"),
                   origin=Origin(d.get("origin", Origin.SYSTEM.value)))


@dataclass
class Reply:
    """Lo que contesta un cocinero a un mensaje."""

    text: str | None = None
    actions: list[Action] = field(default_factory=list)


@dataclass
class OwnerReply:
    """Lo que el orquestador le contesta a la persona dueña cuando ella le habla."""

    text: str
    suggestions: list[str] = field(default_factory=list)  # frases cortas para tocar
    tasks: list[dict] = field(default_factory=list)       # lista numerada del día, si corresponde
    card: dict | None = None                              # detalle de una tarea: contexto y opciones
    meta: dict = field(default_factory=dict)              # vía, fidelidad, ruteo, tiempos (para el panel, no para la persona)

    def to_dict(self) -> dict:
        return {"text": self.text, "suggestions": self.suggestions, "tasks": self.tasks, "card": self.card,
                "meta": self.meta}


@dataclass(frozen=True)
class Health:
    ok: bool
    detail: str = ""


class ActionError(RuntimeError):
    """La acción no se puede ejecutar así (falta un dato, choca con otra). El mensaje va a la persona."""


# --- piezas ----------------------------------------------------------------------------------------------------------
class Piece:
    """Lo común a todo lo que se monta."""

    name: str = ""
    version: str = "0.0.0"
    description: str = ""


class Cook(Piece):
    """Cocinero: agente permanente de una brigada. Se sobreescribe solo lo que se usa.

    Las acciones, eventos y tools que puede usar NO se declaran acá: los declara el manifiesto de su
    brigada, que es la única fuente de verdad (el harness rechaza lo que no esté declarado).
    """

    #: comandos que ofrece al panel: nombre -> descripción
    commands: dict[str, str] = {}

    def start(self, ctx: Context) -> None:
        """Se llama una vez al montarse."""

    def interest(self, msg: Message, ctx: Context) -> float:
        """0 a 1: qué tan suyo es este mensaje. Lo usa el orquestador para ordenar."""
        return 0.0

    def in_progress(self, msg: Message, ctx: Context) -> bool:
        """¿Tiene una conversación abierta con este contacto?"""
        return False

    def handle(self, msg: Message, ctx: Context) -> Reply | None:
        """La respuesta, o None si este mensaje no es para este cocinero."""
        return None

    def execute(self, action: Action, ctx: Context) -> str | None:
        """Ejecuta una acción ya permitida. Devuelve el texto para el destinatario, si hay."""
        raise ActionError(f"{self.name} no sabe ejecutar '{action.type}'")

    def on_event(self, event: str, data: dict, ctx: Context) -> None:
        """Reacciona a un evento del bus."""

    def command(self, name: str, data: dict, ctx: Context) -> Any:
        """Una orden del panel (cambiar un estado, listar…)."""
        raise ActionError(f"{self.name} no tiene el comando '{name}'")

    def tick(self, now: datetime, ctx: Context) -> None:
        """Tareas programadas. El harness lo llama periódicamente."""

    def health(self, ctx: Context) -> Health:
        return Health(True)

    def stop(self, ctx: Context) -> None:
        """Se llama al desmontarse."""


class Orchestrator(Piece):
    """Decide qué cocineros ven cada mensaje y en qué orden. Opcionalmente atiende a la persona dueña.

    Solo la interfaz: la implementación (mando, voz, ruteo, Secretaria) es de la pieza 02-orquestador.
    Desde 2.1 también tiene ganchos: `configure` (config de la instalación), `tick` (cada vez que corre el tick del
    harness) y `on_event` (solo los eventos que nombra `consumes`). En `tick` y `on_event` recibe un
    `OrchestratorContext`: puede leer y avisar, nunca ejecutar (open loops sin efecto).
    """

    #: eventos del bus que el orquestador escucha (ej. "pendiente.creado", "brigada.jefe_caido"); "*" = todos
    consumes: tuple[str, ...] = ()

    def configure(self, config: dict) -> None:
        """La config que trae la instalación (`orchestrator.config`). Se llama una vez, antes de montarlo."""
        self.config = dict(config)

    def route(self, msg: Message, ctx: Context, cooks: list[Cook]) -> list[Cook]:
        raise NotImplementedError

    def talk_to_owner(self, text: str, ctx: OwnerContext) -> OwnerReply | None:
        """None = este orquestador no sabe atender a la persona."""
        return None

    def tick(self, now: datetime, ctx: OrchestratorContext) -> None:
        """Revisión periódica (pendientes viejos, brigadas caídas). Solo lee y avisa."""

    def on_event(self, event: str, data: dict, ctx: OrchestratorContext) -> None:
        """Un evento del bus que nombra `consumes`."""
