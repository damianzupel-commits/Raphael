# ESTADO.md — Instantánea del proyecto

> Estado operativo del repo. Para el contexto estructural (arquitectura, modelos,
> convenciones, gates de seguridad) ver `CLAUDE.md`. **Actualizá este archivo al
> cerrar cada sesión** (ver protocolo al final).

**Última actualización:** 2026-09-30
**Último commit:** `6b68e68 opt: ablacion prompts (system -80%, skills+core -65%, gates intactos)`
**Rama:** ⚠️ `opt/system-prompt-ablacion` — TODO el trabajo de las sesiones 2026-09-29/30
está acá, **NO en master** (master quedó en `46c49b6`). Falta decidir el merge a master.
**Working tree:** ⚠️ hay cambios SIN commitear (el ruteo de modelos, punto 8 abajo).
Claude no puede commitear desde su entorno (permisos del mount de `.git`); commitealo
vos: `git add -A && git commit -m "feat: ruteo de modelos + retiro opencode/cloud_expert"`.

---

## Sesión 2026-10-11/13 — app móvil, Centro de Mando nativo, autoconciencia (leé esto primero)

> Tanda grande con Claude. **TODO SIN COMMITEAR** (Damian pidió no commitear). Plan de
> ejecución detallado: `docs/SPEC-PLAN-2026-10-13-cierre-gaps-panel-auth-autoconciencia.md`.
> Patrón de todo lo nuevo: flags que cambian comportamiento o gastan plata/red van **default OFF**.

**Modelo free + ruteo:** se abandonó OmniRoute (bug de auth) → tier 2 por **OpenRouter auto-router**
(`openrouter/free`). `TIER2_BASE_URL`/`TIER2_API_KEY`. Router de dificultad del chat construido
(`difficulty_router.py`, flag off). Override de endpoint/key/modelo **por tier** (TIER{1,3,4}_* + los
TIER2_* existentes) en `model_registry.endpoint_for_model(tier=...)` — cada tier puede tener su API.

**Config amigable (web, `/configuracion`):** panel data-driven (`app/user_config.py` + docs/raphael/
configuracion-raphael.html) servido por el backend, embebido en la tray (`ui/config_dialog.py`). Toggles/
text/number/select/secret. Sección **APIs por tier** (keys enmascaradas, nunca se devuelven). Al guardar,
el diálogo se cierra y reabre solo. Sección **Dispositivos vinculados** (listar/revocar). Reemplaza al
viejo diálogo de 5 toggles.

**Sync por QR (Etapa 1):** `app/pairing.py` + `/vincular` + tray `ui/pair_dialog.py` + Android
`PairScanScreen.kt`/`PairingPayload.kt`. La PC muestra un QR, el cel lo escanea y queda configurado solo.
El QR emite un **device token** (no la key maestra).

**Auth por dispositivo (DPAPI):** `app/device_tokens.py` — tokens revocables por dispositivo (guarda
solo el hash + DPAPI). `auth.py` con scopes: `verify_api_key` (master/full) + `verify_read` (solo lectura).
Mission-control y el globo ahora piden token (WS acepta `?key=` porque el navegador no puede setear headers).
Endpoints `/api/devices` + `/api/devices/revoke`. La key maestra sigue valiendo (no rompe la tray).

**CENTRO DE MANDO NATIVO (Android, `ui/mando/`):** grilla de las **10 brigadas** en vivo (WS), detalle con
escuadrón/tiers, **monitor de tools en vivo** ("actividad en vivo"), secciones interactivas de **Ingesta /
Investigación / Trading**, y **grafo 3D de Obsidian** (~410 notas, rotar/zoom/tap). El panel HTML de la PC
tiene las mismas secciones (paridad, ítem 4).

**Brigadas — lo construido esta tanda:**
- *Operaciones:* supervisor Sonnet (`ops_supervisor.py`, `OPS_SUPERVISOR_ENABLED`, fail-open) + watchdog
  (`OPS_WATCHDOG_ENABLED`) para destrabar tools colgadas. Ambos **off** por default.
- *Ingesta:* watchlist de fuentes + registro de ingeridos con link (`ingestion/sources.py`); el watcher
  recorre la watchlist; web ingerida también se registra. Endpoints `/api/ingest*`.
- *Investigación:* casos de research retenidos (`research_cases.py`); un pedido "investigá X" crea el caso y
  **la respuesta final se engancha como hallazgo**. Endpoints `/api/investigation*`.
- *Trading:* watchlist + estado/bias/R:R/confianza + **panel de riesgo** (sizing de la señal) + **track record**
  (backtest, `/api/trading/watch/backtest`) + **alertas** (loop `TRADING_WATCH_LOOP_ENABLED` off → avisa por
  panel + espejo de chat). SOLO análisis, nunca opera.
