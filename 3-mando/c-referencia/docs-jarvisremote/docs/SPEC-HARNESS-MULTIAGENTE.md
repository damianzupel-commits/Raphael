# 🧩 Spec técnico — Harness Multi-Agente (motor de orquestación)

> **Documento de DISEÑO, no de construcción.** Describe el motor genérico que ejecuta
> "brigadas" (grafos de agentes). Se construye en **4to año del estudio (M14) /
> post primera venta** (F1-2 del roadmap). Escribirlo ahora sirve para tener el plano
> claro y saciar la curiosidad de arquitecto sin construir sobre arena.
>
> Relación con lo existente: `docs/BRIGADA-AUDITORIA.md` es UNA instancia (el pipeline
> de auditoría); `docs/LA-BRIGADA.md` es la metáfora. Este doc es el **motor reusable**
> que corre cualquier brigada. Creado: 2026-09-09.

---

## 0. Punto de partida: qué hay hoy vs qué agrega esto
- **Hoy:** `agent.py` es un arnés de **un solo agente** (loop LLM → tool → LLM, con
  reintentos, trimming de contexto, ~100 tools). Funciona y alcanza para tareas de un frente.
- **Esto:** la capa que se monta ENCIMA para coordinar **varios agentes** especializados,
  cada uno con su contexto chico y su rol. Reutiliza lo que ya existe (`tools/`,
  `llm_client`, `config`, el vault como pizarra, `_log_llm_usage`).
- **Principios rectores** (heredados del blueprint y la brigada): hub-and-spoke + pizarra;
  cada estación se gana su lugar; model routing por tier; delegar de a uno, verificando.

---

## 1. Modelo conceptual (las 4 piezas)
- **Agente (nodo):** unidad con un rol, contexto acotado, set de tools propio (menor
  privilegio), un tier de modelo, y una función `run(task, blackboard) -> result`.
  Puede ser determinista (sin LLM) o con LLM.
- **Grafo (DAG):** nodos + aristas de dependencia (arista = "B necesita el output de A").
  **Acíclico**: sin ciclos = sin bucles infinitos por construcción.
- **Orquestador (Sous-Chef):** ejecuta el DAG en orden topológico, pasa outputs entre
  nodos, maneja errores, agrega el resultado final.
- **Pizarra (Blackboard):** estado compartido donde los agentes leen/escriben. Nadie se
  habla directo; todo pasa por el orquestador o la pizarra. Respaldada por el vault de
  Obsidian (largo plazo) + un store de ejecución (por corrida).

---

## 2. Contratos / interfaces (el corazón del spec)
Las abstracciones mínimas, en pseudo-Python:

```python
@dataclass
class Task:
    id: str
    payload: dict          # input, ej. {"repo_path": "..."}
    context_ref: str       # puntero a la pizarra

@dataclass
class AgentResult:
    ok: bool
    output: dict
    artifacts: list[str]   # refs a artefactos en la pizarra
    error: str | None = None

class Agent(Protocol):
    name: str
    tier: int              # 0 determinista · 1 rápido · 2 potente
    tools: list[str]       # subset ACOTADO (no ve las tools de otras estaciones)
    async def run(self, task: Task, bb: "Blackboard") -> AgentResult: ...

@dataclass
class Node:
    agent: Agent
    depends_on: list[str]  # names de nodos previos que deben terminar OK

class Blackboard(Protocol):
    def read(self, key: str): ...
    def write(self, key: str, value) -> None: ...
    # respaldo: vault de Obsidian (persistente) + ExecutionStore (por corrida)
```
Contrato clave: **un Agente es testeable aislado** (input → output puro), y el
orquestador es testeable con agentes fake. Esto es lo que hace el sistema mantenible.

---

## 3. El orquestador (motor de ejecución)
1. **Construir + validar el DAG:** detectar ciclos (si hay ciclo → error, no se ejecuta),
   ordenar topológicamente.
2. **Programar nodos:** un nodo corre cuando TODAS sus dependencias terminaron `ok=True`.
3. **Concurrencia:** nodos sin dependencia mutua pueden correr en paralelo:
   - I/O-bound (llamadas a LLM/API): `asyncio.gather`.
   - Filesystem del repo: git worktrees (§5).
   Empezar **secuencial**; agregar paralelo solo donde se mida beneficio.
4. **Paso de datos:** el output de una dependencia se pasa como input vía la pizarra
   (no por variables globales).
5. **Manejo de errores (política por nodo):** `retry(n)` / `skip` (si es opcional) /
   `abort` (si es crítico → corta esa rama del grafo, no todo).
6. **Anti-bucle / presupuesto:** el DAG ya garantiza sin ciclos; además un presupuesto
   global por corrida (max nodos, max tiempo, max costo/tokens) que corta si se pasa.
