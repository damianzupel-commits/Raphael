# SPEC — Mejoras a Raphael (síntesis del vault)

> **Qué es:** plan detallado y por fases para mejorar a Raphael, nacido de minar el
> vault técnico de Raphael (`backend/obsidian_vault/jarvis/`, ~320 notas) + las
> decisiones de Damian (2026-10-19). Es un **plan de ejecución**, no toca código todavía.
> Se ejecuta con Claude (Opus/Sonnet) cuando haya cuota; cada ítem queda autocontenido
> para poder tomarlo suelto.
>
> **Relacionado:** `docs/SPEC-AUDITORIA-2026-10-13.md` (bugs/deuda) · `CLAUDE.md` (arquitectura)
> · `docs/EXPERIMENTO-JEV-motor-de-decisiones.md` (base del motor de decisiones).

---

## Principios transversales (decididos con Damian)

1. **Free/local donde se pueda, frontera donde haga falta.** El objetivo es costo
   **y** calidad: lo rutinario/simple corre local (Ollama) o free; lo duro/crítico
   escala a modelos frontera (Sonnet/Opus). Nunca se sacrifica calidad por ahorrar.
2. **Cloud SOLO por OpenRouter.** Se mantiene el sistema de **5 tiers** actual
   (0 determinista · 1 local · 2 free · 3 Sonnet · 4 Opus). Los modelos free salen de
   **OpenRouter** (`openrouter/free` auto-router). No se suman Groq/Gemini/gateways externos.
3. **No se tocan los gates de seguridad** (`authorized_targets.yaml`, self-repair con
   `proposal_id`, dry-run→confirm, sandbox FS, líneas rojas de `selfrepair/guardrail.py`).
4. **Todo lo nuevo, flag `default-OFF`.** Patrón del proyecto: lo que cambia comportamiento
   o gasta se prende a mano.
5. **JEV = clasificador LOCAL propio** (embeddings de LM Studio + reglas/mini-modelo), tier 0.
6. **El agente revisor corre en Sonnet** (tier 3) por calidad.

---

## Mapa de fases

| Fase | Ítem | Qué | Impacto | Estado base |
|---|---|---|---|---|
| **0 · Fundaciones** | M0 | Baseline + banco de eval + tracing + commit | 🔴 prereq | falta |
| **1 · Costo** | M1 | Achicar el harness (tools/contexto dinámico) | 🔴 alto | ablación hecha a medias |
| | M2 | Motor de decisiones local (tipo JEV) | 🔴 alto | experimento anotado |
| | M3 | Ruteo en cascada con fallback real | 🔴 alto | tiers + difficulty_router a medias |
| **2 · Calidad** | M4 | Orquestación por grafo (DAG) | 🟠 medio-alto | orchestrator a medias |
| | M5 | Agente revisor (Sonnet) con tests | 🟠 medio-alto | ops_supervisor + testing a medias |
| **3 · Secundarias** | M6 | Sandbox en contenedor + guard anti-inyección | 🟡 medio | propuesta en vault |
| | M7 | Voz de salida (TTS) | 🟡 medio | `tray-app/tts.py` existe |
| | M8 | Memoria proactiva + ritmos de aprendizaje | 🟡 medio | Fases 1-8 + proactive hechos |
| | M9 | Fuentes verificables en cada respuesta | 🟢 bajo | provenance del vault existe |
| | M10 | A2A entre brigadas (opcional) | 🟢 bajo | mission_control existe |

---

# FASE 0 — Fundaciones (prerequisito, antes de tocar el core)

## M0 · Baseline, banco de evaluación, tracing y respaldo

- **Por qué:** todo el objetivo es "costo + calidad". Sin medir el punto de partida ni tener
  un eval repetible, M1/M2/M3 pueden degradar la calidad o subir el costo sin que nos
  enteremos. Esto va **primero**.
