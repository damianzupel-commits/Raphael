"""Tests del harness multi-agente (motor de orquestación).

El spec (§2) promete que el orquestador es testeable con agentes FAKE y que cada
agente es testeable aislado. Estos tests cumplen esa promesa sin tocar LLM ni red.
Las funciones son sync (envuelven asyncio.run) para correr bajo pytest sin plugins.
"""

from __future__ import annotations

import asyncio

import pytest

from app.harness.a2a import Message, MessageBus
from app.harness.blackboard import ExecutionStore, MemoryBlackboard
from app.harness.contracts import AgentResult, Node, Task
from app.harness.orchestrator import Budget, DAGError, Orchestrator, topological_order
from app.harness.routing import DEFAULT_TIER_MODELS, NoModelForTier, resolve_model
from app.harness.worktrees import merge_results, partition_files


# --- Agente fake reutilizable --------------------------------------------------
class FakeAgent:
    def __init__(self, name, *, tier=0, ok=True, output=None, fails_until=0, log=None):
        self.name = name
        self.tier = tier
        self.tools = []
        self._ok = ok
        self._output = output or {}
        self._fails_until = fails_until  # falla las primeras N veces, después ok
        self._calls = 0
        self._log = log

    async def run(self, task: Task, bb) -> AgentResult:
        self._calls += 1
        if self._log is not None:
            self._log.append(self.name)
        if self._fails_until and self._calls <= self._fails_until:
            return AgentResult.fail(f"{self.name} falla intento {self._calls}")
        if not self._ok:
            return AgentResult.fail(f"{self.name} configurado para fallar")
        return AgentResult(ok=True, output={**self._output, "by": self.name})


def _run(coro):
    return asyncio.run(coro)


# --- DAG: orden, ciclos, deps --------------------------------------------------
def test_orden_topologico_respeta_dependencias():
    nodes = [
        Node(FakeAgent("c"), depends_on=["b"]),
        Node(FakeAgent("b"), depends_on=["a"]),
        Node(FakeAgent("a")),
    ]
    assert topological_order(nodes) == ["a", "b", "c"]


def test_ciclo_es_rechazado():
    nodes = [
        Node(FakeAgent("a"), depends_on=["b"]),
        Node(FakeAgent("b"), depends_on=["a"]),
    ]
    with pytest.raises(DAGError):
        topological_order(nodes)


def test_dependencia_inexistente_es_rechazada():
    nodes = [Node(FakeAgent("a"), depends_on=["fantasma"])]
    with pytest.raises(DAGError):
        topological_order(nodes)


def test_nombres_duplicados_rechazados():
    nodes = [Node(FakeAgent("a")), Node(FakeAgent("a"))]
    with pytest.raises(DAGError):
        topological_order(nodes)


def test_on_error_invalido_rechazado():
    with pytest.raises(ValueError):
        Node(FakeAgent("a"), on_error="explota")


# --- Ejecución -----------------------------------------------------------------
def test_corre_en_orden_y_pasa_output_por_pizarra():
    order_log: list[str] = []
    nodes = [
        Node(FakeAgent("scan", log=order_log, output={"n": 3})),
        Node(FakeAgent("triage", log=order_log), depends_on=["scan"]),
        Node(FakeAgent("report", log=order_log), depends_on=["triage"]),
    ]
    report = _run(Orchestrator().run(nodes, Task(id="t")))
    assert report.ok
    assert order_log == ["scan", "triage", "report"]
    # el output de scan quedó en la pizarra
    assert report.blackboard.read("scan")["n"] == 3
    assert report.store.summary()["ok"] == 3


def test_nodo_critico_que_falla_corta_su_rama_pero_no_las_otras():
    nodes = [
        Node(FakeAgent("a", ok=False), on_error="abort"),
        Node(FakeAgent("b"), depends_on=["a"]),   # depende de a -> se saltea
        Node(FakeAgent("c")),                      # independiente -> corre igual
    ]
    report = _run(Orchestrator().run(nodes, Task(id="t")))
    assert not report.ok
    assert "a" in report.aborted
    assert "b" in report.skipped
    assert report.store.is_done_ok("c")  # la rama independiente sí corrió


def test_nodo_opcional_skip_no_voltea_la_corrida():
    nodes = [
        Node(FakeAgent("a")),
        Node(FakeAgent("opt", ok=False), depends_on=["a"], on_error="skip"),
    ]
    report = _run(Orchestrator().run(nodes, Task(id="t")))
    assert report.ok  # skip no marca la corrida como fallida
    assert "opt" in report.skipped


def test_retry_reintenta_hasta_exito():
    agent = FakeAgent("flaky", fails_until=2)  # falla 2 veces, éxito a la 3ra
    nodes = [Node(agent, on_error="retry", max_retries=3)]
    report = _run(Orchestrator().run(nodes, Task(id="t")))
    assert report.ok
    assert report.store.get("flaky").attempts == 3


