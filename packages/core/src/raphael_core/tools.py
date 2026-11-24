"""Gateway de tools: registro único, caja por efímero (menor privilegio) y compuerta de política.

En JarvisRemote un efímero llamaba a sus tools directo: el nivel de autonomía no pasaba por el medio (problema anotado
en DISENO-V2 §2). Acá toda llamada pasa por tres filtros, en este orden:

  1. EDICIÓN: en la nube no se registra nada `dangerous` ni `active_scan` (se rechaza al registrar, no al llamar).
  2. CAJA: el efímero solo ve y solo puede llamar las tools de su `HelperSpec.tools` (lista blanca). Pedir otra = error
     que vuelve al modelo como dato; no se ejecuta nada.
  3. COMPUERTA: el runtime decide con la política (`tool_<nombre>` de esa brigada; en la `autonomy` de la instalación,
     `brigada.tool_<nombre>`). En `automatico` se ejecuta; si no, queda un pendiente de tipo "tool" y al modelo le
     vuelve `{"status": "pending_approval", ...}`. La tool se ejecuta recién cuando una persona aprueba
     (`Runtime.approve`).

Las tools pueden ser sync o async. Una sync corre en un hilo para no trabar el loop.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from .contract import ActionError, Level
from .manifest import ToolSpec

Gate = Callable[["Tool", dict], Awaitable[dict | None]]   # None = puede correr; dict = lo que se le devuelve al modelo


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


def parameters_of(fn: Any) -> dict:
    """Esquema JSON de los parámetros de una función (para el modelo). `fn.parameters` lo pisa si existe."""
    if isinstance(getattr(fn, "parameters", None), dict):
        return fn.parameters
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = p.annotation
        if isinstance(ann, str):
            ann = {"str": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict}.get(ann.split("|")[0]
                                                                                                         .strip(), str)
        props[name] = {"type": _JSON_TYPES.get(ann, "string")}
        if p.default is p.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


class ToolError(ActionError):
    """Una tool que no se puede registrar o no se puede llamar desde esa caja."""


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., Any]
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    spec: ToolSpec | None = None          # nivel, etiquetas y peligrosidad (del manifiesto)
    owner: str = ""                       # brigada que la registró ("" = compartida)

    @property
    def level(self) -> Level:
        return self.spec.level if self.spec else Level.AUTO

    @property
    def dangerous(self) -> bool:
        return bool(self.spec and (self.spec.dangerous or self.spec.active_scan))

    def schema(self) -> dict:
        """Formato OpenAI (`tools=[...]`)."""
        return {"type": "function", "function": {"name": self.name, "description": self.description or
                                                 (self.spec.description if self.spec else ""),
                                                 "parameters": self.parameters}}

    async def run(self, args: dict) -> Any:
        if inspect.iscoroutinefunction(self.fn):
            return await self.fn(**args)
        return await asyncio.to_thread(self.fn, **args)


class ToolRegistry:
    def __init__(self, edition: str = "personal") -> None:
        self.edition = edition
        self._tools: dict[str, Tool] = {}
        self._disabled: set[str] = set()

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """La persona apaga o prende una tool (desde el panel). Apagada, ningún efímero la ve ni la puede llamar."""
        if name not in self._tools:
            raise ToolError(f"no hay ninguna tool {name}")
        (self._disabled.discard if enabled else self._disabled.add)(name)
        return enabled

    def enabled(self, name: str) -> bool:
        return name in self._tools and name not in self._disabled

    def register(self, tool: Tool) -> Tool:
        if self.edition == "cloud" and tool.dangerous:
            raise ToolError(f"la tool {tool.name} es peligrosa o de escaneo activo: no se carga en la nube")
        prev = self._tools.get(tool.name)
        if prev is not None and prev.owner != tool.owner:
            raise ToolError(f"ya hay una tool {tool.name} de {prev.owner or 'uso compartido'}")
        self._tools[tool.name] = tool
        return tool

    def unregister_owner(self, owner: str) -> list[str]:
        gone = [n for n, t in self._tools.items() if t.owner == owner]
        for n in gone:
            del self._tools[n]
        return gone

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list(self) -> list[dict]:
        return [{"name": t.name, "owner": t.owner, "level": t.level.value, "dangerous": t.dangerous,
                 "description": t.description, "enabled": t.name not in self._disabled}
                for t in sorted(self._tools.values(), key=lambda t: t.name)]

    def box(self, allowed: Iterable[str], *, brigade: str, gate: Gate | None = None) -> ToolBox:
        return ToolBox(self, frozenset(allowed), brigade=brigade, gate=gate)


class ToolBox:
    """Lo que ve un efímero: solo sus tools, y cada llamada pasa por la compuerta."""

    def __init__(self, registry: ToolRegistry, allowed: frozenset[str], *, brigade: str, gate: Gate | None) -> None:
        self.registry = registry
        self.allowed = allowed
        self.brigade = brigade
        self.gate = gate

    def tools(self) -> list[Tool]:
        return [t for n in sorted(self.allowed) if (t := self.registry.get(n)) is not None and self.registry.enabled(n)]

    def missing(self) -> list[str]:
        """Tools de la caja que no están registradas (la brigada las declaró pero nadie las cargó)."""
        return [n for n in sorted(self.allowed) if self.registry.get(n) is None]

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self.tools()]

    async def call(self, name: str, args: dict) -> tuple[Any, bool]:
        """(resultado, ejecutada). `ejecutada=False` = quedó pendiente de aprobación (el resultado lo explica)."""
        if name not in self.allowed:
            raise ToolError(f"la tool {name} no está en la caja de este efímero")
        tool = self.registry.get(name)
        if tool is None:
            raise ToolError(f"la tool {name} no está cargada")
        if not self.registry.enabled(name):
            raise ToolError(f"la tool {name} está desactivada por la persona")
        if self.gate is not None:
            held = await self.gate(tool, args)
            if held is not None:
                return held, False
        return await tool.run(args), True
