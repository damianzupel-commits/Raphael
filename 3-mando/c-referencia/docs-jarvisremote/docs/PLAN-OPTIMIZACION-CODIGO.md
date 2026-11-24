# Plan de optimización de código — seguro y ordenado

> Creado el 2026-09-25. Basado en `ANALISIS-CODIGO-RAPHAEL.md`. Objetivo: mantener
> el código limpio y optimizarlo **sin romper el Raphael que funciona.**
>
> **Principio rector:** contener, no reconstruir. Cambios **chicos**, uno por vez,
> **cada uno verificado con los tests**. Nada de refactors grandes a ciegas.

## Regla de oro (la que evita el cliché de "la IA se enredó")
Antes y después de CADA paso: correr los tests en Windows.
```
cd backend
.venv\Scripts\python.exe -m pytest -q
```
Si un paso pone algo en rojo, se revierte ese paso y listo. Sin esa red, no se toca
el núcleo.

## Alcance: la cadena del Auditor (no "todo")
Optimizamos lo que usa el **producto** (auditar código). El lab (investigation,
malware, ingestion, pentest, phone) **no se toca** en esta pasada: es más superficie,
más riesgo, y no cobra. Menos es más.

La cadena del Auditor:
`agent.py` (núcleo) → `tools/` (routing) → `security/` + `quality/` + `findings/`
→ `harness/` (brigada) → `audit_report.py` → `obsidian/` (guardado).

---

## Pasos (ordenados por valor/riesgo — de menor a mayor riesgo)

### Paso 0 — Red de seguridad: tests corriendo *(obligatorio, primero)*
- Correr `pytest` y ver que pase (o anotar qué falla HOY, para no confundir un
  fallo previo con uno nuestro).
- Si hay tests Windows-only que molestan, marcarlos con `@pytest.mark` para poder
  correr el resto en cualquier lado (habilita CI a futuro).
- **Riesgo: nulo. Habilita todo lo demás.**

### Paso 1 — Tool-routing por dominio (QW-1) *(alto valor, riesgo bajo-medio)*
- Hoy se cargan las **104 tools + ~30k tokens** en CADA llamada. Ruido + costo.
- Fix: exponer solo las tools del dominio de la tarea (auditoría ≠ control de PC ≠
  investigación). Ya existe `skills.py` como clasificador; se extiende.
- Es **aditivo** (una capa de selección antes de armar el prompt), no reescribe el
  loop. Verificable con un test de "para tarea de auditoría, se exponen las tools de
  auditoría".
- **Impacto: mejores decisiones del modelo + menos costo. Y beneficia directo al
  Auditor.**

### Paso 2 — Partir `agent.py` en un paquete `agent/` *(reorg, riesgo medio)*
- 1.401 líneas en un archivo. Se parte SIN cambiar lógica, solo mudando funciones:
  - `agent/loop.py` — el loop principal (`run_agent`, `_run_agent_turn*`).
  - `agent/context.py` — trim/budget/cap (`_trim_history*`, `_cap_tool_result`, …).
  - `agent/guards.py` — anti-loop, gate obsidian, blocked paths, audit-safe.
  - `agent/persistence.py` — persist/load conversaciones.
  - `agent/__init__.py` — reexporta la API pública (para no tocar quien la importa).
- **Regla:** mover, no reescribir. Después de cada archivo movido, correr tests.
- **Impacto: el hotspot deja de crecer; más fácil de mantener y de testear.**

### Paso 3 — Limpiar fronteras / imports perezosos *(riesgo medio)*
- Hay **7 imports perezosos** para esquivar ciclos (ej. `audit_report` ↔ `harness`).
- Revisar de a uno: si el ciclo se puede romper moviendo una función/const a un
  módulo común, se limpia; si no, se deja documentado (no forzar).
- **Impacto: fronteras de módulo más honestas.**

## Lo que NO se hace en esta pasada
- ❌ Tocar el lab (investigation, malware, ingestion, pentest, phone).
- ❌ Cambiar comportamiento del loop (solo mudarlo de archivo).
- ❌ Refactors "porque sí" sin un test que lo cubra.
- ❌ Nada a ciegas: si no se puede verificar, no se hace.

## Después de esto
Retomamos con **solo el Auditor** y lo perfeccionamos (el plan ya está en
`Raphael-Auditor-Producto/07-.../DETALLE/`: citar fuentes QW-3, botón generar PDF,
tests como gate, etc.). El Paso 1 y 2 de acá dejan el terreno limpio para eso.