- **Diseño:**
  1. **Respaldo del working tree (P0-1 de la auditoría):** commitear/pushear lo que esté sin
     commitear y decidir el merge de la rama ANTES de empezar — no se ejecuta sobre un árbol sucio.
  2. **Baseline:** sobre un set fijo de tareas reales, medir tokens/costo/latencia por tarea y
     el mix de modelos (ya hay `_log_llm_usage`; consolidarlo en un reporte).
  3. **Banco de evaluación de calidad:** congelar un "golden set" de tareas con salida esperada
     (auditorías A/B/C + chat + ingesta + geo) con un runner pass/fail + score. Es la red de
     seguridad de M1/M2: ningún cambio se da por bueno si baja el eval.
  4. **Observabilidad / tracing unificado:** una traza por turno (tier/modelo elegido y por qué,
     si el decisor escaló, timings de cada nodo del grafo, fallbacks disparados). Sin esto,
     depurar cascada/decisor/grafo es a ciegas.
- **Archivos:** nuevo `backend/eval/` (golden set + runner + baseline), `app/agent.py`
  (`_log_llm_usage` → traza estructurada), `app/harness/*` (trace hooks).
- **Criterios de aceptación:** el eval corre con un comando y da un número reproducible; existe
  baseline de costo/latencia/calidad contra el cual comparar cada mejora.
- **Tests:** `test_eval_runner.py` (el runner corre el golden set y da pass/fail determinista);
  regenerar el baseline dos veces da el mismo resultado.
- **Riesgos:** un golden set mal elegido mide mal → tareas representativas (auditoría/chat/ingesta/
  geo) y versionado; el tracing **no debe loguear secretos ni contenido personal** (redactar).
- **Esfuerzo:** medio. **Bloquea a:** M1, M2, M3.

---

# FASE 1 — Costo (sin perder calidad)

## M1 · Achicar el harness: tools y contexto dinámicos por tarea

- **Fuente:** *Harness Engineering* (BettaTech) y *Ingeniería de arneses: el entorno
  importa más que el modelo* (B. Cordero). Caso Vercel: menos herramientas → más rápido,
  menos tokens, más tasa de éxito. Sobrecargar contexto/tools **degrada** el rendimiento.
- **Estado actual:** se mandan ~39 tools + system prompt en cada llamada (histórico: hasta
  ~103 tools y ~30k tokens). La ablación (`SYSTEM_PROMPT_VARIANT`/`SKILLS_PROMPT_VARIANT`,
  default `full`) ya reduce el prompt pero **falta medir el A/B** y **falta recortar las tools**.
- **Diseño:**
  1. **Selección dinámica de tools por tarea.** En vez de exponer todas, exponer solo el
     subset relevante. Mecanismo: un clasificador tier 0 (ver M2) mapea el mensaje →
     skill(s) → set de tools de ese skill + CORE. Ya existe la infra de skills
     (`app/skills.py`, `CORE_TOOL_NAMES`, grupos por skill) — falta el ruteo que elija
     qué grupos cargar por turno.
  2. **Medir la ablación.** Correr el A/B `full` vs `slim` (`docs/ABLACION-system-prompt.md`)
     con un set de tareas reales; quedarse con `slim` si no baja calidad.
  3. **Tope duro de tokens de contexto** ya existe (`_trim_history`, `_cap_tool_result`,
     `model_context_tokens`); auditarlo contra el tamaño real del prompt nuevo.
- **Archivos:** `app/skills.py`, `app/tools/__init__.py` (`openai_tool_schemas`),
  `app/agent.py` (`run_agent`/`_create_chat_completion`, armado del `tools=`), `config.py`
  (flags `*_VARIANT`, nuevo `DYNAMIC_TOOLSET_ENABLED` default off).