- *Memoria/Antimalware:* los jobs de fondo (consolidación/curiosidad/malware) ahora **reportan a su brigada**.
- *Geolocalización pública (NUEVA, #10):* `app/geo_intel.py` + globo 3D `/globo` (Three.js propio, MIT-limpio,
  inspirado en God's Eye View de Bilawal Sidhu). `ip_geolocate` cae como **pin en el globo** en vivo. Capa de
  **vuelos** (ADS-B público de OpenSky, proxy server-side `/api/geo/flights`). Pestaña tray `🌐 Mapa de
  inteligencia` + overlay nativo (`ui/mando/GloboOverlay.kt`).

**Aprendizaje proactivo (`app/proactive.py`, `PROACTIVE_LEARNING_ENABLED` off):** amplía casos abiertos /
llena huecos del vault por iniciativa propia.

**Autoconciencia — capa 1 (self-model):** `app/self_model.py` + `GET /api/self` + tool **`raphael_self_model`**
(en CORE): Raphael lee qué es / qué puede / qué tiene apagado / sus líneas rojas / sus límites honestos
(incl. que la conciencia fenoménica no se resuelve). Pendiente del ítem 6 (🔬 research): LAYA calibrada (F1),
auto-detectar tests→refuerzo positivo (F2), reconsolidación de contenido (F3).

**A cargo de Damian:** `pip install qrcode` (QR), `ccxt`/`yfinance` (trading real), `scrapling` (web_get);
reiniciar backend + `.\gradlew.bat installDebug`; **commitear** (nada commiteado). Verificado por py_compile +
tests aislados + node --check del JS (el sandbox no importa la app por win32crypt; corré pytest vos).

**Pendiente del plan:** ítem 6 F1/F2/F3 (research); capas ricas del globo (barcos/cables) o forkear God's Eye
View (MIT; ojo datos no-comerciales para el producto).

---

## Sesión 2026-10-04 — estructura informacional cerebro-símil (leé esto primero)

Objetivo de Damian: que la estructura de info de Raphael funcione lo más parecido a
un cerebro + que pueda **indexar/embeber info directa de internet**. Spec:
`docs/SPEC-estructura-informacional-cerebro.md` (cuatro sistemas de memoria, dinámicas,
tabla §3-bis de qué procesador/tier ejecuta cada función, estado del arte Exa/Firecrawl/
Jina/MCP y el hueco vertical-local-MCP).

- **Fase 1 — Spreading activation (HECHO, tier 0 puro):** `app/obsidian/spreading.py`
  (`propagate` pura + `search_spreading`), tool `obsidian_buscar_asociativo` (en CORE),
  test `tests/test_spreading.py`. Recupera por asociación: semillas por coseno →
  propaga por los wikilinks del grafo con decay + convergencia.
- **Fase 2 — Pesos Hebbianos (HECHO, tier 0):** `app/obsidian/hebbian.py` (`bump` pura +
  persistencia JSON junto al índice de embeddings), wireado en `search_spreading`
  (`usar_pesos`/`reforzar`) y en la tool (`reforzar=true`). Satura en cap. Test
  `tests/test_hebbian.py`. **Falta de Fase 2:** reconsolidación de CONTENIDO (§3.5).
- **Ingesta web directa (HECHO):** `app/obsidian/web_ingest.py` (tool `obsidian_ingerir_web`,
  en CORE). URL → `web_get` → `chunk_text` (pura) → embeber nomic → notas enlazadas con
  provenance (URL+fecha+web-ingest-id), idempotente, sin modelo de chat. Test
  `tests/test_web_ingest.py`. Es la "biblioteca para IA a escala personal".
- **BUG ENCONTRADO Y ARREGLADO — ingesta de videos no andaba desde el chat:** Damian
  pidió ingerir videos sueltos y Raphael le devolvió los capítulos (web_get) sin guardar
  nada. Causa raíz doble: (1) NO existía tool de video suelto (solo `youtube_ingest_playlist`,
  playlist entera); (2) esa tool NO estaba en ningún skill → el agente nunca la exponía
  (solo era accesible por CLI). Fix: `ingest_video` + `fetch_video_entry` nuevos en
  `youtube_playlist.py` (reusan el pipeline por-video, extraído a `_process_entry`), tool
  `youtube_ingest_video` (`tools/ingestion.py`), y **nuevo skill `ingesta`** que expone
  `youtube_ingest_video` + `youtube_ingest_playlist` + `obsidian_ingerir_web` con keywords
  (verificado que "ingestar los videos" lo dispara). De paso mapeé `audit_report_brigade`
  (hueco preexistente: registrado sin skill, rompía test_skills) a `security_audit`. Test
  `tests/test_youtube_single_video.py`. **Para que tome efecto: reiniciar el backend.**
- **Ingesta AUTOMÁTICA de la playlist (2026-10-05):** vigilante en background
  `app/ingestion/playlist_watcher.py` (`watch_loop`, enganchado en `main.py` startup
  como el scan de malware). Cada `PLAYLIST_WATCH_INTERVAL_MINUTES` (default 3, pedido de
  Damian) revisa la playlist e ingiere SOLO los videos nuevos (idempotente; si no hay
  novedad, chequeo barato sin LLM). Corre en background → no sufre el timeout de la tray.
  Flags: `PLAYLIST_WATCH_ENABLED` (default true), `PLAYLIST_WATCH_INTERVAL_MINUTES`,
  `PLAYLIST_WATCH_MAX_PER_RUN` (default 8, 0=sin tope), `PLAYLIST_WATCH_URL`. Test
  `tests/test_playlist_watcher.py`. **Requiere reiniciar el backend.** OJO: con videos
  nuevos consume el LLM activo (lento en local, con costo en Sonnet).
- **Nota sobre la ingesta manual (2026-10-05):** NO estaba rota — funciona. El
  "Read timed out (1800s)" de la tray es porque la playlist entera en el modelo LOCAL
  tarda >30 min (cada video ~1-2 min); el backend sigue atrás y crea las notas igual
  (13 notas de video creadas hoy, verificadas). El vigilante en background resuelve esto
  de raíz. Para ingesta manual sin timeout: Sonnet, o "ingestá N videos" (max_videos).
- **Fase 4 — Olvido adaptativo (HECHO, tier 0):** `app/obsidian/strength.py`. Fuerza de
  recuperación por nota: sube al usarse, decae sin uso (half-life 14d), pondera el
  ranking del spreading (`usar_fuerza`). Nunca entierra bajo lo neutro, no borra nada.
  Test `tests/test_strength.py`.
- **Fase 3 — Consolidación "sueño" (HECHO):** `app/obsidian/consolidation.py`. Agrupa
  notas recientes relacionadas (clusters por coseno, core puro) y escribe notas de
  SÍNTESIS con el LLM local (tier 1) + refuerza links. ADITIVO/reversible (no toca las
  originales), idempotente. Tool `memoria_consolidar` (dry-run default) + job background
  `consolidation_loop` (default APAGADO, `CONSOLIDATION_ENABLED`; interval/lookback/
  threshold/max-clusters configurables). Test `tests/test_consolidation.py`.
  **Requiere reiniciar el backend.** La estructura cerebro-símil (Fases 1-4) está COMPLETA.
- **Rastro de activación en vivo sobre el grafo (2026-10-05):** cuando Raphael recupera
  notas (spreading o búsqueda normal), guarda el rastro en `app/obsidian/activation_trace.py`
  y lo expone en `GET /api/obsidian/activation`. La pestaña Obsidian de la tray lo pollea
  (QTimer 1.5s, solo mientras está visible) y enciende esos nodos en el grafo 3D con un
  halo dorado que se desvanece (el "rastro"), vía `graph3d.html::setActivation` +
  `GraphView.set_activation`. Halo paralelo al de severidad (no lo pisa), mismo truco de
  geometría prestada. Backend testeado (`tests/test_activation_trace.py` + core del grafo
  verificado por JS syntax). **La parte visual (QWebEngine) NO se pudo correr en el sandbox:
  Damian la confirma reiniciando la tray + backend y chateando con el grafo abierto.**
- **Vault unificado DE VERDAD (2026-10-05):** el lector solo leía `jarvis/` y `human/`
  (flat) → Raphael veía 19 de 440 notas. Ahora `vault.list_notes` recorre TODO Vault-Fenix
  recursivamente: las carpetas temáticas (10-Raphael-Seguridad=328, 07-Conciencia=39, etc.)
  se leen como autor 'human'; excluye `.`/`_` y `OBSIDIAN_EXCLUDED_DIRS`. El `id` pasó a
  ser la ruta relativa (los ids de jarvis/ NO cambian). `get_note` ahora acepta rutas
  anidadas (`{note_id:path}`), `read_note`/`save_note`/`_note_path` generalizados (guard de
  traversal). Nueva tool `obsidian_reindexar` (recalcula embeddings de las ~437, en skill
  memoria). Verificado contra el Vault-Fenix real (437 notas) + tests
  `tests/test_vault_topical.py`. **Al reiniciar: el grafo muestra las 437; para semántica/
  spreading correr `obsidian_reindexar` con LM Studio (:1234) prendido.**
- **Raphael predictivo (spec + Fase 5, 2026-10-05):** nuevo spec
  `docs/SPEC-raphael-predictivo.md` — las 4 vistas modernas de la cognición que el
  diseño asociativo no tenía (procesamiento predictivo/inferencia activa, representación
  sucesora, analogía/structure-mapping, consolidación por esquema), + el encuadre de
  Damian "el modelo de IA = la conciencia del cerebro" (3 capas: estructura/dinámica/
  modelo; conciencia de acceso vs. fenoménica; funcionalismo vs IIT). **Fase 5 HECHA:**
  `app/obsidian/successor.py` — representación sucesora (transiciones DIRIGIDAS A→B,
  a diferencia del Hebbian simétrico), recall anticipatorio en `search_spreading`
  (`anticipar=True`) y en la tool `obsidian_buscar_asociativo`. Tier 0 puro, test
  `tests/test_successor.py`. **Fases 6-8 también HECHAS (2026-10-05):** F6 saliencia por
  sorpresa (`successor.surprise()` escala el bump de fuerza en `search_spreading`); F7
  analogía/structure-mapping (`app/obsidian/analogy.py` + tool `obsidian_analogia`); F8
  consolidación por esquema (`consolidation.schema_fit`) + composición
  (`app/obsidian/composition.py` + tool `obsidian_componer`). Todas tier 0 (+embeddings),
  con tests. La estructura cerebro-símil (Fases 1-8) está COMPLETA. **Requiere reiniciar el backend.**
- **Ruteo de modelos a 5 TIERS (2026-10-06, nuevo esquema de Damian):** `routing.py`
  `DEFAULT_TIER_MODELS` reescrito: **0** sin modelo (determinista) · **1** LOCAL
  (`jarvis-text-v2`, jobs programados; sin fallback cloud por privacidad) · **2**
  FREE rotativos de OpenRouter (operativo/simple, `TIER2_FREE_MODELS` env-config,
  default llama-3.3-70b:free + gpt-oss-120b:free + nemotron-3-super:free; solo
  contenido NO sensible) · **3** Sonnet 5.5 (pesado) · **4** especial = Opus (lo más
  duro; el planner ya usa Opus por su propia config). Las estaciones de razonamiento
  de las brigadas (audit E3/E5/E6, trading T8) renumeradas de tier 2→3 para seguir en
  Sonnet. El "sueño" (consolidación) ahora corre en **tier 1 local** explícito
  (`model_registry.client_and_model_for_tier(1)`) — correcto por diseño y por privacidad
  (sintetiza notas personales sin salir de la PC). Tests de harness siguen genéricos/
  verdes. **PENDIENTE:** ruteo del AGENTE PRINCIPAL por tarea (hoy el tier aplica a
  brigadas/jobs, no al chat; falta que el agente elija modelo por tarea — lo charlado).
  **Requiere reiniciar el backend.**
- **Principios informacionales 9+ / Etapa A del cerebro no biológico (2026-10-06):**
  plan maestro en `vision/RAPHAEL-CEREBRO-NO-BIOLOGICO.md` (anatomía de órganos + etapas
  A-D, honesto sobre 🔨/🔬/❓). Construido (tier 0, con tests):
  - **Metacognición/confianza:** `app/obsidian/confidence.py` → `search_spreading` devuelve
    `confianza` por nota + `confianza_global` + `recomendacion` (confiar/verificar). LAYA
    queda como estimador calibrado encima (pendiente, su 2da vida).
  - **Atención/separación de patrones:** `app/obsidian/attention.py` (MMR) →
    `buscar_asociativo(diversificar=true)` evita casi-duplicados.
  - **Crédito por resultado (sustrato lazo B):** `app/obsidian/feedback.py` + tool
    `obsidian_feedback` (en CORE) — refuerza lo que SIRVIÓ, no solo lo co-usado.
  Tests: test_confidence, test_attention (+ cores verificados). Etapas B(lazo cerrado)/
  C(impulsos/proactividad)/D(auto-rediseño) + principios restantes = 🔬 investigación.
  **Requiere reiniciar el backend.**
- **Etapa B — lazo cerrado de aprendizaje (CONSTRUIDA, 2026-10-06):** crédito por
  resultado con refuerzo Y **marcado aversivo** (LTD) — `strength.py` ahora soporta
  valencia negativa con piso (factor ≥0.5), `hebbian.weaken/debilitar` baja aristas con
  piso (≥0.3); homeostasis. `feedback.reward_from_signals` combina señales por situación
  catalogada (auto en código/auditoría, explícito en conversación) → `credit`/`outcome`.
  Tools `obsidian_resultado` (cierra el lazo) y `obsidian_feedback`, ambas en CORE. Tests
  `test_feedback.py` + strength negativo. Decisiones B/C/D registradas en
  `vision/ETAPAS-BCD-diseno.md`. **Hook automático HECHO (2026-10-06):** en el `finally` de
  `run_agent`, si el turno se cae por una excepción, marca AVERSIVAMENTE (con piso) las notas
  del último rastro de activación — señal negativa objetiva, auto; el refuerzo positivo queda
  explícito (`obsidian_resultado`). Flag `FEEDBACK_AUTO_ENABLED` (default on), 100% defensivo.
  **La Etapa B quedó COMPLETA.** (Pendiente fino 🔬: auto-detectar tests/correcciones para el
  refuerzo positivo automático.)
- **Etapa C — proactividad / curiosidad (CONSTRUIDA, 2026-10-06):** `curiosity.py` detecta
  huecos del vault (notas faltantes citadas, huérfanas) → tool `obsidian_curiosidad` + job
  `curiosity_loop` (default OFF, solo-avisar). `goals.py` metas persistentes + tool
  `obsidian_objetivos`. `privacy.py` compuerta de sensibilidad (`safe_tier`): lo personal
  (Fénix) nunca va al tier 2 free. Tests test_curiosity/test_privacy.
- **Etapa D — auto-rediseño seguro (CONSTRUIDA, 2026-10-06):** `app/selfrepair/guardrail.py`
  (`is_protected`/`check`) formaliza las LÍNEAS ROJAS en código — wireado en
  `selfrepair_propose_fix` Y `code_apply_fix`: la auto-modificación NUNCA toca
  authorized_targets/gate/auth/.env/config, ni con confirmación. Kill-switch
  `SELF_REDESIGN_ENABLED` (default off) + `SELF_PROTECTED_PATHS`. Grafo auto-tunea (ya
  pasa); código siempre propuesto+confirmado. Test test_guardrail.
- **MODO PRUEBA free-only (2026-10-06):** `app/testmode.py` + tool `raphael_modo_prueba`.
  Para cuando no hay crédito en OpenRouter: el chat y los tiers pagos (3/4) caen a modelos
  FREE (tier 2, $0), y NO toca material personal (el lector del vault excluye las carpetas
  sensibles). Env `TEST_MODE` o runtime. Tests test_testmode. **Requiere reiniciar el backend.**
- **TIER 2 vía OmniRoute (2026-10-07, idea de Damian):** el tier 2 free ahora puede salir
  por un gateway OpenAI-compatible configurable en vez de OpenRouter. Config nueva
  `TIER2_BASE_URL`/`TIER2_API_KEY` (default vacío = OpenRouter como siempre). Si apuntás
  `TIER2_BASE_URL` a **OmniRoute** (`http://localhost:20128/v1`, gateway local open-source
  que rota 90+ proveedores free con fallback por cuota + compresión de prompts), tanto el
  modo prueba como los jobs/estaciones que resuelven tier 2 salen por ahí. Cambios:
  `model_registry.endpoint_for_model` (rama tier-2→gateway ANTES del chequeo de "/"),
  `testmode.chat_client_and_model` (el chat resuelve su cliente+modelo del tier 2),
  `agent._create_chat_completion` (acepta `_client`, y el `extra_body` de usage de
  OpenRouter se decide por el endpoint REAL del cliente). Tests nuevos en
  test_model_registry (4) + test_testmode (1). La compuerta de privacidad SIGUE aplicando:
  lo personal/Fénix nunca llega al tier 2, use OpenRouter u OmniRoute. **A cargo de Damian:**
  `npm install -g omniroute`, correr `omniroute`, conectar cuentas en su dashboard, setear
  las 2 vars en `.env`, reiniciar el backend. Verificado por py_compile + lógica aislada
  (sandbox no importa la app por `win32crypt`); corré pytest y commiteá vos en PowerShell.
- **TIER 2 resuelto vía OpenRouter auto-router (2026-10-06):** OmniRoute tenía un bug de
  auth en `/v1` (key válida, "nunca usada", 401). En vez de pelearlo, apuntamos el tier 2
  directo a OpenRouter con el modelo **`openrouter/free`** (auto-router que rota modelos free
  solos, matcheando tool-calling). En el `.env`: `TIER2_BASE_URL=https://openrouter.ai/api/v1`,
  `TIER2_API_KEY`=su key de OpenRouter (reusada de LLM_API_KEY), `TIER2_FREE_MODELS=openrouter/free`.
  Backup del `.env` con OmniRoute en `.env.bak-omniroute-20261006`. Límite free: 20/min,
  1000/día (Damian compró $10 alguna vez). Con `TEST_MODE=true` el chat sale por acá, no por el local.
- **Autorediseño: flag wireado de verdad (2026-10-06):** `SELF_REDESIGN_ENABLED` era un flag
  MUERTO (solo en config.py). Ahora está conectado en `selfrepair_propose_fix`: OFF = no puede
  ni proponer; ON = propone, pero aplicar sigue necesitando confirmación por proposal_id + las
  líneas rojas nunca se tocan. Damian lo quiere **siempre ON** (`SELF_REDESIGN_ENABLED=true`).
  Tests: test_selfrepair_gate. **Proactivo (pedido de Damian 2026-10-06):** se cambió el system
  prompt + la descripción de la tool para que Raphael proponga mejoras a su propio código por
  iniciativa propia (selectivo, solo cosas concretas), sin esperar a que se lo pidan. Aplicar sigue
  necesitando confirmación por proposal_id.
- **Router de dificultad del chat (2026-10-06, CONSTRUIDO, apagado por pedido):**
  `app/harness/difficulty_router.py` (puro, `classify(text)->tier` por heurística: keywords de
  complejidad + largo). Wireado en `testmode.chat_client_and_model` (via `_last_user_text` en
  agent.py): si `DIFFICULTY_ROUTER_ENABLED=true` y NO estás en modo prueba, el chat escala a
  Claude (tier 3 Sonnet / tier 4 Opus) solo cuando la tarea lo amerita; lo simple queda free.
  Default **OFF** (el "botón" es `DIFFICULTY_ROUTER_ENABLED`). En modo prueba no aplica (todo free).
  Tests: test_difficulty_router.
- **Jobs de fondo prendidos (2026-10-06):** `PLAYLIST_WATCH_URL` seteada (ingesta auto cada 15min
  tras bajarlo de 3), `CONSOLIDATION_ENABLED=true` (cada 24h, corre con modelo local por
  privacidad), `CURIOSITY_ENABLED=true`. Todo requiere reiniciar el backend.
- **Espejado del chat en vivo PC↔celular (2026-10-06, CONSTRUIDO):** lo que se escribe en el
  celular aparece en la PC al instante y viceversa, vía push por WebSocket (no al refrescar).
  TRES partes:
  * **Backend:** conversación compartida `"default"`; `app/chat_link.py` (registry + broadcast de
    suscriptores, testeado); `GET /api/history` (historial mostrable) + `WS /ws/chat` (suscripción
    + re-emisión de cada turno) en main.py; hook de broadcast en `/api/chat`; `client_id` en
    ChatRequest + `ChatMirrorMessage`/`HistoryResponse` en models; `agent.get_display_history`.
    Dedup: el backend saltea al `origin` (el que lo mandó ya lo mostró por HTTP). Tests:
    test_chat_link, test_display_history.
  * **Tray (PC):** `ui/chat_view.py` abre un `QWebSocket` (nativo PySide6) a /ws/chat, se suscribe
    como `client_id="tray-pc"`, y muestra los turnos que llegan del celular. Manda `client_id` en
    el POST. Config `WS_CHAT_URL`/`CLIENT_ID`/`SHARED_CONVERSATION_ID`. Compila.
  * **Android:** `ChatMirrorClient.kt` (WebSocket OkHttp a /ws/chat, mismo patrón que
    PhoneLinkService), wireado en `ChatViewModel` (+ carga de historial al abrir); `ensureClientId()`
    y conversación fija `"default"` en SettingsRepository; `client_id` en ChatRequest; `GET history`
    en BackendApi. **NO compilado (sin SDK en el entorno) — se prueba al rebuild/redeploy; puede
    necesitar una iteración de build.** OJO: el celular pasa a la conversación "default", así que sus
    chats viejos (bajo el UUID anterior) no se muestran más (siguen en el backend, no se borran).
  * **A cargo de Damian:** reiniciar backend; conectar celular por USB y correr `deploy.ps1`.
- **App celular: avatar de estado + rebrand a Raphael (2026-10-07):** idea del propio Raphael (se le
  preguntó cómo querría que fuera su app). (1) `RaphaelAvatar` en `ChatScreen.kt`: orbe dibujado con
  Canvas que "respira" lento cuando está inactivo y más rápido/brillante mientras piensa
  (`thinking=isSending`). Un estado "actuando" distinto necesitaría streaming de tool-events (futuro).
  (2) Rebrand "Jarvis"→"Raphael" en TODO el texto visible del app (chat, Configuración, notificaciones,
  mensajes de error, app_name="Raphael Remote"), PROTEGIENDO "hey Jarvis" (wake word real que detecta
  el modelo openWakeWord — cambiarla rompería la voz) y los identificadores de clase
  (JarvisAccessibilityService, package com.jarvisremote.app). NO compilado acá; se prueba al redeploy.
- **CENTRO DE MANDO integrado al harness (2026-10-11):** el panel de brigadas ya no es un HTML
  suelto — lo SIRVE el backend y se alimenta de actividad REAL. Partes:
  * `app/mission_control.py` — estado en vivo de las 9 brigadas + broadcaster + mapa tool→brigada
    (`TOOL_BRIGADE`) + `report()`/`report_tool()`. Tests: test_mission_control.
  * `main.py` — `GET /centro-de-mando` (sirve el HTML de docs/raphael), `GET /api/mission-control/state`,
    `WS /ws/mission-control` (snapshot inicial + eventos en vivo). SIN auth (solo-lectura, uso local;
    cerrar con token = pendiente).
  * `agent.py` — cada tool_call reporta a su brigada (enciende Seguridad/Memoria/Ingesta/Ops/etc. en vivo
    durante el trabajo real; Seguridad alterna ⚔️Ataque/🛡️Defensa según sea pentest o auditoría).
  * `playlist_watcher.py` — reporta a la brigada Ingesta cada corrida (actividad de fondo sin chat).
  * El HTML (`docs/raphael/centro-de-mando-raphael.html`): si lo sirve el backend (http) usa la data en
    vivo por WebSocket; si se abre como archivo (file://) cae a la simulación. Mismo archivo, dos modos.
  * **En la TRAY-APP (2026-10-11):** nueva pestaña "🎯 Centro de Mando" en el menú del orbe
    (`ui/mission_control_view.py` = QWebEngineView que carga la URL del backend, mismo patrón que el
    grafo 3D; wireada en `ui/main_window.py` y `ui/orb.py`). Muestra el panel EN VIVO dentro de la app.
  * **A cargo de Damian:** reiniciar el BACKEND (para las rutas) y la TRAY-APP (para la pestaña nueva);
    después, desde el orbe → "Centro de Mando". O abrir `http://localhost:8000/centro-de-mando` en el navegador.
  * Pendiente (fácil): wire de fondo de consolidación→Memoria, curiosidad→Memoria, malware→Antimalware;
    eventos del orquestador maestro (Opus) coordinando; token de auth para el panel.
- **PENDIENTE:** idea a futuro de Damian: biblioteca vertical servida por MCP (§7 spec).
- **Nota:** todo esto es sobre el working tree con los cambios sin commitear de antes;
  suma 3 módulos nuevos + 3 tests + edits en `spreading`/`obsidian.py`/`skills.py`.
  Verificado por lógica (sandbox no puede importar por `win32crypt`); los 16 asserts de
  core pasan. Commitealo vos en PowerShell.

---

## Sesión 2026-09-29 — lo más reciente (leé esto primero)

Sesión larga con Claude (remoto). Todo commiteado en la rama `opt/system-prompt-ablacion`
(commits `5bb6c93` + `6b68e68`); **sin mergear a master todavía**.

**1. Optimización de prompts (ablación) — aplicando el video "Borra todos tus skills":**
- `SYSTEM_PROMPT` −80% (3.514→708 palabras), `CORE_PROMPT` + 6 fragmentos de skills −65%
  (3.271→1.150). Cada gate de seguridad conservado (regla de las 3R). Detrás de flags
  `SYSTEM_PROMPT_VARIANT` y `SKILLS_PROMPT_VARIANT` (default `full` = sin cambios).
- Doc: `docs/ABLACION-system-prompt.md` (clasificación, cómo medir el A/B, nota de que
  el slim rinde con cerebro fuerte y el `full` quizás con el local 8B).
- `CLAUDE.md` ganó un **TL;DR operativo** arriba (referencia detallada intacta).
- **PENDIENTE:** medir el A/B (`=slim` en `.env`, reiniciar, correr tareas).

**2. Memoria episódica (Fase 1+2) — nuevo módulo `backend/app/memory/`:**
- Continuidad autobiográfica: captura automática al cierre de turno + recall automático
  (últimas 24h + salientes), store firmado (Ed25519+DPAPI, reusa `investigation`),
  espejo en el vault. Flags `EPISODIC_MEMORY_*` (prendido por default, destilado LLM off).
- Spec: `docs/SPEC-memoria-episodica.md`. Tools: `memoria_recordar/listar/corregir/olvidar/verificar`.

**3. `web_get` — capa de navegación de agente** (`backend/app/tools/web_get.py`):
- Tool autoescalante (fast→stealth→dynamic→proxy) + representación compacta + cache
  versionado + custodia de credenciales/login (allowlist + DPAPI). Spec:
  `docs/SPEC-capa-navegacion-de-agente.md`.
- **PENDIENTE:** activar en la PC (`pip install scrapling` + `.\.venv\Scripts\scrapling.exe install`).

**4. Lookups OSINT** (`backend/app/tools/osint_lookups.py`): `ip_geolocate` + `crypto_address_trace`
(inspirados en Horus/6abd, reimplementados — Horus es GPL, no se copió código). En el skill `datos_externos`.

**5. Trading harness (Fede Esses / IFVG):** `backend/app/trading/` (engine/signals/backtest) +
`backend/app/harness/trading_brigade.py` + router. Pestaña de trading en la tray. Backtest anda.

**6. Escuadrón de drones (diseño):** specs + modelos 3D paramétricos + planos de fabricación
en `Desktop/Damian/Proyectos/` (`NanoHornet-3D/`, `Escuadron-3D/`). No es parte del repo.
Specs de referencia: `docs/SPEC-escuadron-drones.md`.

**7. Instagram:** cuenta `@raphaelseguridad` creada; primer post **pendiente de publicar**.

**8. Ruteo de modelos por tarea (2026-09-30, SIN commitear todavía):**
- **Cerebro cambiado a `anthropic/claude-sonnet-5.5`** vía OpenRouter (`.env`, línea
  `LMSTUDIO_MODEL`). ⚠️ El selector de la tray lo pisa — no lo toques si usás Sonnet.
- **Planner Sonnet→Opus** (`app/tools/planner.py`, tool `planear_con_opus` en CORE): el
  loop delega planificación dura a Opus 5.5 (config `PLANNER_*`).
- **Ruteo por tiers reconciliado:** `routing.py` mapa 0/1/2/3 (0 determinista · 1 local ·
  2 Sonnet · 3 Opus) + `model_registry.endpoint_for_model` (cloud→OpenRouter, local→Ollama
  `LOCAL_MODEL_BASE_URL`) + `candidates_for` (override explícito primero, después fallback
  por tier). Enchufado en las estaciones LLM de auditoría (E3/E5/E6) con fallback en cascada.
- **Persistencia del registro de modelos** (`MODEL_REGISTRY_PATH`, sin escribir keys).
- **T8 · Lectura Esses** en la brigada de trading (`trading_brigade.py`, tier 2): el LLM lee
  los datos deterministas de T1-T7 y da lectura discrecional con las reglas de Fede Esses;
  best-effort (nunca bloquea la señal).
- **Retirados opencode y cloud_expert** (Gemini): con Sonnet 5.5 quedaron redundantes;
  des-registrados (archivos en disco dormidos), skill `code_delegation` eliminado.
- Docs: `docs/ABLACION-system-prompt.md` (incluye la ablación de prompts).

**Cabos sueltos de la sesión:** **commitear el ruteo de modelos** (working tree sucio) ·
activar web_get · medir A/B de prompts (`*_VARIANT=slim`) + probar Sonnet · publicar IG ·
recargar OpenRouter + reindexar vault → ingestar ~3 videos que faltan · decidir el merge
de `opt/system-prompt-ablacion` a master · seguir con los Tests A/B/C de auditoría (alimentan
la primera venta).

---

## Sesión 2026-09-04 — histórica

**Bitácora completa de la sesión** en `docs/BITACORA-SESION-2026-09-04.md` (ingesta
YouTube resuelta con yt-dlp + validada remoto; memoria persistente; rediseño de UI a
orbe flotante "Raphael"; robustez de arranque anti-10048; y el gran avance:
**informe de auditoría client-facing + triage automático de falsos positivos**,
validado en 3 repos — pygoat/flask-realworld/studybud). Roadmap de mejoras en
`docs/ROADMAP-MEJORAS-RAPHAEL.md`. **Conocimiento de diseño** (la brigada, retrieval,
model routing, precisión vs cobertura, "la IA redacta/vos verificás") en el vault:
`obsidian_vault/jarvis/diseno-de-raphael-brigada-retrieval-routing-y-precision-de-auditoria.md`.
Cola: verificar tray → Test C (Raphael se audita a sí mismo) → QW-3 (citar fuentes) →
**primera venta** (Gig de Fiverr ya publicado).

---

## Sesión 2026-08-30 (histórica)

**Cerebro cambiado a DeepSeek V4 Pro** vía OpenRouter (pay-as-you-go). En `backend/.env`:
`LMSTUDIO_BASE_URL=https://openrouter.ai/api/v1`, `LMSTUDIO_MODEL=deepseek/deepseek-v4-pro-0813`,
`LLM_API_KEY=<key de OpenRouter>`. Backup de la config local (Ollama / `jarvis-text-v2`) en
`backend/.env.bak-openrouter`. ⚠️ **El selector de modelo de la tray-app PISA esta config**
(la vuelve a `jarvis-text-v2`) — si usás DeepSeek, no toques el selector (bug anotado en `TABLA.md`).

**Costo bajo control:** el prompt pesa ~30k tokens (system prompt + 103 tools por llamada),
pero DeepSeek cachea automático (~99% cache-hit una vez caliente) → ~US$0.0008 por pedido simple.
Se agregó instrumentación de tokens/costo por llamada en `agent.py` (`_log_llm_usage` → `general.log`).
Optimización opcional pendiente: mandar menos de 103 tools por llamada.

**Sistema de cocina (cómo se organiza el trabajo):** `COMANDAS.md` (riel de tareas; 4 pasos:
entra comanda → tabla → fuego → emplatado; **UNA en el fuego a la vez**), `TABLA.md` (ideas crudas
sin confirmar), `recetario/` (servicios/procedimientos; ⭐ receta 01 = Blindaje PyME), `PROVEEDORES.md`,
`docs/LA-BRIGADA.md`, `docs/raphael/` (documentación completa del proyecto).

**Prioridad ACTUAL: primera venta (Blindaje PyME).** El servicio que se vende AHORA es la versión
**LITE** (backups + Defender full/Tamper Protection + SmartScreen + updates de Windows +
contraseñas/wifi), entregable en un día — **NO** la receta 01 "gourmet" (kernel-grade, semanas).
Herramienta de venta: `Escritorio/Blindaje-PyME-Checklist-15min.md` (chequeo con permiso → informe → precio).

**Ingesta YouTube:** 49/52 videos de la playlist "Info para Jarvis" ingeridos al vault con
discernimiento de relevancia; fix de traducción (pt→es/en) agregado; faltan ~3 por bloqueo temporal
de IP de YouTube (re-run cuando levante).

---

## Índice — dónde vive cada cosa

- **Qué es el proyecto / arquitectura / modelos / gates de seguridad:** `CLAUDE.md`
- **Estado y prioridades:** este archivo (`ESTADO.md`)
- **Riel de tareas (qué hacer y en qué orden):** `COMANDAS.md` · **Ideas crudas:** `TABLA.md`
- **Servicios y procedimientos vendibles:** `recetario/` · **Proveedores/ingredientes:** `PROVEEDORES.md`
- **Brigada de agentes:** `docs/LA-BRIGADA.md` · **Docs completas del proyecto:** `docs/raphael/`
- **Base de conocimiento (notas de video, seguridad, negocio):** `backend/obsidian_vault/jarvis/`
- **Diseños de laboratorio y defensa:** `lab/` (cyber range, defensa kernel-grade, orquestación remota)
- **Config y secretos:** `backend/.env` (**NO se commitea** — el repo es PÚBLICO)
- ⚠️ **Material PERSONAL de Damian (proyecto Fénix, análisis psicológicos) vive en un vault APARTE,
  `C:\Users\dam\Vault-Fenix` — NO es parte de este proyecto, NO va al repo público ni al contexto de Raphael.**

---

## En qué se estaba trabajando (últimas sesiones)

El trabajo reciente (ver últimos ~15 commits) fue una tanda grande de features
que quedaron integradas y commiteadas:

- **Módulo de protección antimalware** (`backend/app/malware/`, spec 2026-08-16):
  YARA + ClamAV + heurística conductual + FIM + monitor del proceso propio +
  cuarentena reversible. Integrado al agente y con tests. Sysmon quedó como capa
  experimental **apagada** por default.
- **Completado de formularios web** con credential store cifrado (DPAPI) +
  `shell_exec`, con dry-run + preview obligatorio antes de cualquier submit.
  - **[2026-08-17] Gate de consentimiento del submit ahora con enforcement a
    nivel código** (antes dependía SOLO del prompt del modelo). `browser_preview_submit`
    con `confirm=false` emite un **preview token de un solo uso** (`pv-xxxxxxxx`)
    atado a `submit_selector` + URL de la página + timestamp, guardado en un store
    en memoria con TTL corto (`FORM_PREVIEW_TOKEN_TTL_SECONDS`, default 300s).
    `confirm=true` ahora EXIGE el nuevo parámetro `preview_token`: sin él, o con uno
    de otro formulario/página, vencido o ya usado, el submit se **rechaza sin hacer
    click**. Mismo espíritu que el `proposal_id` de `selfrepair`. Archivos:
    `app/tools/web_forms.py` (store + validación), `app/config.py` (TTL),
    `app/skills.py` (prompt actualizado), `tests/test_web_forms.py` (cobertura del
    gate). Tests de web_forms en verde (17/17).
- **Pentesting activo**: sqlmap, OWASP ZAP y captura de paquetes (scapy) sumados
  a nmap, todos detrás del gate único `authorized_targets.yaml`.
- **Pipeline de auto-reparación** (`selfrepair/`) con gate de aprobación manual,
  **testing automático** (detección/runner/store) y **escaneo de seguridad/calidad**
  con modelo de hallazgos unificado + triage + benchmark OWASP.
- **Cliente cloud** (Google AI / Gemini Flash) + tools `cloud_expert_*` y
  `opencode_run_task`.
- **~70 notas nuevas en el vault** de conocimiento (`backend/obsidian_vault/jarvis/`).
- **Modelo de chat:** histórico → local `jarvis-text-v2` (Qwen3-30B) → `gpt-oss:120b-cloud`
  (Ollama cloud, pegaba límite semanal) → **HOY: `deepseek/deepseek-v4-pro-0813` vía OpenRouter**
  (ver la sección "Sesión 2026-08-30" arriba y la sección de modelos en `CLAUDE.md`).

## Lo más reciente y todavía sin cerrar

Las últimas notas del vault (`arquitectura-jarvis`, 2026-08-16/17) documentan una
**decisión de diseño pendiente que necesita el input de Damian**, no código:

### Sandboxing en contenedor para `pc_run_command` y `browser` (PROPUESTO, no implementado)

Nota completa:
`backend/obsidian_vault/jarvis/propuesta-sandboxing-en-contenedor-para-pc-run-command-y-browser.md`.

Contexto: `pc_run_command` es una blocklist de texto, no un sandbox real, y
`FS_ALLOWED_ROOT` por default es el **HOME entero**. La propuesta acota el radio
de daño metiendo `pc_run_command` + `browser_*` en un container Linux (Docker),
**sin tocar** `desktop_*` (necesita GUI de Windows) ni las tools de pentesting
(no pasan por `shell_exec`).

Estado de la infraestructura (verificado 2026-08-16):
- **Docker: NO instalado.** WSL2: sí (prerrequisito listo). Falta un solo paso:
  Damian instala Docker Desktop (MSI + UAC, no automatizable por Jarvis).

**Mitigación barata pendiente (cero riesgo, no requiere Docker):** achicar
`FS_ALLOWED_ROOT` en `backend/.env` de `Path.home()` a solo
`C:\Users\dam\Documents\JarvisRemote` + carpetas de proyectos que Jarvis cree.
Cambio de una línea que ya reduce muchísimo la superficie de ataque.

**Dos decisiones de arquitectura que Damian tiene que tomar antes de implementar:**
1. ¿El backend FastAPI entero corre dentro del container (más simple de razonar,
   pero complica `desktop_*`/`phone_*` que sí o sí van en el host) o solo un
   container "worker" que el backend en host controla vía `docker exec`?
2. ¿Vale el costo de RAM/CPU de Docker Desktop siempre corriendo (la PC ya tuvo
   apagados por consumo) o el container se levanta solo bajo demanda?

## Cyber range (en armado)

Se está montando el **laboratorio de pentesting aislado** para probar los módulos
ofensivos y de detección de Jarvis (diseño en `lab/CYBER-RANGE-DESIGN.md` +
`lab/DETECCION-ESTRES-NOCTURNO.md`). **Guía de continuación:
`lab/RETOMAR-LAB.md`** — leela para retomar sin perder el hilo.

Estado actual (2026-08-17):

- **VirtualBox 7.2.14** + Extension Pack instalados (se fue con el plan B del
  diseño; VMware era la recomendación, pero VBox es válido — sin auto-snapshots,
  se hacen a mano).
- **Kali 2026.2** importada: Adaptador 1 = Red interna "labnet" (ataque, aislada),
  Adaptador 2 = NAT (solo updates, apagar en ataques).
- **Metasploitable 2** creada con `Metasploitable.vmdk`, Adaptador 1 = labnet
  (una sola placa, sin NAT).
- **Servidor DHCP en labnet** (`VBoxManage dhcpserver add`): rango
  10.13.37.100–200, server-ip 10.13.37.1, máscara 255.255.255.0. Coincide con el
  `10.13.37.0/24` del diseño.
- **Quedó a mitad:** Metasploitable booteando; falta loguear (msfadmin/msfadmin),
  sacar IP con `ifconfig`, encender Kali (kali/kali) y verificar conectividad +
  tomar snapshots BASE. Ver checklist en `lab/RETOMAR-LAB.md` §2.

Pendientes destacados del range: instalar Docker Desktop (DVWA/Juice Shop/Caldera),
Atomic Red Team + MITRE Caldera v5, agregar `10.13.37.0/24` a
`authorized_targets.yaml` a mano antes de que Jarvis toque los blancos, y
registrar Nessus Essentials en tenable.com (Damian, desde el celular).

## Orquestación remota (diseño nuevo, sin implementar)

**Diseño: `lab/ORQUESTACION-REMOTA-DESIGN.md`** (2026-08-17, solo diseño, no toca
código). Cómo Damian controla a Jarvis **desde el celular estando fuera de casa**
para orquestar el cyber range (abrir/manejar VMs, lanzar pentest/detección en
labnet, reportar) sin debilitar ningún gate existente. Decisiones clave:

- **Canal remoto solo por Tailscale** (nada expuesto a internet, router sin
  puertos abiertos): backend atado a la interfaz Tailscale vía `tailscale serve`
  (o bind a la IP `100.x`), grant de tailnet celular↔PC solo-ese-puerto.
- **Auth por dispositivo** (token/JWT) guardado con **DPAPI** (reusa el patrón de
  `forms/credential_store.py` e `investigation/keys.py`), revocable/rotable — no
  el `API_KEY` único en claro de hoy.
- **Tools nuevas (spec, no código):** `vm_control` (wrapper de `VBoxManage` con
  allow-list de VMs del lab + audit firmado) y `ssh_guest` (SSH a Kali por una
  interfaz de gestión, blancos aún restringidos por `authorized_targets.yaml`).
- **Cola de misiones** con estados (encolada→corriendo→necesita-confirmación→
  completada/fallida) y **confirmaciones remotas** para pasos gated, atadas a cada
  paso al estilo `preview_token`/`proposal_id`.
- **Plan por fases** (menor→mayor riesgo): 1) `vm_control` local · 2) endpoint
  autenticado sobre Tailscale · 3) `ssh_guest` · 4) cola de misiones + confirmación
  remota. Requisito físico: PC prendida (opción Wake-on-LAN documentada).

