# PARA FABLE 5.2 — Raphael: arquitectura decidida y trabajo a implementar

> **Documento autocontenido.** Se lee solo: no depende de ningún otro documento del repo. **Todo lo que figura acá está YA DECIDIDO por Damian** (el dueño del proyecto).
> No hay preguntas abiertas ni cosas "a confirmar": no pidas confirmación sobre las decisiones de la sección 1; implementá y optimizá lo que pide la sección 5.
>
> Fecha: 2026-11-16. Rutas relativas a la raíz del repo `C:\Users\dam\Documents\JarvisRemote` (Windows 11).
> Convención de Damian: en sus documentos, **`R)`** y **`DAMIAN:`** marcan una **opinión suya**; tomala como tal (gana sobre cualquier documento previo).

---

## 0. Encuadre: qué se te pide

**Raphael** es un asistente personal con agentes organizados en **brigadas**, escrito en Python (FastAPI) y orientado a trabajar **en la PC de Damian, con gates de seguridad implementados en código**.
Hoy el sistema funciona, pero su **modelo de interacción difiere del que Damian decidió**. Tu trabajo:

1. **Implementar el modelo de interacción decidido** (sección 1): *Ayudantes → Jefe → Orquestador → Usuario*; el **orquestador es la única voz hacia el usuario**; el **jefe** coordina, sintetiza con su especialización y **reporta al orquestador**; **cada rol tiene su propio LLM y es siempre intercambiable por configuración**.
2. **Optimizar** los puntos listados en la sección 5, **en el orden de prioridad dado**, midiendo con los criterios de cada uno.
3. **Sin debilitar ningún invariante** (sección 6): gates, aprobación del usuario, líneas rojas.

**Qué NO se te pide:** rediseñar la arquitectura, cuestionar las decisiones de la sección 1, ni agregar capacidades fuera del alcance. Si encontrás una contradicción entre este documento y el código, **el código dice cómo es hoy y este documento dice cómo debe ser**; la distancia es el trabajo.

**Cómo entregar:** commits atómicos por tema (en español, prefijos `feat:`/`fix:`/`refactor:`/`test:`/`docs:`), tests en verde, validaciones que no empeoren (sección 7), y la documentación actualizada. No commitees secretos.

---

## 1. La arquitectura objetivo DECIDIDA

### 1.1 Flujo

```
                         Damian (texto / voz)
                                ▲   │
        mensaje final, personal   │   │  pedido
        y cercano ("en sus formas")   ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ L1  ORQUESTADOR  (LLM propio)                                 │  clasifica/rutea y es la VOZ con el usuario
  └──────────────▲───────────────────────────────┬───────────────┘
   REPORTE INTERNO│ (estructurado)                │ pedido + brigada
  ┌──────────────┴───────────────────────────────▼───────────────┐
  │ L2  JEFE DE BRIGADA  (LLM propio, permanente, con memoria)    │  coordina, delega y SINTETIZA con su especialización
  └──────────────▲──────────────────┬────────────▲────────────────┘
   resultado     │                  │ sub-tarea  │ resultado
  ┌──────────────┴───────┐   ┌──────▼────────────┴──┐
  │ L3  AYUDANTE EFÍMERO │   │ L3  AYUDANTE EFÍMERO │   hacen el trabajo real; nacen y mueren; reportan al jefe
  │     (LLM propio)     │   │     (LLM propio)     │
  └──────────────┬───────┘   └──────────┬───────────┘
                 │ llamadas             │
  ┌──────────────▼──────────────────────▼───────────────────────┐
  │ L4  SKILLS / TOOLS   (~131 tools, cada una con su gate)       │
  └───────────────────────────────────────────────────────────────┘
```

**El trabajo baja (Orquestador → Jefe → Ayudantes) y el resultado sube capa por capa: Ayudantes → Jefe → Orquestador → Usuario.** Nadie salta una capa.

### 1.2 Las cinco decisiones de Damian (diseño final)

1. **Flujo:** Ayudantes → Jefe → Orquestador → Usuario.
2. **Orquestador (L1):** además de clasificar y rutear, es la **VOZ con el usuario**. Toma el reporte interno del jefe y le comunica a Damian el resultado **de forma personal y cercana, "en sus formas"**
   (español rioplatense con voseo, directo, sin relleno). **El mensaje final al usuario lo produce el orquestador, no el jefe.**
3. **Jefe (L2):** **coordina** a sus ayudantes efímeros, **sintetiza** sus resultados con **su especialización de dominio** y le **reporta al orquestador** con un **reporte interno estructurado**; **no le habla al usuario**.
   **Tiene su PROPIO LLM.** **Nunca responde directo**, y no tiene tools de dominio (solo delega y lee su memoria).
4. **Ayudantes efímeros (L3):** hacen el trabajo real (con la caja de tools más chica posible, su propio LLM y timeout) y **reportan al jefe**. Nacen por tarea y mueren.
5. **Modelo SIEMPRE intercambiable:** el modelo de **cada rol** (orquestador, jefe, ayudante) es **swappable por configuración**, sin tocar código. El default es **nemotron** (`nvidia/nemotron-3.5-super-vl-120b-a12b` por NVIDIA NIM), pero ningún rol queda atado a un modelo o proveedor.

### 1.3 Consecuencias (todas decididas)