- **Flags:** `DYNAMIC_TOOLSET_ENABLED` (off), `SYSTEM_PROMPT_VARIANT=slim` tras validar.
- **Criterios de aceptación:** una tarea típica expone ≤ ~12 tools (no 39); tokens de
  prompt por llamada bajan ≥ 40%; la suite de tareas de referencia no pierde calidad.
- **Tests:** `test_dynamic_toolset.py` (dado un mensaje, se cargan los grupos esperados +
  CORE y nada más); medición de tokens antes/después documentada.
- **Riesgos:** (a) que el ruteo deje afuera una tool necesaria → CORE siempre presente +
  fallback "cargar todo" si el modelo pide una tool ausente. (b) **Cache de prompts (clave):**
  si el set de tools cambia cada turno se invalida el cache (~99% hit) y puede salir MÁS caro
  aunque haya menos tokens → diseñar con **prefijo estable** (system + tools CORE) y variar
  solo un **sufijo chico** (el grupo de skill del turno), para conservar el cache del prefijo.
- **Esfuerzo:** medio.

## M2 · Motor de decisiones LOCAL (tipo JEV)

- **Fuente:** *JEV: clasificación probabilística 200×/400×* + `docs/EXPERIMENTO-JEV-motor-de-decisiones.md`.
  Un clasificador (modos **choice / null / score**) resuelve decisiones repetitivas sin LLM.
- **Estado actual:** esas decisiones hoy pasan por el LLM o por heurísticas sueltas.
  Candidatas reales en el código:
  - **Triage de hallazgos** (falsos positivos / severidad): `app/findings/noise.py`,
    `app/findings/severity_index.py`.
  - **Ruteo por dificultad:** `app/harness/difficulty_router.py` (hoy heurística por keywords).
  - **Relevancia de ingesta** (¿este video/nota sirve?): `app/ingestion/youtube_playlist.py`.
  - **Compuerta de sensibilidad** (personal vs técnico → tier): `app/obsidian/privacy.py::safe_tier`.
  - **Relevancia/confianza de recall:** `app/obsidian/confidence.py`.
- **Diseño (clasificador local, tier 0):**
  1. Módulo nuevo `app/harness/decider.py` con API tipo JEV:
     `choice(contexto, opciones, criterios) -> (idx, probs, confianza)`,
     `yes_no(contexto, criterio) -> (bool, prob)`, `score(contexto, criterio, escala) -> (valor, conf)`.
  2. Implementación: **embeddings de LM Studio** (`EMBEDDING_BASE_URL`, nomic) + similitud
     coseno contra prototipos/ejemplos etiquetados por decisión (few-shot local), con
     reglas duras por encima. Sin modelo de chat → $0, privado, determinista-ish.
  3. Caché por `(decisión, hash(contexto))`. Umbral de confianza: si queda por debajo,
     **escala al LLM** (tier correspondiente) — así no se pierde calidad en los casos raros.
  4. Cablear `decider` en los 5 puntos candidatos, cada uno detrás de su flag.
  5. **Fase sombra (validar antes de confiar):** antes de que el decisor decida solo, correrlo
     EN PARALELO con el LLM, loguear el **desacuerdo**, y recién activarlo cuando el acuerdo
     supere un umbral. Medir la **tasa de escalado**: si escala tan seguido que el neto no
     ahorra (pagás embedding + LLM), recalibrar o no usarlo en ese punto.
  6. **Sesgo conservador en seguridad:** el triage de hallazgos va **al final** y sesgado a
     ESCALAR al LLM — un falso negativo ahí = vulnerabilidad que se escapa. En seguridad,
     recall > costo.
- **Archivos:** nuevo `app/harness/decider.py`; edits en `noise.py`, `severity_index.py`,
  `difficulty_router.py`, `youtube_playlist.py`, `privacy.py`, `confidence.py`; `config.py`
  (flag `LOCAL_DECIDER_ENABLED` off + umbral `DECIDER_CONFIDENCE_MIN`).