## Defensa "kernel-grade" gratis (diseño nuevo, sin implementar)

**Diseño: `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`** (2026-08-17, solo diseño, no toca
código, no instala nada). Cómo acercar `app/malware/` a un EDR **sin driver propio
ni certificado EV** ($0, riesgo de BSOD nulo). Tesis: **orquestar los componentes
de kernel que Windows ya trae firmados por Microsoft** en vez de escribir código de
kernel. Decisiones clave:

- **Detección (consumir telemetría de kernel):** ETW en tiempo real (pywintrace /
  PythonForWindows), Sysmon (ampliar `sysmon_monitor.py` de Event ID 8/10 a
  1/3/7/11/22, config SwiftOnSecurity), AMSI para fileless, auditoría 4688+cmdline.
  ETW le da al `behavioral_watcher` el **PID+imagen** que hoy le falta para matar al
  proceso que cifra, no solo detectar el patrón.
- **Bloqueo real sin driver propio (confirmado):** Defender **ASR** rules (bloqueo
  en kernel vía `Set-MpPreference`, ej. dump de LSASS), **WDAC** (Code Integrity,
  enforcement antes de cargar en memoria), **AppLocker** (más simple/evadible), y
  **WFP** (filtros de red desde user-mode con `fwpuclnt`, capa ALE, sin driver).
