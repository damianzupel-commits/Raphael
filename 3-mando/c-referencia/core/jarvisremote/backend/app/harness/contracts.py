"""Contratos / interfaces del harness multi-agente (spec §2).

Las abstracciones mínimas. El punto clave: un Agente es testeable AISLADO
(input -> output puro), y el orquestador es testeable con agentes fake. Eso es
lo que hace el sistema mantenible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Task:
    """Unidad de trabajo que entra a un nodo."""
    id: str
    payload: dict[str, Any] = field(default_factory=dict)  # ej. {"repo_path": "..."}
    context_ref: str = ""  # puntero a la pizarra (namespace de esta corrida)


@dataclass
class AgentResult:
    """Salida de un agente. `ok=False` + `error` cuando falla."""
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)  # refs a artefactos en la pizarra
    error: str | None = None

    @staticmethod
    def fail(error: str) -> "AgentResult":
        return AgentResult(ok=False, output={}, artifacts=[], error=error)


@runtime_checkable
class Agent(Protocol):
    """Un nodo ejecutable. Determinista (tier 0) o con LLM (tier 1/2).

    `tools` es un subset ACOTADO (menor privilegio: no ve las tools de otras
    estaciones). El harness inyecta el cliente del modelo del tier correcto.
    """
    name: str
    tier: int  # 0 determinista · 1 rápido · 2 potente
    tools: list[str]

    async def run(self, task: Task, bb: "Blackboard") -> AgentResult: ...


# Política de error por nodo (spec §3.5).
ERROR_POLICIES = ("retry", "skip", "abort")


@dataclass
class Node:
    """Un agente + sus dependencias en el grafo."""
    agent: Agent
    depends_on: list[str] = field(default_factory=list)  # names de nodos previos
    on_error: str = "abort"  # "retry" | "skip" | "abort"
    max_retries: int = 1

    @property
    def name(self) -> str:
        return self.agent.name

    def __post_init__(self) -> None:
        if self.on_error not in ERROR_POLICIES:
            raise ValueError(
                f"on_error inválido: {self.on_error!r} (usá uno de {ERROR_POLICIES})"
            )


@runtime_checkable
class Blackboard(Protocol):
    """Estado compartido. Nadie se habla directo: todo pasa por la pizarra o el
    orquestador. Respaldo real: vault de Obsidian (persistente) + ExecutionStore
    (por corrida). Acá el contrato mínimo."""

    def read(self, key: str, default: Any = None) -> Any: ...
    def write(self, key: str, value: Any) -> None: ...