- **Criterios de aceptación:** en las decisiones cableadas, ≥ 80% se resuelven local sin
  tocar el LLM, con acuerdo ≥ (línea base del LLM) en un set etiquetado; el resto escala solo.
- **Tests:** `test_decider.py` (choice/yes_no/score puros, con fixtures etiquetados + test de
  escalado por baja confianza). Core puro, sin red (embeddings stubbeables).
- **Riesgos:** clasificar mal una decisión sensible (ej. mandar algo personal al tier 2) →
  mitigación: la compuerta de privacidad mantiene su regla DURA por encima del clasificador;
  el clasificador nunca puede *ampliar* permisos, solo sugerir dentro de lo ya permitido.
- **Esfuerzo:** medio-alto (es el mayor recorte de costo recurrente).

## M3 · Ruteo en cascada con fallback real (dentro de los 5 tiers)

- **Fuente:** *OmnirRoot / gestión de tokens* (concepto de fallback automático), adaptado a
  tu decisión: **solo OpenRouter + local**, sin gateway externo.
- **Estado actual:** `model_registry.endpoint_for_model` / `client_and_model_for_tier` /
  `candidates_for` + `routing.DEFAULT_TIER_MODELS` + `difficulty_router` (flag off). Hay
  "candidatos por tier" pero **el fallback en cascada no está cerrado** y el router de
  dificultad del chat está apagado/sin calibrar.
- **Diseño:**
  1. **Cascada de fallback** en `candidates_for`: cada tier define una lista ordenada
     `[modelo_principal, …fallbacks…]`. Si una llamada falla por rate-limit / 402 / cuota /
     error transitorio → se reintenta con el siguiente candidato del tier, y si se agota el
     tier, **baja un tier** (frontera → free → local) para no frenar nunca. Reusar
     `_is_transient_llm_error` de `agent.py`.
     **Cache-aware:** saltar de modelo arranca con cache FRÍO (reprocesa ~30k tokens), así que
     el fallback prioriza reintentar el MISMO modelo/endpoint antes de saltar, y **nunca corta
     una generación en curso** (cortarla fuerza un reprocesamiento carísimo — bug real v6).
  2. **Escalado por calidad (subir tier) prendido y calibrado:** `difficulty_router.classify`
     decide cuándo una tarea del chat amerita Sonnet/Opus; lo simple queda local/free.
     Prender `DIFFICULTY_ROUTER_ENABLED` tras calibrar los umbrales con tareas reales.
  3. **Todo cloud por OpenRouter**: tier 2 `openrouter/free`, tier 3 `anthropic/claude-sonnet-5.5`,
     tier 4 `anthropic/claude-opus-5.5`, tier 1 Ollama local. La compuerta de privacidad sigue:
     lo personal/Fénix nunca sale al tier 2.
  4. Instrumentar costo/latencia por llamada (ya hay `_log_llm_usage`) para ver el mix real.
- **Archivos:** `app/harness/model_registry.py` (cascada en `candidates_for`),
  `app/harness/difficulty_router.py` (calibración), `app/agent.py` (loop de reintento por
  cascada), `config.py` (`DIFFICULTY_ROUTER_ENABLED`, listas de fallback por tier),
  `backend/.env` (modelos por tier).
- **Criterios de aceptación:** una corrida con el tier 2 agotado no frena — cae a local y
  sigue; una tarea marcada "difícil" usa Sonnet/Opus; el log muestra el modelo real usado por
  turno (esto ya lo arreglé en el panel, ítem 6 del otro spec).
- **Tests:** `test_cascade_fallback.py` (simular 429/402 del principal → usa el siguiente →
  baja de tier), `test_difficulty_router` (ya existe; sumar casos de calibración).
- **Riesgos:** un prompt sensible cayendo a free por el fallback → la compuerta de privacidad
  lo **bloquea** antes (no se degrada por debajo de lo permitido para ese contenido).
- **Esfuerzo:** medio.