7. **Observabilidad:** loguea cada transición (inicio/fin/costo/tokens por nodo) —
   extiende el `_log_llm_usage` que ya tenés.

---

## 4. Comunicación entre agentes (dos versiones)
- **V1 — hub-and-spoke (empezar acá):** los agentes NO se hablan entre sí. El orquestador
  reparte y junta; el estado compartido vive en la pizarra. Más simple, robusto y barato;
  no se rompe con un modelo mediano.
- **V2 — A2A (solo cuando V1 se quede corto):** protocolo agente-a-agente para negociación
  bidireccional (ej. el Catador le pide al Redactor que reescriba una sección). Con
  **protección anti-bucle**: presupuesto de mensajes + TTL por conversación. No construir
  hasta que un caso real lo justifique.

---

## 5. Paralelismo con git worktrees
- **Problema:** varios agentes escribiendo sobre el mismo repo se pisan.
- **Solución:** cada agente que MODIFICA archivos corre en su propio `git worktree`
  (copia de trabajo aislada, misma historia de git). Flujo:
  `git worktree add` → el agente trabaja y commitea ahí → el orquestador integra
  (cherry-pick/merge) → `git worktree remove`.
- Los agentes **read-only** (escaneo, triage) no necesitan worktree: comparten el checkout.
- Esta es la respuesta técnica a "auditar/operar sobre un codebase gigante en paralelo".

---

## 6. Model routing por tier (F1-6)
- Mapa `{tier: modelo}` en config (extiende lo que ya existe: `cloud_expert`=Gemini,
  embeddings=nomic).
  - **Tier 0:** sin modelo (determinista: escaneo, config, ensamblado).
  - **Tier 1:** chico/rápido (router/clasificador, chequeos simples). Corren mucho.
  - **Tier 2:** potente (triage, redacción, catador, orquestador). Donde el LLM razona.
- El agente declara su `tier`; el harness le inyecta el cliente del modelo correcto, con
  **fallback** si un proveedor se cae.

---

## 7. Estado y persistencia (la pizarra)
- **ExecutionStore (por corrida):** inputs/outputs/artefactos de cada nodo. Hace la corrida
  **auditable** y **reanudable**.
- **Vault de Obsidian (largo plazo):** memoria compartida entre corridas (lo que ya usás).
- **Reanudación:** si una corrida se corta, se retoma desde el último nodo `ok=True` (los
  outputs previos están en el store). Idempotencia por nodo cuando sea posible.

---

## 8. Seguridad y control (respeta tus gates)
- Nodos con **side-effects** (aplicar fixes, pentest activo, borrar) requieren
  **confirmación manual** (dry-run → confirm), igual que hoy. El orquestador NO auto-aplica
  lo irreversible.
- **Menor privilegio:** cada agente ve solo sus tools, no las de las otras estaciones.
- Presupuestos de costo/tiempo como cortacircuitos.

---

## 9. Plan de evolución sobre Raphael (cómo se monta sin romper nada)
- **Fase A:** envolver el loop actual de `agent.py` como un `Agent` genérico (nodo tier 2).
  No cambia el comportamiento; solo lo hace "encajable" en un grafo.
- **Fase B:** extraer las estaciones de auditoría (scan, contexto, triage, config,
  redacción, catador, pase) como `Agent`s con el contrato del §2. Ya existen como
  funciones en `audit_report.py`/`security/`; es refactor, no invención.
- **Fase C:** el orquestador ejecuta el DAG de esas estaciones (reemplaza la secuencia
  lineal de `generate_client_report`).
- **Fase D:** paralelismo (worktrees) + routing por tier.
- **Fase E:** A2A, solo si hace falta.

Cada fase es un incremento chequeable, no un big-bang.

---

## 10. Riesgos y decisiones abiertas
- **Complejidad vs valor:** no construir V2/A2A ni worktrees hasta que el caso real los
  pida. Un DAG secuencial hub-and-spoke ya es el 80% del valor.
- **Concurrencia:** empezar secuencial; paralelizar solo lo que se mida.
- **Sobre-ingeniería:** el enemigo. La brigada se gana estación por estación; el motor,
  fase por fase. Si no hay 2-3 estaciones que coordinar, el orquestador formal no se justifica.

---

## Referencias
- [`BRIGADA-AUDITORIA.md`](BRIGADA-AUDITORIA.md) — la instancia (pipeline de auditoría).
- [`LA-BRIGADA.md`](LA-BRIGADA.md) — la metáfora de cocina.
- [`ROADMAP-MEJORAS-RAPHAEL.md`](ROADMAP-MEJORAS-RAPHAEL.md) — F1-2 (brigada), F1-6 (routing).
- Corresponde a **M14** del `Plan-de-Estudios-Agentes-IA.md` (4to año) y al examen final de
  Fase 1 de `Estrategia-Carrera-IA-Seguridad.md`.