- Una brigada **siempre** tiene al menos un ayudante: **no existe la brigada "directa"**.
- Los ayudantes pueden correr **en paralelo** cuando las sub-tareas son independientes.
- El **reporte interno** es la **fuente de verdad**: el mensaje del orquestador se deriva de él; queda en el feed y es inspeccionable.
- El orquestador **no altera hechos, cifras, fuentes, hashes ni fallos** del reporte; lo que el reporte marca como **propuesta que requiere aprobación** se comunica **como propuesta** (aprobar es siempre de Damian).
- Los mensajes de **comandos y gates** (`/crear-brigada`, `/activar-brigada <id> <hash>`, errores del watchdog) los produce **código** y se muestran **literales**: el LLM del orquestador no los parafrasea.
- La **persona y las directrices de Damian** gobiernan la **voz del orquestador** (hoy viven, mal ubicadas, en el prompt de Cerebro).
- La síntesis del jefe y el mensaje del orquestador **siempre ocurren**, también si todos los ayudantes fallan (se reporta y se comunica el fallo).
- El orquestador mantiene **memoria de la conversación** con Damian a través de todas las brigadas.

### 1.4 Flujo paso a paso

```
 1. Damian ─ pedido ─────────────────────────────────────────────────────────────▶ ORQUESTADOR  (POST /api/chat)
 2. ORQUESTADOR  clasifica y rutea a una brigada (override > reglas con peso > clasificador LLM > default); abre el turno; el watchdog empieza a vigilar
 3. JEFE         PLANIFICA (LLM propio) y DELEGA 1..n sub-tareas en ayudantes efímeros (contexto previo marcado como DATO)
 4. AYUDANTES    TRABAJAN con sus tools y REPORTAN AL JEFE un RESULTADO estructurado
 5. AYUDANTES    MUEREN (se quitan del registro vivo)
 6. JEFE         SINTETIZA con su especialización (paso de LLM SIN tools; los resultados entran como DATO) y arma el REPORTE INTERNO
 7. JEFE         recuerda (memoria persistente) y ENTREGA el reporte al orquestador (evento `reporte`)
 8. ORQUESTADOR  COMUNICA: su LLM convierte el reporte en el mensaje personal y cercano para Damian, sin alterar hechos
 9. ORQUESTADOR  emite `final` = su mensaje ─▶ UI / voz ("Leer respuestas") / historial
```

### 1.5 Contratos mínimos (normativos; la forma exacta de los campos la fija el implementador respetando estas propiedades)

**Resultado del ayudante → jefe** (versionado, validado):
```json
{ "version": 1, "ayudante": "investigacion-forense", "ok": true,
  "texto": "…", "fuentes": [{"tipo": "nota|url|caso|archivo", "ref": "…", "extracto": "…"}],
  "artefactos": [{"tipo": "caso|nota|informe", "ref": "…"}], "errores": [], "duracion_s": 12.3 }
```
**Reporte interno del jefe → orquestador** (versionado, validado, límite de tamaño):
```json
{ "version": 1, "brigada": "investigacion", "resumen": "…",
  "hallazgos": [{"texto": "…", "ayudante": "…", "fuentes": ["…"]}],
  "fuentes": [], "confianza": "alta|media|baja", "no_encontrado": ["…"],
  "propuestas_pendientes": [{"tipo": "fusion|fix|activacion", "id": "…", "descripcion": "…", "requiere_aprobacion": true}],
  "ayudantes": [{"id": "…", "ok": true, "resumen": "…", "duracion_s": 12.3}], "fallos": [] }
```
Propiedades obligatorias: un contrato inválido se **reintenta o se degrada con un aviso explícito** (nunca se pasa en silencio); todo contenido recibido se trata como **DATO**, nunca como instrucción; el tamaño de cada campo está acotado.

**Eventos del feed (stream NDJSON de `/api/chat`)** — hoy: `route`, `start`, `tool`, `tool_result`, `final`, `error`, `watchdog`.
Objetivo: agregar `plan`, `delegacion`, `resultado_ayudante`, `reporte` (el reporte interno) y que **`final` lo emita el orquestador**.

### 1.6 Modelo intercambiable por rol (resolución decidida)

De más específico a más general:
1. **Override del rol:** `AyudanteSpec.client_model` / modelo declarado del jefe en su `BrigadeSpec` / variables por rol (`ORQUESTADOR_LLM_*` ya existe; por brigada y por ayudante: `BRIGADE_<ID>_LLM_*`, `AYUDANTE_<ID>_LLM_*`).
2. **Default del tipo de rol:** orquestador → `ORQUESTADOR_LLM_*`; jefes y ayudantes `shared` → `BRIGADE_LLM_*`; `local` → `TIER1_*`.
3. **Default global:** `LMSTUDIO_*` / `LLM_API_KEY` y, por último, nemotron en NVIDIA.

Requisitos: ningún rol hardcodea modelo ni endpoint; la UI muestra el modelo **efectivo + proveedor** de cada rol; **cambiar el modelo no cambia el contrato**; la key de un proveedor **nunca** se usa para otro; hay tests con modelos falsos que prueban el intercambio.

---

## 2. Qué es el sistema hoy (verificado contra el código, 2026-11-16)