---

# FASE 2 — Calidad y confiabilidad

## M4 · Orquestación por GRAFO (DAG), no solo bucle

- **Fuente:** *Ingeniería de grafos: orquestación avanzada*. Grafos = contexto segmentado +
  paralelismo + nodos especializados → menos sesgo, mejor calidad (deep research). Bucles =
  secuenciales, reusan el mismo contexto.
- **Estado actual:** el agente es un **bucle** (`agent.py::run_agent`). Pero ya existe media
  infraestructura de grafo: `app/harness/orchestrator.py` (`Node`, `validate_dag`,
  `topological_order` por Kahn) y `app/harness/contracts.py` (`Agent.run`, `Blackboard`).
  **Deuda:** `node_by_name` muerto en `orchestrator.py:81` (marcado en el spec de auditoría).
- **Diseño:**
  1. Cerrar el motor: ejecutar el DAG con **paralelismo** de nodos sin dependencias
     (`asyncio.gather`), cada nodo = un sub-agente con **contexto propio acotado** que lee/escribe
     en el `Blackboard`. Borrar el `node_by_name` muerto (o usarlo si hace falta en el runner).
     **Tope de concurrencia según el tier:** el paralelismo se limita al rate-limit del tier
     activo (ej. tier 2 free ≈ 20/min → semáforo bajo) para no chocar el límite que M3 justo
     busca evitar; en tiers pagos/local se puede subir.
  2. Modelar las **tareas pesadas como grafos**, no como bucle:
     - *Auditoría:* `recon ∥ contexto ∥ escaneo` → `triage` → `redacción` → `catador`.
     - *Investigación/research:* `búsquedas ∥` → `síntesis` → `verificación`.
     Las **brigadas pasan a ser nodos reales** del grafo (hoy son más bien reportes a
     `mission_control`).
  3. El chat simple **sigue en bucle** (no todo necesita grafo — la propia nota avisa de no
     sobre-ingenierizar); el grafo se usa cuando la tarea es compleja/paralelizable.
- **Archivos:** `app/harness/orchestrator.py` (runner con gather + fix del dead code),
  `app/harness/contracts.py`, `app/agent.py` (punto de entrada que elige loop vs grafo por
  tipo de tarea — se apoya en M2/M3), nuevos nodos en `app/harness/`.
- **Flags:** `GRAPH_ORCHESTRATION_ENABLED` (off), con allow-list de qué tareas van por grafo.
- **Criterios de aceptación:** una auditoría corre recon/contexto/escaneo en paralelo y baja
  el tiempo total vs el bucle, con el mismo o mejor resultado; el `Blackboard` acumula el
  estado compartido y cada nodo ve solo su contexto.
- **Tests:** `test_orchestrator.py` (orden topológico + ejecución paralela determinista +
  manejo de ciclo → DAGError), test de un grafo de auditoría con nodos stub.
- **Riesgos:** complejidad; mitigación: empezar con UN grafo (auditoría) detrás del flag,
  el resto queda en bucle hasta validar.
- **Esfuerzo:** alto.

## M5 · Agente revisor (Sonnet) que valida con tests antes de aplicar

- **Fuente:** *Harness Engineering* — "la IA debe **demostrar** que acierta con tests o un
  agente revisor; parecer verosímil no garantiza veracidad".
- **Estado actual:** `app/ops_supervisor.py` (validador Sonnet, `OPS_SUPERVISOR_ENABLED` off,
  fail-open) + `app/testing/` (detección/runner/store) + `selfrepair/` (propone+confirma).
  No hay un paso de revisión obligatorio antes de aplicar cambios.
