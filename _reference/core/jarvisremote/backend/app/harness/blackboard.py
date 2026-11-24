"""Pizarra en memoria + ExecutionStore (spec §7).

La pizarra es el estado compartido de una corrida. El ExecutionStore guarda el
resultado de cada nodo para que la corrida sea AUDITABLE y REANUDABLE: si se
corta, se retoma desde el último nodo `ok=True` sin recalcular lo anterior.

Esta implementación es en memoria (testeable, sin dependencias). El respaldo
persistente (vault de Obsidian / disco) se enchufa como adaptador después, sin
cambiar el contrato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import AgentResult


class MemoryBlackboard:
    """Pizarra en memoria. Cumple el Protocol `Blackboard`."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def read(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def write(self, key: str, value: Any) -> None:
        self._store[key] = value

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def snapshot(self) -> dict[str, Any]:
        return dict(self._store)


@dataclass
class NodeRecord:
    node: str
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempts: int = 0
    seconds: float = 0.0


class ExecutionStore:
    """Registro de la corrida: un `NodeRecord` por nodo ejecutado. Permite
    reanudar (saltear nodos que ya terminaron ok) y auditar qué pasó."""

    def __init__(self) -> None:
        self._records: dict[str, NodeRecord] = {}

    def record(self, node: str, result: AgentResult, attempts: int, seconds: float) -> None:
        self._records[node] = NodeRecord(
            node=node,
            ok=result.ok,
            output=result.output,
            error=result.error,
            attempts=attempts,
            seconds=seconds,
        )

    def get(self, node: str) -> NodeRecord | None:
        return self._records.get(node)

    def is_done_ok(self, node: str) -> bool:
        rec = self._records.get(node)
        return rec is not None and rec.ok

    def all_records(self) -> list[NodeRecord]:
        return list(self._records.values())

    def summary(self) -> dict[str, Any]:
        recs = self.all_records()
        return {
            "nodes_run": len(recs),
            "ok": sum(1 for r in recs if r.ok),
            "failed": [r.node for r in recs if not r.ok],
            "total_seconds": round(sum(r.seconds for r in recs), 3),
        }
