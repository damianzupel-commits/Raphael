"""Manifiesto de una brigada (`manifest.yaml`): lo que el harness necesita saber ANTES de importar su código.

Es la única fuente de verdad sobre qué puede hacer una brigada: sus cocineros, el nivel de autonomía
de cada acción, sus tools, los eventos que publica y escucha, su espacio de datos, su healthcheck y qué
exporta o borra al desmontarse. Lo que no está declarado acá, el harness no lo deja pasar.

Ejemplo mínimo:

    id: saludo
    name: Brigada de saludo
    version: 1.0.0
    contract: ">=2.0,<3"
    cooks:
      - {id: saludador, entry: "raphael_saludo:Greeter"}
    actions:
      saludar: {level: automatico}
      regalar: {level: aprobacion, tags: [spend]}
    events: {publishes: [saludo.hecho], consumes: [pendiente.creado]}
    commands:
      visitas: {read: true, description: "cuántas veces escribió cada contacto"}
    setup: "raphael_saludo.setup:register"     # registra las tools sin `entry` al montar
    health: "raphael_saludo:check"             # se corre al montar y cada 5 min

Ruteo (2.1, 22 nov 2026): `routing: {signals: [{pattern: "en la web|internet", weight: 2}], direct_only: false,
safe_default: false}`. Lo lee el orquestador desde el catálogo del harness.

Comandos (22 nov 2026): el orquestador solo corre los declarados con `read: true`. Uno no declarado lo puede correr
la persona desde el panel, con aviso; el orquestador nunca.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contract import CONTRACT_VERSION, Level, contract_compatible, parse_version

ID = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
ACTION = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
EVENT = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z0-9_-]+)*$")
ENTRY = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")

Tag = Literal["spend", "irreversible", "external"]
Edition = Literal["personal", "cloud"]

#: etiquetas que obligan a confirmar a mano antes de dejar una acción en automático
RISKY_TAGS: frozenset[str] = frozenset({"spend", "irreversible"})


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActionSpec(_Base):
    """Una acción con efecto. El nivel es obligatorio: ninguna acción queda sin decidir quién la aprueba."""

    level: Level
    tags: frozenset[Tag] = frozenset()   # spend: gasta plata · irreversible: sin vuelta atrás · external: sale al mundo
    description: str = ""

    @property
    def risky(self) -> bool:
        return bool(self.tags & RISKY_TAGS)


class ToolSpec(_Base):
    name: str
    entry: str | None = None          # 'modulo:funcion'; None = la registra el código de la brigada al montarse
    level: Level = Level.AUTO         # leer/analizar = automatico; si tiene efecto, declararlo
    tags: frozenset[Tag] = frozenset()
    dangerous: bool = False           # solo en la edición personal
    active_scan: bool = False         # escaneo activo (nmap, sqlmap…): nunca en la nube
    description: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not ACTION.match(v):
            raise ValueError(f"nombre de tool inválido: {v!r}")
        return v

    @field_validator("entry")
    @classmethod
    def _entry(cls, v: str | None) -> str | None:
        if v is not None and not ENTRY.match(v):
            raise ValueError(f"entry inválido (se espera 'modulo:nombre'): {v!r}")
        return v


class CommandSpec(_Base):
    read: bool = False                # True = solo lee: lo puede pedir el orquestador
    description: str = ""


class CookSpec(_Base):
    id: str
    entry: str                        # 'paquete.modulo:Clase'
    blocking: bool = False            # True = sus métodos sync se corren en un hilo aparte

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID.match(v):
            raise ValueError(f"id de cocinero inválido: {v!r}")
        return v

    @field_validator("entry")
    @classmethod
    def _entry(cls, v: str) -> str:
        if not ENTRY.match(v):
            raise ValueError(f"entry inválido (se espera 'modulo:Clase'): {v!r}")
        return v


class EventsSpec(_Base):
    publishes: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()    # "*" = todos

    @field_validator("publishes", "consumes")
    @classmethod
    def _names(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        malos = [e for e in v if e != "*" and not EVENT.match(e)]
        if malos:
            raise ValueError(f"nombres de evento inválidos: {malos}")
        return v


class RouteSignal(_Base):
    """Una señal para el ruteo del orquestador: un patrón sobre el pedido normalizado (minúsculas, sin acentos)."""

    pattern: str = Field(min_length=1, max_length=300)
    weight: Literal[1, 2] = 1         # 2 = señal fuerte: con dos brigadas con señal fuerte, el pedido es trabajo conjunto

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"patrón de ruteo inválido {v!r}: {exc}") from None
        return v


class RoutingSpec(_Base):
    """Cómo encuentra el orquestador a esta brigada (2.1). Montarla ya la hace ruteable: no se toca el orquestador.

    `signals`: patrones con peso. `direct_only`: solo por su pestaña o `/id` (nunca por auto-ruteo ni trabajo conjunto).
    `safe_default`: la brigada puede ser el destino por defecto cuando nada matchea (tiene que ser de solo lectura;
    cuál se usa lo decide la config del orquestador)."""

    signals: tuple[RouteSignal, ...] = Field(default=(), max_length=40)
    direct_only: bool = False
    safe_default: bool = False


class StoreSpec(_Base):
    space: str | None = None          # None = el id de la brigada


class UninstallSpec(_Base):
    export: tuple[str, ...] = ()      # colecciones que se ofrecen exportar al desmontar
    delete: tuple[str, ...] = ()      # colecciones que se borran ("*" = todo el espacio)


class Manifest(_Base):
    id: str
    name: str
    version: str
    contract: str
    description: str = ""
    cooks: tuple[CookSpec, ...] = ()
    chief: str | None = None          # 'modulo:SPEC' de un BrigadeSpec (motor de jefe y efímeros)
    actions: dict[str, ActionSpec] = Field(default_factory=dict)
    tools: tuple[ToolSpec, ...] = ()
    events: EventsSpec = EventsSpec()
    store: StoreSpec = StoreSpec()
    config_schema: dict = Field(default_factory=dict)
    health: str | None = None         # 'modulo:funcion' (ctx) -> Health; al montar y cada 5 min
    setup: str | None = None          # 'modulo:funcion' (ctx) al montar: registra tools sin `entry`
    commands: dict[str, CommandSpec] = Field(default_factory=dict)
    routing: RoutingSpec = RoutingSpec()  # 2.1: señales para el orquestador
    uninstall: UninstallSpec = UninstallSpec()
    editions: frozenset[Edition] = frozenset({"personal", "cloud"})

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID.match(v):
            raise ValueError(f"id de brigada inválido (minúsculas, números y guiones): {v!r}")
        return v

    @field_validator("version")
    @classmethod
    def _version(cls, v: str) -> str:
        parse_version(v)
        return v

    @field_validator("contract")
    @classmethod
    def _contract(cls, v: str) -> str:
        contract_compatible(v, "0.0.0")  # solo valida la sintaxis; la compatibilidad la decide el cargador
        return v

    @field_validator("actions")
    @classmethod
    def _actions(cls, v: dict[str, ActionSpec]) -> dict[str, ActionSpec]:
        malos = [a for a in v if not ACTION.match(a)]
        if malos:
            raise ValueError(f"nombres de acción inválidos: {malos}")
        return v

    @field_validator("commands")
    @classmethod
    def _commands(cls, v: dict[str, CommandSpec]) -> dict[str, CommandSpec]:
        malos = [c for c in v if not ACTION.match(c)]
        if malos:
            raise ValueError(f"nombres de comando inválidos: {malos}")
        return v

    @field_validator("chief", "health", "setup")
    @classmethod
    def _entries(cls, v: str | None) -> str | None:
        if v is not None and not ENTRY.match(v):
            raise ValueError(f"entry inválido (se espera 'modulo:nombre'): {v!r}")
        return v

    @model_validator(mode="after")
    def _coherence(self) -> Manifest:
        if not self.cooks and not self.chief:
            raise ValueError(f"brigada {self.id}: necesita al menos un cocinero o un jefe")
        ids = [c.id for c in self.cooks]
        if len(ids) != len(set(ids)):
            raise ValueError(f"brigada {self.id}: cocineros repetidos")
        tools = [t.name for t in self.tools]
        if len(tools) != len(set(tools)):
            raise ValueError(f"brigada {self.id}: tools repetidas")
        if not self.editions:
            raise ValueError(f"brigada {self.id}: tiene que poder correr en alguna edición")
        return self

    # --- lo que usan el cargador y el harness
    @property
    def space(self) -> str:
        return self.store.space or self.id

    def supports_contract(self, version: str = CONTRACT_VERSION) -> bool:
        return contract_compatible(self.contract, version)

    def tools_for(self, edition: str) -> tuple[ToolSpec, ...]:
        """Las tools que se pueden cargar en esa edición: en la nube no entra nada peligroso ni de escaneo activo."""
        if edition == "cloud":
            return tuple(t for t in self.tools if not (t.dangerous or t.active_scan))
        return self.tools


def manifest_from(data: dict) -> Manifest:
    return Manifest.model_validate(data)


def load_manifest(path: str | Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return manifest_from(data)
