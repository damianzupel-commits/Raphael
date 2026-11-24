"""El reparto de un pedido entre varias brigadas: un DAG chico, validado por CÓDIGO.

Portado de JarvisRemote `orquestador/mando.py` (`Reparto`, `_dependencias`) y de la validación estricta de
`app/harness/orchestrator.py` (dependencias inexistentes, nombres repetidos, ciclos), más un presupuesto por turno.

Cada brigada es un nodo con su sub-tarea; `after[b]` = las brigadas cuyo resultado `b` necesita ANTES de empezar. Sin
dependencias, todas van en paralelo, que es siempre una ejecución válida: por eso, ante cualquier cosa rara en las
dependencias que propuso el modelo, se cae a paralelo y queda un aviso (nunca se ejecuta un plan inválido).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Plan:
    tasks: dict[str, str]                                  # brigada -> sub-tarea (en el orden del pedido)
    via: str                                               # "model" | "model+request" | "request"
    after: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def levels(self) -> list[list[str]]:
        """Orden de ejecución por niveles (cada nivel corre en paralelo). Las dependencias ya están validadas."""
        return topological_levels(list(self.tasks), self.after)

    def event(self) -> dict:
        return {"type": "plan", "tasks": dict(self.tasks), "via": self.via,
                "after": {b: list(a) for b, a in self.after.items()}, "levels": self.levels(),
                **({"warnings": list(self.warnings)} if self.warnings else {})}


def topological_levels(nodes: list[str], after: dict[str, tuple[str, ...]]) -> list[list[str]]:
    """Kahn por niveles. Lanza ValueError si hay un ciclo (no debería: `validate_after` ya lo descarta)."""
    done: set[str] = set()
    out: list[list[str]] = []
    while len(done) < len(nodes):
        level = [n for n in nodes if n not in done and set(after.get(n, ())) <= done]
        if not level:
            raise ValueError("el plan tiene un ciclo: " + ", ".join(n for n in nodes if n not in done))
        out.append(level)
        done.update(level)
    return out


def validate_after(raw: Any, nodes: list[str]) -> tuple[dict[str, tuple[str, ...]], str]:
    """Las dependencias que propuso el modelo, validadas: (dependencias, problema). Con problema, las dependencias
    vuelven vacías (todo en paralelo). Reglas: un dict; cada clave y cada dependencia es una brigada del plan; nada
    depende de sí mismo; sin ciclos. Las repetidas se juntan."""
    if raw in (None, {}, []):
        return {}, ""
    if not isinstance(raw, dict):
        return {}, "las dependencias no son un objeto"
    deps: dict[str, tuple[str, ...]] = {}
    for b, before in raw.items():
        if b not in nodes:
            return {}, f"'{b}' no es una brigada del plan"
        if not isinstance(before, list) or not before:
            return {}, f"las dependencias de '{b}' no son una lista"
        for a in before:
            if not isinstance(a, str) or a not in nodes:
                return {}, f"'{b}' depende de '{a}', que no es una brigada del plan"
            if a == b:
                return {}, f"'{b}' depende de sí misma"
        deps[b] = tuple(dict.fromkeys(before))
    try:
        topological_levels(nodes, deps)
    except ValueError as exc:
        return {}, str(exc)
    return deps, ""


def apply_budget(plan: Plan, *, max_brigades: int, max_levels: int) -> Plan:
    """El presupuesto del turno: como mucho `max_brigades` nodos (se quedan los primeros) y `max_levels` niveles (si
    se pasa, todo en paralelo). Lo que se recorta queda dicho en los avisos."""
    tasks, after, warnings = dict(plan.tasks), dict(plan.after), list(plan.warnings)
    if len(tasks) > max_brigades:
        keep = list(tasks)[:max_brigades]
        cut = [b for b in tasks if b not in keep]
        tasks = {b: tasks[b] for b in keep}
        warnings.append(f"presupuesto del turno: van {max_brigades} brigadas; quedaron afuera {', '.join(cut)}")
        after = {b: tuple(a for a in deps if a in tasks) for b, deps in after.items() if b in tasks}
        after = {b: d for b, d in after.items() if d}
    new = Plan(tasks, plan.via, after, warnings)
    if len(new.levels()) > max_levels:
        warnings.append(f"presupuesto del turno: el plan pedía {len(new.levels())} etapas (máximo {max_levels}); "
                        "van todas en paralelo")
        new = Plan(tasks, plan.via, {}, warnings)
    return new