- **Circuito de respuesta:** evento de kernel → correlación → contención (matar
  proceso / cortar red por WFP / cuarentena reversible / snapshot) → `store` firmado
  Ed25519 → nota a Obsidian. Preventivo (ASR/WDAC/AppLocker/WFP pre-cargados) vs.
  contención posterior (detectar→matar siempre deja una ventana).
- **Plan por fases (por esfuerzo):** 1) Sysmon+config+consumo · 2) ETW tiempo real ·
  3) AMSI · 4) enforcement (ASR→AppLocker→WDAC→WFP), **siempre audit mode antes de block**.
- **Checklist de prioridades (por cuánto protege): `lab/DEFENSA-PRIORIDADES.md`**
  (2026-08-17, solo documentación). Complementa al diseño con el orden priorizado
  por protección: 0) Defender full + Tamper Protection (paso cero) · 1) AppLocker→WDAC
  (lo que más protege, más esfuerzo) · 2) ASR · 3) AMSI · 4) Sysmon+ETW (capa sensorial)
  · 5) WFP. Regla transversal: todo lo que bloquea va primero en **modo auditoría**.
- **Límite honesto:** no veta creación de proceso *antes* del hecho de forma
  arbitraria (solo por regla), canal Event Log manipulable, AMSI evadible, rootkits
  no detectables desde el host. Recién ahí valdría un driver firmado.

