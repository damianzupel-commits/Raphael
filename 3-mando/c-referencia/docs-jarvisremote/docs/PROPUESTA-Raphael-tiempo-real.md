# PROPUESTA — Raphael auditando código en tiempo real

> Estado: **PROPUESTA / idea de diseño (NO implementado).** Creado el 2026-09-26.
> Sector: docs de diseño de Raphael. No mezclar con specs ya implementados.
> Nace de una pregunta de Damian: "¿Raphael podría auditar código en tiempo real?".

---

## Respuesta corta
Sí, en **"casi tiempo real"**, y Raphael ya tiene casi todas las piezas. Lo que NO
es realista es "verificación LLM completa por cada tecla" — eso no lo hace ningún
sistema (el LLM es demasiado lento/caro para latencia de tipeo).

## El modelo correcto: dos velocidades
La auditoría tiene dos partes con costos MUY distintos:
- **Escaneo determinista** (Semgrep/Bandit/Ruff…): rápido (segundos), sobre todo si
  corre solo sobre el **archivo/diff que cambió**, no el repo entero.
- **Triage + Catador con LLM** (leer el código real, distinguir falsos positivos,
  verificar el informe): lento y caro. NO va por tecla.

Entonces el diseño es de **dos pisos** (la misma idea que venimos usando):

| Disparador | Qué corre | Latencia | Para qué |
|---|---|---|---|
| **Al guardar (on-save)** | escaneo determinista del archivo cambiado + reglas | ~segundos | feedback instantáneo estilo IDE |
| **Al commitear / abrir PR** | escaneo del diff + **triage/Catador LLM** (async) | ~segundos a min | profundidad, falsos positivos, informe |

## Piezas que Raphael YA tiene (no hay que inventar)
- **File-watcher:** el del módulo `malware/` (watchdog) ya observa cambios en disco.
  Se reusa para disparar el re-escaneo incremental.
- **Grafo del código** (`codebase/`): sabe qué archivos/funciones afecta un cambio →
  permite auditar solo el subgrafo impactado, no todo.
- **Harness / Brigada** (`harness/`): el DAG podría re-correr **solo las estaciones
  afectadas** por el diff (reanudable vía el ExecutionStore).
- **Cache por proyecto** (`security/`, `quality/` store): evita re-escanear lo que no
  cambió.
- **LAYA (experimento):** un modelo de decisión local podría hacer el **triage
  instantáneo** del piso rápido (real vs falso positivo tentativo), escalando a
  DeepSeek solo en el commit. Ver `EXPERIMENTO-JEV-motor-de-decisiones.md`.

## Arquitectura propuesta (por fases)
1. **Modo incremental:** dado un diff/archivo, correr escáneres solo sobre eso +
   mapear con el grafo qué más toca. (Aditivo sobre `security_scan_project`.)
2. **Watch mode:** enganchar el watcher a (1) → auditoría al guardar, resultados en un
   panel (o subrayado si algún día hay plugin de editor).
3. **Gate de commit/PR:** hook de git (pre-commit / CI) que corre la Brigada sobre el
   diff con el LLM (async), y bloquea/avisa según severidad.
4. **Triage rápido con LAYA** en el piso on-save; DeepSeek solo en el piso de commit.

## Límites honestos
- La verificación profunda (Catador contra el código real) **no** es de latencia de
  tipeo — corre async o al commit. Prometer "cada tecla con verificación LLM" sería
  humo.
- Escanear demasiado seguido genera ruido/falsos positivos; el piso on-save debe ser
  conservador (solo lo del archivo cambiado, reglas de alta confianza).
- Es una **propuesta**: no tocar el producto hasta diseñarlo bien y poder testear en
  vivo (misma disciplina que el resto de Raphael).

## Valor
"Encontrá el agujero **mientras escribís**, no después de shippear" — es el enfoque
shift-left, el más vendible, y encaja con el diferencial local/verificado de Raphael.

## Fuente
- Conversación 2026-09-26. Relacionado: `EXPERIMENTO-JEV-motor-de-decisiones.md`
  (LAYA para el triage rápido), `SPEC-HARNESS-MULTIAGENTE.md`, `BRIGADA-AUDITORIA.md`.
