"""Harness multi-agente: el motor genérico que ejecuta "brigadas" (grafos de
agentes especializados). Ver `docs/SPEC-HARNESS-MULTIAGENTE.md`.

Construido de forma ADITIVA (2026-09-20): estos módulos son el motor reusable;
NO reemplazan todavía el pipeline lineal de `audit_report.generate_client_report`
(que sigue siendo el camino de producción). La integración real de las estaciones
de auditoría como nodos del DAG es la Fase C del spec y se activa cuando se pueda
testear contra el backend en vivo.

Piezas (spec §1):
- `contracts`  — Task, AgentResult, Agent (Protocol), Node, Blackboard (Protocol).
- `blackboard` — pizarra en memoria + ExecutionStore (estado por corrida, reanudable).
- `orchestrator`— el Sous-Chef: valida el DAG (sin ciclos), lo corre en orden topológico.
- `routing`    — model routing por tier con fallback.
- `worktrees`  — paralelismo con git worktrees + lógica pura de partición/merge.
- `a2a`        — comunicación agente-a-agente V2 (con anti-bucle: TTL + presupuesto).
"""