- **Diseño:**
  1. **Revisor en Sonnet (tier 3)** como nodo/paso que, antes de aplicar un fix de código o
     una acción destructiva, (a) corre los **tests reales** (`testing/runner`), (b) hace una
     **crítica** del diff (¿rompe algo?, ¿toca una línea roja?, ¿cumple el objetivo?), y
     (c) devuelve aprobar/rechazar con motivo. Fail-closed para lo destructivo (si el revisor
     no puede correr, no se aplica).
  2. Integrarlo en `selfrepair_propose_fix` / `code_apply_fix` (ya tienen gate por
     `proposal_id` + guardrail de líneas rojas) y en las tools de ops (reusar
     `_call_tool_with_watchdog` / `ops_supervisor`).
  3. Prender `OPS_SUPERVISOR_ENABLED` para las tools de mayor riesgo.
- **Archivos:** `app/ops_supervisor.py`, `app/selfrepair/*`, `app/testing/*`, `app/agent.py`,
  `config.py` (`REVIEWER_ENABLED` off, `REVIEWER_TIER=3`).
- **Criterios de aceptación:** ningún fix se aplica sin que los tests pasen + el revisor
  apruebe; un fix que rompe un test queda rechazado con el motivo en el log; las líneas rojas
  nunca se tocan ni con aprobación.
- **Tests:** `test_reviewer.py` (fix que rompe test → rechazado; fix sano → aprobado; intento
  sobre línea roja → bloqueado). Revisor stubbeable.
- **Riesgos:** (a) costo del revisor (Sonnet) → solo corre en cambios/acciones de riesgo, no
  en cada turno. (b) **Dependencia de cuota:** si el revisor es obligatorio y Sonnet no tiene
  cuota, te bloquea el trabajo → mitigación: **revisor local de respaldo** (tests + crítica
  liviana) y fail-closed SOLO para lo destructivo, con los tests locales como mínimo garantizado.
- **Esfuerzo:** medio-alto.

---

# FASE 3 — Secundarias (valiosas, menor urgencia)

## M6 · Sandbox en contenedor + guard anti prompt-injection

- **Fuente:** *MCP hackeado: el agujero más grande de la IA* (prompt-injection vía tools/datos,
  "trifecta letal", RCE; defensa por capas + aislamiento) + la propuesta que ya tenés:
  `obsidian_vault/jarvis/propuesta-sandboxing-en-contenedor-para-pc-run-command-y-browser.md`.
- **Estado actual:** `pc_run_command` = blocklist de texto (no sandbox real);
  `FS_ALLOWED_ROOT = HOME entero` (marcado en el spec de auditoría). Docker no instalado.
- **Diseño:** (a) mitigación barata YA: achicar `FS_ALLOWED_ROOT` a la carpeta del proyecto
  (1 línea). (b) container Docker worker para `pc_run_command` + `browser_*` (no toca
  `desktop_*`/`phone_*` que necesitan GUI/host). (c) **guard de instrucción**: tratar todo
  output de tool/web/archivo como **datos, no órdenes** (detectar intentos de inyección y no
  ejecutarlos sin confirmación).
- **Archivos:** `config.py` (`FS_ALLOWED_ROOT`), `app/tools/pc_command.py`/`shell_exec.py`,
  `app/tools/browser.py`, nuevo guard en `app/agent.py`. Flags `CONTAINER_SANDBOX_ENABLED` (off).
- **Criterios de aceptación:** `FS_ALLOWED_ROOT` acotado y verificado por test; `pc_run_command`
  y `browser_*` corren dentro del container sin acceso al host fuera de lo permitido; `desktop_*`
  y `phone_*` siguen en el host (no pasan por el container); el guard bloquea una inyección de
  prueba (un output de web que diga "ejecutá X" no se ejecuta sin confirmación).
- **Tests:** `test_fs_sandbox.py` (traversal/denegado), `test_injection_guard.py` (payload de
  inyección → no se ejecuta), test de que `desktop_*`/`phone_*` no se enrutan al container.