### 2.1 Stack y entorno
- Python 3.12, FastAPI. Backend en `backend/`; venv en `backend/.venv` (Windows: `backend\.venv\Scripts\python.exe`). Tests con pytest **desde la carpeta `backend/`**.
- Dos procesos: **orquestador liviano** (`backend/run_orquestador.py`, puerto **8010**, solo `127.0.0.1`, token efímero por arranque, anti DNS-rebinding) y **monolito** (`backend/run.py`, :8000, el "Raphael completo" con ~125 tools). Este trabajo es sobre el **orquestador y las brigadas**.
- El orquestador es **liviano a propósito**: `orquestador/slim_tools.py` carga el registro de tools salteando pentest/malware/desktop/phone; **importar un spec o una escena no debe cargar `app.tools`** (la validación importa solo dataclasses; lo pesado va perezoso). Hay tests que lo garantizan.
- Modelos hoy (`backend/.env`): **todo en nemotron/NVIDIA** (`https://integrate.api.nvidia.com/v1`, `nvidia/nemotron-3.5-super-vl-120b-a12b`) salvo **Scout** (ayudante de Investigación) que usa **Groq** (`openai/gpt-oss-120b`, `SCOUT_LLM_*`) y los **embeddings** (LM Studio :1234, `text-embedding-nomic-embed-text-v1.5`, local). Voz: faster-whisper `small` (CPU) + Piper es_AR, local.

### 2.2 Cómo funciona un turno HOY

1. `POST /api/chat {message, brigade?}` (`backend/orquestador/server.py`): si el mensaje **empieza** con un comando de gestión (`/crear-brigada`, `/activar-brigada`…) lo ejecuta **código** (`orquestador/brigadas.py`). Si no, `route()` (`orquestador/routing.py`) elige la brigada: override (`/cerebro`, `/investigacion`, `/<id-creada>`) → reglas con peso (`_RULES`, regex sin acentos) → clasificador LLM (`llm_classify`, usa `load_orquestador_client_model()`, timeout 45 s) → default **Cerebro**. Las brigadas **creadas** nunca entran al auto-ruteo.
2. Emite `route`, toma un `asyncio.Lock` **por brigada** y corre `watchdog.supervise(chief, message, on_event, brigade, spec)`; el feed sale como NDJSON.
3. El **jefe** (`brigades/engine.py::GenericChief.run`):
   - **Sin ayudantes (Cerebro):** corre `BrigadeChief.run` (`brigades/chief.py`): mini-loop LLM→tool→LLM (máx. 12 iteraciones) con sus propias tools (`obsidian_buscar_asociativo`, `obsidian_search_notes`); **su respuesta es la respuesta al usuario**.
   - **Con ayudantes (Investigación, Seguridad, creadas que delegan):** `spec.routing.clasificar(message)` (regex en orden; gana la primera; si ninguna, el `default`) elige **un** ayudante; `_spawn(modo)` crea un `BrigadeChief` efímero; corre bajo `asyncio.wait_for(timeout)` (default 900 s); emite `tool delegar:<id>`; **devuelve el `reply` crudo del ayudante** (que es el `final`); anota `[ayudante] reply` en la memoria del jefe. El jefe **no llama a ningún LLM**.
4. El **registro vivo** (`brigades/live.py`) anota cada efímero mientras corre; el **watchdog** (`orquestador/watchdog.py`) corta runs colgados (loops, falta de progreso, timeout, errores) y avisa en el feed.
5. La UI (`orquestador/ui.html`) pinta el feed; con "Leer respuestas" activo, lee el `final` por voz local.

### 2.3 Las piezas (qué existe y dónde)

| Pieza | Archivo | Estado hoy |
|---|---|---|
| Servidor y endpoints (`/api/chat`, `/api/meta`, `/api/cocineros`, `/api/efimeros`, `/api/watchdog`, `/api/voz*`, `/api/brigadas*`, vistas de Cerebro/Investigación) | `backend/orquestador/server.py` | ✅ |
| Ruteo a brigada | `backend/orquestador/routing.py` | ✅ (el LLM solo clasifica) |
| Comandos de gestión de brigadas (por código) | `backend/orquestador/brigadas.py` | ✅ |
| Watchdog | `backend/orquestador/watchdog.py` | ✅ |
| Cocineros por brigada (desde el spec) | `backend/orquestador/agentes.py` | ✅ |
| UI | `backend/orquestador/ui.html` | ✅ |
| Jefe persistente (mini-loop, memoria en `backend/data/brigades/<id>.json`, últimos 16 mensajes, tope 6000 chars por resultado de tool) | `backend/brigades/chief.py` | ✅ |
| Motor genérico que ejecuta un `BrigadeSpec` | `backend/brigades/engine.py` | ✅ (con la divergencia de §3) |
| Spec declarativo (`BrigadeSpec`, `AyudanteSpec`, `Routing`, `RouteRule`, `SkillSpec`, `WatchSpec`, `ValidationSpec`) | `backend/brigades/spec.py` | ✅ |
| Registro de brigadas (declarativas + legacy Scout + creadas activas, re-verificadas en cada uso) | `backend/brigades/registry.py` | ✅ |
| Resolución de modelos (`load_chief_client_model`, `load_local_client_model`, `load_orquestador_client_model`, `describe_endpoint`, `effective_label`) | `backend/brigades/config.py` | ✅ (parcial: falta override por rol) |
| Brigadas: Cerebro / Investigación / Seguridad | `backend/brigades/cerebro.py`, `investigacion.py`, `seguridad.py` (+ `*_scene.py`) | ✅ |
| Crear brigadas: fábrica, gate firmado, política de tools, diseñador | `backend/brigades/factory.py`, `draft_store.py`, `tool_catalog.py`, `designer.py`, `ejemplos.py` | ✅ |
| Registro vivo de efímeros | `backend/brigades/live.py` | ✅ |
| Servicio de memoria write-only hacia Cerebro | `backend/brigades/memory_service.py` | ✅ |
| Directrices de Damian (carta editable) | `backend/brigades/directrices.py` | ✅ |
| Cerebro: spreading, hebbiano, consolidación, olvido, sucesora, analogía, composición, confianza, atención, feedback, curiosidad, metas | `backend/app/obsidian/*.py` | ✅ |
| Validación: framework, harness, pasos por brigada, genéricos, baselines | `backend/validation/*.py`, `backend/validation/baselines/` | ✅ |
| Voz local (STT/TTS) | `backend/voice/engine.py`, `worker.py` | ✅ |
| Tools (registro con `@register_tool`) | `backend/app/tools/` | ✅ |
| Persona del asistente | `backend/app/agent.py` (`RAPHAEL_PERSONA`) | ✅ |
| **Comunicador / voz del orquestador** | (nuevo) `backend/orquestador/voz.py` | ❌ a construir |
| **Contratos (resultado y reporte)** | (nuevo) módulo en `backend/brigades/` | ❌ a construir |