def test_presupuesto_de_nodos_corta():
    nodes = [Node(FakeAgent(n)) for n in ["a", "b", "c", "d"]]
    report = _run(Orchestrator().run(nodes, Task(id="t"), budget=Budget(max_nodes=2)))
    assert report.stopped_by_budget
    assert report.store.summary()["nodes_run"] == 2


def test_reanudacion_saltea_nodos_ya_ok():
    store = ExecutionStore()
    store.record("a", AgentResult(ok=True, output={"cached": True}), attempts=1, seconds=0.0)
    a = FakeAgent("a")  # si corriera, incrementaría _calls
    nodes = [Node(a), Node(FakeAgent("b"), depends_on=["a"])]
    report = _run(Orchestrator().run(nodes, Task(id="t"), store=store))
    assert report.ok
    assert a._calls == 0  # no se re-ejecutó
    assert report.blackboard.read("a") == {"cached": True}


def test_agente_que_tira_excepcion_no_voltea_la_corrida():
    class Boom:
        name, tier, tools = "boom", 0, []
        async def run(self, task, bb):
            raise RuntimeError("kaboom")

    nodes = [Node(Boom(), on_error="skip")]
    report = _run(Orchestrator().run(nodes, Task(id="t")))
    assert "boom" in report.skipped
    assert "kaboom" in (report.store.get("boom").error or "")


# --- Routing por tier ----------------------------------------------------------
def test_tier0_no_usa_modelo():
    assert resolve_model(0) is None


def test_tier2_usa_primario():
    assert resolve_model(2) == DEFAULT_TIER_MODELS[2][0]


def test_fallback_cuando_primario_no_disponible():
    # Lista propia: la del tier 2 sale de TIER2_FREE_MODELS del .env y puede tener un solo modelo.
    modelos = {2: ["modelo-primario", "modelo-respaldo"]}
    got = resolve_model(2, tier_models=modelos, is_available=lambda m: m != "modelo-primario")
    assert got == "modelo-respaldo"


def test_sin_modelos_disponibles_falla_claro():
    with pytest.raises(NoModelForTier):
        resolve_model(2, is_available=lambda _m: False)


# --- Worktrees (lógica pura) ---------------------------------------------------
def test_particion_por_cantidad_balanceada():
    chunks = partition_files([f"f{i}" for i in range(10)], 3)
    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 10
    assert max(len(c) for c in chunks) - min(len(c) for c in chunks) <= 1


def test_particion_por_tamano_greedy():
    files = ["big", "s1", "s2", "s3"]
    sizes = {"big": 100, "s1": 10, "s2": 10, "s3": 10}
    chunks = partition_files(files, 2, size_of=lambda f: sizes[f])
    loads = [sum(sizes[f] for f in c) for c in chunks]
    # el archivo gigante queda solo de un lado, el resto del otro
    assert max(loads) == 100


def test_particion_vacia_y_mas_chunks_que_archivos():
    assert partition_files([], 4) == []
    assert len(partition_files(["a", "b"], 5)) == 2


def test_merge_descarta_duplicados_por_id():
    class F:
        def __init__(self, i): self.id = i
    a, b, c = F(1), F(2), F(1)
    merged = merge_results([[a, b], [c]])
    assert [x.id for x in merged] == [1, 2]


# --- A2A (anti-bucle) ----------------------------------------------------------
def test_conversacion_normal_termina_sola():
    bus = MessageBus()

    async def redactor(msg: Message):
        if msg.kind == "request_rewrite":
            return Message("redactor", "catador", "rewritten", {"text": "ok"})
        return None

    async def catador(msg: Message):
        return None  # acepta, no responde -> fin

    bus.register("redactor", redactor)
    bus.register("catador", catador)
    transcript = _run(bus.run_conversation(Message("catador", "redactor", "request_rewrite")))
    assert [m.kind for m in transcript] == ["request_rewrite", "rewritten"]


def test_anti_bucle_ttl_corta():
    bus = MessageBus(max_hops=4, max_messages=999)

    async def ping(msg: Message):
        return Message("a", "b", "ping")  # rebota para siempre

    async def pong(msg: Message):
        return Message("b", "a", "pong")

    bus.register("a", ping)
    bus.register("b", pong)
    transcript = _run(bus.run_conversation(Message("a", "b", "ping")))
    # el TTL corta: no crece indefinidamente
    assert len(transcript) <= 6


def test_anti_bucle_presupuesto_corta():
    bus = MessageBus(max_hops=9999, max_messages=5)

    async def ping(msg: Message):
        return Message("a", "b", "ping")

    async def pong(msg: Message):
        return Message("b", "a", "pong")

    bus.register("a", ping)
    bus.register("b", pong)
    transcript = _run(bus.run_conversation(Message("a", "b", "ping")))
    assert len(transcript) == 5  # se corta en el presupuesto