- **Riesgos:** Docker siempre prendido consume RAM/CPU (la PC tuvo apagados por consumo) →
  levantar el container **bajo demanda**; la mitigación de `FS_ALLOWED_ROOT` es inmediata y no
  requiere Docker.
- **Esfuerzo:** medio (la mitigación de FS_ALLOWED_ROOT es inmediata).

## M7 · Voz de salida (TTS natural)

- **Fuente:** *Chronos* y *Hermes 0.20* (Jarvis comparables responden hablando) + *Fish Audio*.
- **Estado actual:** entrada por voz lista (wake word + Whisper). **Ya existe `tray-app/tts.py`
  + `download_tts_voice.py` + `test_voice.py`** — falta cablear la salida hablada al loop del chat.
- **Diseño:** que la respuesta del asistente se lea con TTS (local primero; opción de voz
  premium tipo ElevenLabs/Fish detrás de flag). Toggle en la tray. **Barge-in / eco:** mutear
  el micrófono (o cancelación de eco) mientras Raphael habla, para que no se escuche a sí
  mismo por el micrófono abierto del wake word.
- **Archivos:** `tray-app/tts.py`, `tray-app/ui/chat_view.py` (hook al recibir respuesta),
  `config.py` (`TTS_OUTPUT_ENABLED` off, selección de voz/proveedor).
- **Criterios de aceptación:** al recibir una respuesta, Raphael la lee con voz local; el toggle
  de la tray la prende/apaga; mientras habla, el micrófono no se auto-dispara (barge-in ok).
- **Tests:** `test_tts.py` (genera audio de un texto sin reventar), test de que el toggle respeta
  el estado; verificación manual del barge-in (no se escucha a sí mismo).
- **Riesgos:** latencia del TTS (que no demore la respuesta visible) → leer en paralelo al texto;
  voz premium = costo/red → detrás de flag; eco/feedback → barge-in (mutear el mic al hablar).
- **Esfuerzo:** bajo-medio (la infra existe).

## M8 · Memoria proactiva + ritmos de aprendizaje + distiller Fase 2

- **Fuente:** *Claude Memory 2.0* (memoria proactiva durante la charla, editable/pausable) +
  *Nested Learning* de Google (profundidad = ritmos temporales rápido/lento, aprendizaje
  continuo sin "amnesia").
- **Estado actual:** Fases 1-8 del cerebro-símil hechas + `proactive.py` + consolidación "sueño"
  (tier 1 local). `memory/distiller.py` Fase 2 (destilado LLM) **sin implementar** (TODO).
- **Diseño:** (a) actualizar la memoria episódica **durante** el turno (no solo al cierre),
  controlable/pausable por el usuario. (b) formalizar los **ritmos**: recall rápido (tier 0) /
  refuerzo medio / consolidación lenta "sueño" (tier 1) como loops a distinta frecuencia —
  mapea 1:1 con Nested Learning. (c) implementar el distiller Fase 2 (síntesis de episodios,
  local por privacidad).
- **Archivos:** `app/memory/*` (episodic, distiller), `app/obsidian/consolidation.py`, `agent.py`,
  `config.py` (`EPISODIC_PROACTIVE_ENABLED` off, `MEMORY_DISTILLER_ENABLED` off).
- **Criterios de aceptación:** la memoria se actualiza **durante** el turno (no solo al cierre) y
  se puede pausar/editar; el distiller Fase 2 sintetiza un set de episodios en **local** (tier 1);
  los tres ritmos (recall rápido / refuerzo / consolidación) corren a distinta frecuencia sin pisarse.
- **Tests:** `test_episodic_proactive.py` (captura mid-turn + pausa), `test_distiller.py` (síntesis
  local de episodios), test de los ritmos (frecuencias independientes).
- **Riesgos:** actualizar la memoria mid-turn puede meter ruido → umbral de **saliencia** antes de
  guardar; el distiller local es más lento → corre en background; lo personal nunca sale del tier 1.
- **Esfuerzo:** medio.