---

## 3. La distancia: qué hay que cambiar (divergencias DIV)

| ID | Hoy → Objetivo | Dónde |
|---|---|---|
| **DIV-01** | Cerebro responde directo → debe **delegar** (ayudante *recuperador*), **sintetizar** con su especialización de memoria y **reportar al orquestador**; pierde sus tools de búsqueda | `brigades/cerebro.py`; rama `not spec.delegating` de `GenericChief.run` |
| **DIV-02** | Los jefes con ayudantes devuelven el texto **crudo** del ayudante como respuesta final → sintetizar con su LLM y **reportar** | `brigades/engine.py`; `INVESTIGACION_PROMPT`, `SEGURIDAD_PROMPT` ("devolvés su resultado") |
| **DIV-03** | 1 ayudante por pedido, ruteo regex → el jefe **planifica** 1..n delegaciones, en paralelo si son independientes (reglas como red de seguridad) | `brigades/spec.py` (`Routing`), `engine.py` |
| **DIV-04** | El esquema de borradores admite brigadas "directas" → exigir ≥1 ayudante | `brigades/factory.py` (`validate_draft`, `compile_spec`), `ejemplos.py` (`EJEMPLO_DIRECTA`), `designer.py` |
| **DIV-05** | El feed no distingue plan/delegación/resultado/reporte/comunicación → eventos nuevos | `engine.py`, `server.py`, `ui.html` |
| **DIV-06** | Persona y directrices viven en el prompt de **Cerebro** → deben gobernar la **voz del orquestador** | `brigades/cerebro.py` (`build_cerebro_system_prompt`), `directrices.py` |
| **DIV-07** | **El orquestador no es la voz**: su LLM solo clasifica y el `final` lo emite el jefe/ayudante → el orquestador produce el mensaje final | `orquestador/server.py`, `routing.py` |
| **DIV-08** | El jefe que delega **no tiene LLM propio** y no hay config de modelo por rol (jefe, ayudante) → LLM propio e intercambiable por rol | `brigades/spec.py` (`client`), `config.py`, `engine.py` |
| **DIV-09** | No existen los **contratos** (resultado del ayudante, reporte del jefe) | — |

---

## 4. Terminología (de Damian)

- **Cocineros** = agentes **permanentes** de una brigada (el jefe, con memoria). **Efímeros** = ayudantes que se crean por tarea y mueren. **Brigada** = unidad de trabajo (jefe + ayudantes + reglas + validación).
- **Spec** = el dato que declara una brigada. **Validación** = su escena y criterio de éxito; **baseline** = primera corrida verde contra la que se detectan regresiones. **Gate** = barrera implementada en código.
- **Brigadas creadas**: las genera el orquestador desde una descripción; nacen como **borrador no operativo** y solo se activan con la **aprobación firmada** (Ed25519 + DPAPI) de Damian sobre el hash exacto; se usan por `/<id>` o su pestaña, **nunca por auto-ruteo**.
- Vocabulario prohibido: no uses "router", "worker" ni "PRD ticket" en código, docs ni UI.

---

## 5. TRABAJO PRIORIZADO (implementá/optimizá en este orden)

Cada punto: **contexto · qué hacer · archivos · criterios de aceptación · cómo medir**. Los puntos P0–P5 construyen el flujo decidido; P6 son optimizaciones que se hacen **después** de que el flujo funcione y valide.

### P0 — Cimientos (hacer primero; todo lo demás los usa)

**P0.1 Contratos (DIV-09)**
- *Contexto.* El flujo necesita dos contratos estables: resultado del ayudante y reporte del jefe (§1.5). Permiten cambiar el modelo de cualquier rol sin romper nada.
- *Qué hacer.* Un módulo de contratos (dataclasses o pydantic) con versión, validación estricta, límites de tamaño, (de)serialización y una **degradación explícita** si un LLM produce algo inválido (reintento acotado y, si no, aviso en el reporte).
- *Archivos.* (nuevo) `backend/brigades/contracts.py`; consumido por `engine.py`, `chief.py`, `orquestador/server.py`.
- *Aceptación.* Contratos validan casos válidos e inválidos; un campo fuera de límite se recorta o se rechaza de forma determinista; los textos se tratan como DATO.
- *Medir.* Tests de contrato con modelos falsos; 100 % de reportes inválidos detectados; ningún campo perdido entre capas.