## Próximos pasos sugeridos

1. **Respaldo remoto**: pushear los 39 commits locales a `origin` (público). No
   se pusheó todavía a la espera de tu OK (ver abajo). Este es el paso más
   urgente para no volver a perder trabajo.
2. **Mitigación barata de sandbox**: achicar `FS_ALLOWED_ROOT` en `backend/.env`
   (independiente de Docker, cero riesgo).
3. **Decidir el enfoque de sandboxing en contenedor** (las 2 preguntas de arriba)
   e instalar Docker Desktop si se aprueba.
4. **Verificar el modelo activo**: confirmar que `gpt-oss:120b-cloud` es el que se
   quiere dejar por default, o volver a `jarvis-text-v2` local. Correr
   `ollama list` en la PC para confirmar qué está realmente instalado (no se pudo
   verificar desde esta sesión, ver nota abajo).
5. Correr la suite de tests (`cd backend && pytest`) para confirmar que todo sigue
   en verde tras la última tanda de features.

## Notas / cabos sueltos

- **`ollama list` no se pudo correr desde esta sesión** (la sesión de la IA corre
  en un sandbox Linux aislado, sin acceso al Ollama de la PC). Los nombres de
  modelos en `CLAUDE.md` salen del código y la config real (`.env`,
  `.env.example`, Modelfiles), no de `ollama list`. Confirmá el modelo local
  instalado corriendo `ollama list` vos mismo.