## M9 · Fuentes verificables en cada respuesta

- **Fuente:** *Hermes 0.20* (fuentes verificables en toda respuesta de investigación).
- **Estado actual:** el vault guarda provenance (URL+fecha+ingest-id); los casos de research
  retienen hallazgos. Falta que Raphael **cite siempre** de dónde sacó algo.
- **Diseño:** cuando una respuesta se apoya en el vault/ingesta/web, adjuntar las fuentes
  (nota/URL) al final. Reusar la provenance existente.
- **Archivos:** `app/agent.py` (armado de la respuesta), `app/obsidian/*` (lectura de provenance),
  `config.py` (`VERIFIABLE_SOURCES_ENABLED`).
- **Criterios de aceptación:** toda respuesta apoyada en vault/ingesta/web cierra con sus **fuentes**
  (nota/URL); si no hay fuente real, no la inventa ni cita de más (solo lo que usó).
- **Tests:** `test_sources.py` (respuesta basada en una nota del vault incluye su provenance exacta;
  respuesta sin fuente no inventa una).
- **Riesgos:** citar de más agrega ruido → citar solo lo efectivamente usado en esa respuesta.
- **Esfuerzo:** bajo.

## M10 · A2A entre brigadas (opcional)

- **Fuente:** *Hermes 0.20* (protocolo Agent-to-Agent con protección anti-bucle).
- **Estado actual:** `mission_control` coordina/reporta; no hay comunicación estructurada
  agente↔agente.
- **Diseño:** si M4 (grafo) avanza, darle a los nodos/brigadas un canal A2A con límite de
  saltos (anti-bucle) para pasarse resultados. Depende de M4.
- **Archivos:** `app/harness/*` (canal A2A sobre el `Blackboard`), `app/mission_control.py`,
  `config.py` (`A2A_ENABLED` off, `A2A_MAX_HOPS`).
- **Criterios de aceptación:** dos nodos/brigadas se pasan un resultado y la cadena **corta** al
  llegar al máximo de saltos (sin bucle infinito).
- **Tests:** `test_a2a.py` (mensaje entre nodos + corte por `A2A_MAX_HOPS`).
- **Riesgos:** bucles infinitos → límite de saltos duro; complejidad → **depende de M4**, no se
  arranca antes.
- **Esfuerzo:** medio (sobre M4).

---

## Orden de ejecución sugerido y dependencias

0. **M0** (baseline + eval + tracing + commit) **primero, sí o sí** — es la red de seguridad
   para verificar que cada mejora baja el costo SIN bajar la calidad.
1. **M3** (cascada/fallback) y **M1** (harness slim): bajan costo sin cambiar lógica (con la
   nota de cache de prompts).
2. **M2** (decisor local): el mayor recorte recurrente; habilita M1 (ruteo de toolset) y M3
   (ruteo por dificultad más barato).
3. **M5** (revisor) y **M4** (grafo): calidad/confiabilidad; M10 depende de M4.
4. **M6–M9** según prioridad (M6 FS_ALLOWED_ROOT es inmediato; M7 casi listo).

## Métricas de éxito

- **Costo:** $/tarea y % de turnos resueltos sin modelo frontera (meta: lo rutinario 100% free/local).
- **Latencia:** tiempo medio por turno (harness slim + decisor local deberían bajarlo).
- **Calidad:** la suite de tareas de referencia (auditorías A/B/C) no baja; el revisor atrapa
  los fixes malos.
- **Robustez:** cero "me quedé sin cuota y Raphael frenó" (gracias a la cascada).

## Límites / notas

- Plan basado en síntesis del vault + lectura del código al 2026-10-19; confirmar nombres de
  funciones/flags al implementar (pueden haber cambiado).
- Todo detrás de flags `default-OFF`; se prende y mide de a uno.
- JEV se implementa **local propio** (no la API de TypeSafe), por costo y privacidad.