**P0.2 Modelo intercambiable por rol (DIV-08)**
- *Contexto.* Principio decidido: el modelo de cada rol es swappable por config (§1.6).
- *Qué hacer.* Una función única `resolve_role_model(kind, brigade_id, helper_id)` con la cadena override→tipo→global; override por brigada y por ayudante; LLM del jefe; `/api/meta` y el panel Cocineros muestran el modelo efectivo de **cada** rol (jefe incluido); `.env.example` documentado.
- *Archivos.* `backend/brigades/config.py`, `spec.py`, `engine.py`, `orquestador/agentes.py`, `server.py`, `backend/.env.example`.
- *Aceptación.* Cambiar el modelo de un rol por config lo cambia sin tocar código; ningún modelo/endpoint hardcodeado (grep); la key de un proveedor nunca se usa para otro; el contrato no cambia al cambiar de modelo.
- *Medir.* Tests que intercambian el modelo de un rol por uno falso y comprueban flujo y contratos idénticos.

### P1 — El flujo en el motor (jefe: planificar, delegar, sintetizar, reportar)

**P1.1 Ayudante devuelve resultado estructurado (DIV-09/02)**
- *Qué hacer.* Envolver la corrida de cada ayudante en el contrato de resultado: `texto` (su respuesta final), `fuentes`/`artefactos` extraídos de los eventos de sus tools (notas, URLs, casos), `errores` (tool_result con ok=false), `duracion_s`, `ok`. No cambiar sus tools ni sus gates.
- *Archivos.* `backend/brigades/engine.py`, `chief.py`, `contracts.py`.
- *Aceptación.* Todo ayudante, incluso uno que falla o se corta por timeout/watchdog, produce un resultado válido (`ok=false` + error) en vez de una excepción o texto suelto.

**P1.2 Jefe con LLM propio: síntesis y reporte (DIV-02, DIV-08)**
- *Qué hacer.* Tras los resultados, un **paso de LLM sin tools** del jefe (modelo del jefe, §1.6) que sintetiza con su especialización (prompts de síntesis por brigada) y produce el **reporte interno** validado. Si el LLM del jefe falla, **degradar** a un reporte armado con los resultados crudos marcado `sintesis_degradada` (nunca perder el trabajo ni inventar). Persistir en la memoria del jefe (pedido, quién lo resolvió, conclusión).
- *Archivos.* `engine.py`, `brigades/investigacion.py` y `seguridad.py` (prompts de jefe: "devolvés su resultado" → sintetizar y reportar), `chief.py`.
- *Aceptación.* El jefe **nunca** devuelve texto crudo de un ayudante como respuesta; el reporte cita las fuentes de los resultados y reporta `fallos` y `no_encontrado`; sin LLM disponible hay degradación explícita.
- *Medir.* Escena de validación: el reporte contiene todas las fuentes y cifras de los resultados de entrada y ninguna inventada (chequeo determinista); tasa de degradación.

**P1.3 Planificación y paralelismo (DIV-03)**
- *Qué hacer.* El jefe elige 1..n ayudantes y redacta la sub-tarea de cada uno: **primero** reglas (el `Routing` actual como red de seguridad y default seguro/más pasivo), **luego** planificación con LLM para casos ambiguos; delegaciones independientes en paralelo (`asyncio.gather`) con timeouts por ayudante y fallo contenido.
- *Archivos.* `brigades/spec.py` (`Routing`), `engine.py`, `investigacion.py`, `seguridad.py`.
- *Aceptación.* Un pedido que pide web **y** evidencia delega en Scout y Forense; el default sigue siendo el más pasivo; un ayudante colgado no bloquea a los demás.
- *Medir.* Aciertos de delegación en las escenas; delegaciones innecesarias; falsos "scout"/"escaneo" (los caros/peligrosos) = 0.

### P2 — El orquestador como VOZ (DIV-07, DIV-06)

**P2.1 Comunicador del orquestador**
- *Qué hacer.* Módulo `orquestador/voz.py` con el LLM del orquestador (intercambiable): convierte el **reporte interno** en el mensaje final personal y cercano **en las formas de Damian** (rioplatense, voseo, directo, sin relleno; persona en `RAPHAEL_PERSONA`, directrices en `brigades/directrices.py`). Escrito para ser **leído en voz alta** (corto, sin markdown). Presenta `propuestas_pendientes` como propuestas. **Pasa literales** los textos de comandos/gates/watchdog.
- *Fidelidad (obligatoria y verificable).* Un verificador determinista comprueba que todas las cifras, ids, fuentes y fallos del reporte aparezcan en el mensaje y que no aparezcan cifras/fuentes que no estén en el reporte; si falla, **reintento acotado y, si no, mensaje de respaldo por plantilla** construido desde el reporte.
- *Archivos.* (nuevo) `backend/orquestador/voz.py`; `orquestador/server.py` (`/api/chat`: el `final` lo emite el orquestador); `backend/app/agent.py` (`RAPHAEL_PERSONA`), `brigades/directrices.py`.
- *Aceptación.* Ningún texto de jefe/ayudante llega al usuario sin pasar por el orquestador; el `final` siempre es del orquestador; los comandos de gestión y los gates salen literales; el hash de activación nunca se altera.
- *Medir.* Fidelidad (verificador) = 100 % en la escena; juicio de Damian sobre naturalidad; latencia añadida por la comunicación.