- **Generación de video/imagen (ComfyUI) apagada** por consumo de energía real de
  la PC (apagados observados). Ver comentario en `app/tools/__init__.py`.
- **Bug de Playwright en esta PC**: el Chromium bundleado no arranca (firma SxS /
  antivirus Reason/RAV) — `browser.py` usa `channel="msedge"` como workaround.

---

## Estado del respaldo remoto

- **Remoto:** `origin` = `https://github.com/damianzupel-commits/JarvisRemote.git`
- **Accesible:** sí (verificado con `git ls-remote`).
- **Visibilidad:** **PÚBLICO** (confirmado en GitHub el 2026-08-17).
- **Pusheado:** `master` está **al día con `origin/master`** (últimos respaldos:
  2026-08-30, commits `f1017f2` → `e83c99b`). El respaldo remoto ya no es un pendiente.

---

## Protocolo de cierre de sesión

**Al terminar cualquier sesión de trabajo en este repo:**

1. Actualizá este `ESTADO.md`: fecha, último commit, en qué quedaste, qué quedó a
   medias, próximos pasos.
2. Commiteá los cambios con un mensaje `docs:` (ej.
   `docs: actualiza ESTADO tras <lo que hiciste>`).
3. Si corresponde y Damian lo autorizó, pusheá a `origin` para no perder trabajo.
   Recordá que el repo es **público**: no commitees secretos.
