"""El orquestador (Sous-Chef) — motor de ejecución del DAG (spec §3).

Construye y valida el grafo (sin ciclos = sin bucles infinitos por
construcción), lo ordena topológicamente, y corre cada nodo cuando TODAS sus
dependencias terminaron ok. Maneja errores por política de nodo
(retry/skip/abort), respeta un presupuesto global (cortacircuitos), y loguea
cada transición. La corrida es reanudable vía el ExecutionStore.

Hub-and-spoke: los nodos no se hablan entre sí; el output de cada uno se pasa a
los siguientes por la pizarra. Empezar SECUENCIAL (spec §3.3); el paralelismo
se agrega solo donde se mida beneficio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from .blackboard import ExecutionStore, MemoryBlackboard
from .contracts import AgentResult, Blackboard, Node, Task

logger = logging.getLogger("jarvis.harness")


class DAGError(ValueError):
    """DAG inválido: dependencia inexistente, nombres duplicados, o ciclo."""


@dataclass
class Budget:
    """Cortacircuitos global de la corrida (spec §3.6)."""
    max_nodes: int | None = None
    max_seconds: float | None = None


@dataclass
class RunReport:
    ok: bool
    store: ExecutionStore
    blackboard: Blackboard
    skipped: list[str] = field(default_factory=list)
    aborted: list[str] = field(default_factory=list)
    stopped_by_budget: bool = False

    @property
    def summary(self) -> dict[str, Any]:
        s = self.store.summary()
        # OJO: no pisar la clave "ok" del store (que es el CONTEO de nodos ok);
        # el booleano de toda la corrida va como "run_ok" para no colisionar.
        s.update(
            {
                "run_ok": self.ok,
                "skipped": self.skipped,
                "aborted": self.aborted,
                "stopped_by_budget": self.stopped_by_budget,
            }
        )
        return s


def validate_dag(nodes: list[Node]) -> None:
    """Chequea nombres únicos y dependencias existentes. No ordena (eso es
    `topological_order`), pero detecta los dos errores más groseros primero."""
    names = [n.name for n in nodes]
    if len(names) != len(set(names)):
        dupes = sorted({x for x in names if names.count(x) > 1})
        raise DAGError(f"nombres de nodo duplicados: {dupes}")
    known = set(names)
    for n in nodes:
        for dep in n.depends_on:
            if dep not in known:
                raise DAGError(f"nodo {n.name!r} depende de {dep!r}, que no existe en el grafo")


def topological_order(nodes: list[Node]) -> list[str]:
    """Orden topológico por Kahn. Si queda algún nodo sin poder ordenar, hay un
    ciclo -> DAGError (el grafo debe ser ACÍCLICO)."""
    validate_dag(nodes)
    node_by_name = {n.name: n for n in nodes}
    indegree = {n.name: 0 for n in nodes}
    dependents: dict[str, list[str]] = {n.name: [] for n in nodes}
    for n in nodes:
        for dep in n.depends_on:
            indegree[n.name] += 1
            dependents[dep].append(n.name)

    # cola estable (orden de declaración) para que el resultado sea determinista
    ready = [n.name for n in nodes if indegree[n.name] == 0]
    order: list[str] = []
    while ready:
        name = ready.pop(0)
        order.append(name)
        for child in dependents[name]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)

    if len(order) != len(nodes):
        in_cycle = sorted(name for name, d in indegree.items() if d > 0)
        raise DAGError(f"el grafo tiene un ciclo (no se pueden ordenar: {in_cycle})")
    return order


class Orchestrator:
    """Ejecuta una brigada (lista de nodos) en orden topológico."""

    def __init__(self, name: str = "brigada") -> None:
        self.name = name

    async def _run_once(self, node: Node, task: Task, bb: Blackboard) -> tuple[AgentResult, float]:
        start = monotonic()
        try:
            result = await node.agent.run(task, bb)
        except Exception as exc:  # noqa: BLE001 -- un agente que tira NO debe voltear la corrida
            result = AgentResult.fail(f"excepción en {node.name}: {exc!r}")
        return result, monotonic() - start

    async def run(
        self,
        nodes: list[Node],
        task: Task,
        bb: Blackboard | None = None,
        store: ExecutionStore | None = None,
        budget: Budget | None = None,
    ) -> RunReport:
        bb = bb if bb is not None else MemoryBlackboard()
        store = store if store is not None else ExecutionStore()
        budget = budget or Budget()

        order = topological_order(nodes)  # valida + ordena (o levanta DAGError)
        node_by_name = {n.name: n for n in nodes}

        skipped: list[str] = []
        aborted: list[str] = []
        stopped_by_budget = False
        run_started = monotonic()
        nodes_executed = 0

        for name in order:
            node = node_by_name[name]

            # Presupuesto (cortacircuitos).
            if budget.max_nodes is not None and nodes_executed >= budget.max_nodes:
                stopped_by_budget = True
                logger.warning("[%s] presupuesto de nodos agotado en %s", self.name, name)
                break
            if budget.max_seconds is not None and (monotonic() - run_started) > budget.max_seconds:
                stopped_by_budget = True
                logger.warning("[%s] presupuesto de tiempo agotado en %s", self.name, name)
                break

            # Reanudación: si ya terminó ok en una corrida previa, se reutiliza.
            if store.is_done_ok(name):
                rec = store.get(name)
                if rec is not None:
                    bb.write(name, rec.output)
                logger.info("[%s] %s ya estaba ok (reanudado), se saltea", self.name, name)
                continue

            # ¿Alguna dependencia falló o se salteó? -> esta rama no corre.
            broken = [d for d in node.depends_on if (d in skipped or d in aborted or not store.is_done_ok(d))]
            if broken:
                skipped.append(name)
                logger.info("[%s] %s saltea: dependencia rota %s", self.name, name, broken)
                continue

            # Ejecutar con reintentos según política.
            attempts = 0
            max_attempts = node.max_retries + 1 if node.on_error == "retry" else 1
            result = AgentResult.fail("no ejecutado")
            seconds = 0.0
            while attempts < max_attempts:
                attempts += 1
                logger.info("[%s] ▶ %s (intento %d/%d)", self.name, name, attempts, max_attempts)
                result, secs = await self._run_once(node, task, bb)
                seconds += secs
                if result.ok:
                    break
                logger.warning("[%s] %s falló: %s", self.name, name, result.error)

            nodes_executed += 1
            store.record(name, result, attempts, seconds)

            if result.ok:
                bb.write(name, result.output)
                logger.info("[%s] ✔ %s ok (%.3fs)", self.name, name, seconds)
            else:
                if node.on_error == "skip":
                    skipped.append(name)
                    logger.info("[%s] %s falló pero es opcional (skip), sigo", self.name, name)
                else:  # retry agotado o abort -> corta ESTA rama (los dependientes se saltean)
                    aborted.append(name)
                    logger.warning("[%s] ✖ %s abortado, se corta su rama", self.name, name)

        ok = not aborted and not stopped_by_budget
        return RunReport(
            ok=ok,
            store=store,
            blackboard=bb,
            skipped=skipped,
            aborted=aborted,
            stopped_by_budget=stopped_by_budget,
        )