**P2.2 Memoria de la conversación del orquestador**
- *Qué hacer.* Memoria acotada de la conversación (continuidad entre turnos y brigadas, sin mezclar datos entre brigadas), con límites de tamaño y resumen.
- *Archivos.* `orquestador/server.py`, `orquestador/voz.py`. *Medir.* Calidad en conversaciones de varios turnos; tokens de contexto.

### P3 — Las brigadas al nuevo modelo

**P3.1 Cerebro delega (DIV-01, DIV-06)**
- *Qué hacer.* Ayudante efímero **recuperador** (búsqueda asociativa + keyword) que devuelve evidencia **estructurada** (id de nota, título, extracto textual, score); el jefe de Cerebro pierde las tools de búsqueda, sintetiza con su especialización de memoria (fidelidad a los datos, "no encontrado", sin mezclar temas) y reporta. La persona y las directrices pasan a la voz del orquestador (P2.1).
- *Archivos.* `backend/brigades/cerebro.py`, `cerebro_scene.py`, `backend/validation/cerebro.py`, `backend/app/obsidian/spreading.py` y tools de obsidian.
- *Aceptación.* **La validación de Cerebro sigue verde (4 pasos)**: cita las notas correctas sin inventar, aplica una directriz de forma observable, la consolidación no agrupa el distractor, la aislación del vault real se mantiene. Los pasos se adaptan al flujo nuevo **sin aflojar criterios**.

**P3.2 Investigación y Seguridad** — prompts de jefe de síntesis; reporte; gates intactos (`authorized_targets.yaml`, el ayudante Forense solo propone). *Archivos.* `investigacion.py`, `seguridad.py`, sus escenas y `validation/`.

**P3.3 Brigadas creadas (DIV-04)** — exigir ≥1 ayudante y el modelo por rol en el borrador; el diseñador, los ejemplos, la validación genérica y los tests se ajustan; el **gate firmado no cambia**. *Archivos.* `factory.py`, `designer.py`, `ejemplos.py`, `validation/generic.py`.

### P4 — Observabilidad (DIV-05)
- *Qué hacer.* Eventos `plan`, `delegacion`, `resultado_ayudante`, `reporte`, `final` (del orquestador); la UI muestra el reporte interno (inspectable, escapado), qué ayudante aportó qué y el modelo efectivo de **cada** rol; el panel Cocineros muestra el LLM del jefe (hoy dice "sin LLM propio"); la voz lee el mensaje del orquestador.
- *Archivos.* `engine.py`, `server.py`, `ui.html`, `live.py`, `agentes.py`. *Medir.* Tiempo para entender por qué una respuesta salió como salió; tests de UI estáticos (todo escapado).

### P5 — Validación del flujo completo
- *Qué hacer.* Escenas que validan orquestador→jefe→ayudantes→reporte→mensaje: fidelidad, fallos comunicados, propuestas como propuestas, comandos literales, intercambio de modelo por rol, degradaciones. Repetir corridas para medir variabilidad; baselines nuevos solo desde corridas verdes.
- *Archivos.* `backend/validation/`, `backend/brigades/*_scene.py`. *Medir.* Tasa de verde sobre N corridas; regresiones inyectadas detectadas.

### P6 — Optimizaciones (después de que P0–P5 estén verdes)

| ID | Punto | Contexto y enfoque actual | Qué significa optimizarlo | Archivos | Medir |
|---|---|---|---|---|---|
| **O-1** | Clasificación de ruteo del orquestador | Override → reglas con peso → LLM (nemotron razona; 1024 tokens, 45 s) → default Cerebro | Banco de pedidos etiquetados, más resuelto por reglas, menor latencia, pedidos que tocan dos brigadas, ante la duda la opción de menor daño | `orquestador/routing.py` | Exactitud; % por reglas; latencia p50/p95 |
| **O-2** | Umbral de consolidación de Cerebro | `select_pairs`: coseno ≥ 0.85 **y** brecha ≤ 0.08 bajo la mejor similitud de cualquiera de las dos notas; calibrado con 1 escena y nomic-embed-text-v1.5 | Calibrar con varias escenas/vault real, robustecer ante otros modelos de embeddings, umbral adaptativo | `app/obsidian/consolidation.py`, `app/config.py` | Precisión/recall de grupos; paso 4 de la validación verde |
| **O-3** | Recuperación de Cerebro | Spreading + keyword | Evidencia estructurada, afinar spreading/hebbiano para que el distractor no suba | `app/obsidian/spreading.py`, `vault.py`, `embeddings.py` | Recall@k; ausencia del distractor |
| **O-4** | Ciclo de vida/latencia de efímeros | Spawn por pedido (config + cliente), un turno a la vez por brigada | Reusar clientes, delegación paralela, timeouts adaptativos, decidir el lock | `engine.py`, `chief.py`, `live.py`, `server.py` | Latencia p50/p95; arranque del efímero; throughput con 2–3 pedidos |
| **O-5** | Prompts por rol | A mano, con secciones no negociables (SEGURIDAD, FIDELIDAD A LOS DATOS, CONFIRMÁ LO QUE HICISTE) | Matriz rol×objetivo (orquestador/jefe/ayudante), prompts más cortos y verificables, ablaciones medidas | `brigades/*.py`, `app/skills.py`, `scout/identity.py` | Validaciones; tokens por turno |
| **O-6** | Watchdog | Umbrales sin calibrar; solo ve eventos del feed | Latidos del motor, loops semánticos, límites por rol desde el spec, vigilar síntesis y paralelismo | `orquestador/watchdog.py`, `spec.py` | Falsos positivos/negativos |
| **O-7** | Latencia/costo/robustez por rol | Un modelo para casi todo; riesgo de 429 y cortes de red | Modelo por rol (clasificador barato, jefes de calidad), presupuestos de tokens, fallback entre proveedores | `config.py`, `app/harness/model_registry.py` | Latencia/tokens/errores/costo por rol |
| **O-8** | Memoria del jefe | Últimos 16 mensajes; el ayudante recibe 4×300 caracteres como DATO | Memoria útil para sintetizar, resúmenes en vez de truncado | `chief.py`, `engine.py` | Multi-turno; tokens |
| **O-9** | Diseñador de brigadas | 3 intentos con feedback; sin edición de borradores | Plantillas de ayudantes y síntesis, calidad de reglas, edición/versionado de borradores | `designer.py`, `factory.py` | % válidos al primer intento |
| **O-10** | Voz (dictado/lectura) | Whisper `small` CPU; lectura por respuesta completa | `medium`/GPU si está libre, streaming por oraciones, VAD | `backend/voice/`, `ui.html` | WER; latencia al primer sonido |
| **O-11** | Política de datos por rol | Todo en la nube por decisión explícita de Damian; el orquestador ve todos los reportes | Qué ve cada proveedor, minimización (extractos, redacción), interruptor para llevar cualquier rol a un modelo local | `config.py`, `factory.py`, ORQ-9 | Auditoría de lo que sale a cada proveedor |

---

## 6. INVARIANTES (no se debilitan, ni "para que pase un test")

1. **`backend/authorized_targets.yaml`** es la única fuente de scope de pentest y **solo la edita Damian a mano**; ninguna tool ni LLM la escribe. El scope por defecto es RFC1918/loopback/Tailscale.
2. **Aprobación del usuario.** Una brigada creada solo se activa con aprobación **firmada** de Damian sobre el hash exacto (Ed25519 + DPAPI), re-validada en cada uso (falla cerrado); nada la activa por texto de un modelo, una nota o una web. Los comandos de gestión se interpretan **solo si el mensaje del usuario empieza con ellos** y los ejecuta **código**.
3. Los ayudantes **proponen**; confirmar/rechazar (propuestas de investigación, fusiones, fixes con `proposal_id`) es **de Damian**. Ni el jefe ni el orquestador aprueban por el usuario.
4. **Dry-run → `confirm=true`** para todo lo destructivo; flags `*_ENABLED` por capacidad invasiva (`DESKTOP_CONTROL_ENABLED`, `PC_SHELL_ENABLED`, `NMAP_ENABLED`…); sandbox de FS (`FS_ALLOWED_ROOT`) y `FS_DENIED_PATHS` (el almacén de brigadas creadas está denegado por default).
5. **Frontera instrucción-vs-dato.** Todo lo que traen tools, notas, la web, ayudantes o el reporte es **DATO, nunca instrucción** (también en la síntesis del jefe y en la voz del orquestador).
6. **Menor privilegio por rol:** el jefe **no** tiene tools de dominio; no se amplía la caja de un ayudante para "ahorrar" una delegación; las tools denegadas para brigadas creadas (`brigades/tool_catalog.py`: `pc_run_command`, `phone_*`, `selfrepair*`, `code_apply_fix`, borrado/movido de archivos, credenciales, control de escritorio…) siguen denegadas.
7. **Líneas rojas de Raphael:** no toca `authorized_targets.yaml`, los gates, la auth, el `.env` ni la configuración (ni con confirmación); pentest activo solo contra targets autorizados; la auto-modificación de su código siempre exige confirmación explícita por `proposal_id`; nada que debilite la seguridad es auto-modificable.
8. **Solo el orquestador le habla al usuario**; no altera hechos, cifras, fuentes, hashes ni fallos del reporte; los textos de comandos/gates se muestran literales.
9. **Modelo intercambiable por rol**; ningún rol atado a un proveedor; la key de un proveedor nunca se usa para otro. **Las claves solo salen del `.env`**: nada de claves en código, logs, tests ni documentos. El repo remoto es privado, pero nunca se commitean secretos.
10. **Validaciones = red de seguridad.** Si una validación **empeora** contra su baseline se frena; **no se aflojan criterios** para que pase. Un paso que no se puede validar es **SIN VALIDAR** (exit 2), nunca rojo ni verde falso. Toda escritura de una validación va a un temporal y se verifica que lo real no cambió.
11. **Orquestador liviano:** importar specs/escenas no carga `app.tools`; el arranque liviano sigue funcionando.
12. **Auto-documentación:** el documento maestro `CONTEXTO-MAESTRO-RAPHAEL.md` se regenera con un hook de pre-commit; no lo rompas ni lo desactives. Los bloques `AUTO` no se editan a mano.

---

## 7. Cómo trabajar y verificar

- **Entorno:** Windows 11. Desde `backend/`: `.venv\Scripts\python.exe -m pytest tests/<archivo>` (usá `timeout` explícito en corridas largas). No corras modelos pesados en la GPU sin avisar a Damian (puede estar en uso); las validaciones reales usan nemotron (NVIDIA) y embeddings en LM Studio (:1234).
- **Tests relevantes** (todos deben seguir en verde; ~300 en este conjunto): `tests/test_orquestador*.py`, `test_brigade_*.py` (spec, factory, designer, investigacion, seguridad), `test_draft_store.py`, `test_tool_catalog.py`, `test_watchdog.py`, `test_agentes_vivo.py`, `test_validation_*.py`, `test_cerebro_fixes.py`, `test_consolidation.py`, `test_voice.py`, `test_fs_denied_brigadas.py`.
- **Validaciones reales** (desde `backend/`): `.venv\Scripts\python.exe -m validation.todas cerebro investigacion` (un resultado por brigada: PASA / NO PASA / INCOMPLETO; exit 0/1/2). Estado hoy: **Cerebro PASA 4/4 con baseline**; Investigación **INCOMPLETA** (Forense PASA; Scout SIN VALIDAR por falta de `BRAVE_SEARCH_API_KEY`); Seguridad con validación lista y sin corrida real (necesita una VM de laboratorio).
- **Reiniciar el orquestador para ver cambios:** `.venv\Scripts\pythonw.exe run_orquestador.py` (el lanzador detecta si el proceso en :8010 es más viejo que el código/`.env` y lo reinicia solo). Para pruebas, levantá una instancia aparte con `--port` distinto y `--no-browser`.
- **Commits:** atómicos por tema, en español con prefijo (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`) y el porqué en el mensaje. Hay un hook de pre-commit que regenera y stagea los bloques automáticos del documento maestro (puede mostrar "[contexto] …"; es normal).
- **Documentación a actualizar al terminar cada punto:** `docs/ARQUITECTURA-RAPHAEL.md` (estado actual vs objetivo) si existe en el repo, y una nota de la decisión/avance en `docs/contexto/decisiones.md`.
- **No hagas:** hacer que un jefe responda directo o le hable al usuario · saltarte el reporte · dejar que el orquestador cambie hechos · hardcodear modelos · activar brigadas o tocar `authorized_targets.yaml`/`.env` · aflojar un criterio de validación · mezclar el vault personal con vaults de prueba · commitear secretos.

### Definición de "terminado" (por punto)
Código + tests nuevos en verde + suite relevante sin regresiones + validaciones que no empeoran + documentación actualizada + commits atómicos.

---

## 8. Referencia rápida

**Variables de entorno de modelo** (`backend/.env`; ver `.env.example`): `ORQUESTADOR_LLM_BASE_URL/MODEL/API_KEY` (orquestador; la key **solo** de acá), `BRIGADE_LLM_BASE_URL/MODEL/API_KEY` (jefes y ayudantes `shared`), `TIER1_MODEL/BASE_URL/API_KEY` (`local`/tier 1), `LMSTUDIO_*` + `LLM_API_KEY` (chat global del monolito), `SCOUT_LLM_*` (Scout/Groq), `EMBEDDING_BASE_URL/MODEL`, `BRIGADA_MODELO_DEFAULT` (default de brigadas nuevas: `shared`), `BRIGADE_AYUDANTE_TIMEOUT_SECONDS` (900), `WATCHDOG_*`, `VOICE_*`, `CONSOLIDATION_SIMILARITY_THRESHOLD/GAP`.

**Almacenes de datos** (gitignoreados): `backend/data/brigades/<id>.json` (memoria del jefe), `backend/data/brigades_creadas/` (borradores y aprobaciones firmadas), `backend/data/watchdog/` (intervenciones), `backend/validation/results/` (resultados de validación), `backend/data/voices/` (voz Piper).

**Endpoints del orquestador** (token efímero; solo `127.0.0.1:8010`): `POST /api/chat`, `GET /api/meta` (modelo efectivo por brigada y del orquestador), `GET /api/cocineros`, `GET /api/efimeros`, `GET /api/watchdog`, `GET/POST /api/voz*`, `/api/brigadas*` (borradores, revisión, activación, desactivación), vistas de Cerebro e Investigación.

**Eventos del feed hoy:** `route` · `start` · `tool` (incluye `delegar:<ayudante>`) · `tool_result` · `final` · `error` · `watchdog`.

**Estructura de una brigada (`BrigadeSpec`)**: `id`, `name`, `purpose`, `prompt` (str o builder), `client` (`local`/`shared`), `tools` (techo), `vault_path`, `persistent`, `ayudantes` (cada `AyudanteSpec`: `modo`, `id`, `descripcion`, `donde`, `config`, `client_model`, `tool_names`), `routing` (`RouteRule(modo, patron)` en orden + `default`), `skills`, `helper_timeout`, `watch` (`WatchSpec`), `tool_modules`, `validation` (`ValidationSpec`: escena con hash, pasos, criterio, prerrequisitos).

**Brigadas hoy:** Cerebro (núcleo de memoria; vault Obsidian con búsqueda semántica y fases cognitivas), Investigación (Scout = research web trazable; Forense = evidencia digital de un caso, solo propone), Seguridad (defensiva: `escaneo` nmap/ZAP/sqlmap solo detección con gate de scope, `reporte` pasivo). Más las brigadas creadas.

**Glosario:** orquestador (L1, LLM propio, voz con el usuario) · jefe (L2, LLM propio, coordina/sintetiza/reporta) · ayudante efímero (L3, LLM propio, trabaja/reporta al jefe) · tool (L4) · reporte interno (jefe→orquestador, fuente de verdad) · resultado (ayudante→jefe) · gate · watchdog · registro vivo · borrador.
