# RESUMEN MAESTRO — Raphael (JarvisRemote)

> **Qué es este documento:** la foto completa de Raphael en una sola lectura —
> qué es, cómo está armado, qué sabe hacer, con qué gates, en qué estado, y hacia
> dónde va. Es un mapa de alto nivel: para el detalle módulo por módulo está la
> serie `docs/raphael/00-INDICE.md` … `15-configuracion.md`; para el estado
> operativo del día, `ESTADO.md`; para las reglas estructurales, `CLAUDE.md`.
>
> Creado el 2026-10-05 y actualizado el mismo día tras **releer todos los archivos
> del repo relacionados con Raphael**: CLAUDE.md, ESTADO.md, INFORME_COMPLETO.md, los
> specs de `docs/`, la serie `docs/raphael/`, `vision/`, `lab/`, `recetario/`,
> README/QUICKSTART, la memoria del proyecto, el estado de git y el propio código.
> Donde algo no está confirmado en vivo o está apagado/dormido, se dice.

---

## 1. Qué es Raphael

**Raphael** es el nombre del agente; **JarvisRemote** es el proyecto/repo
(`C:\Users\dam\Documents\JarvisRemote`, remoto **público** en
github.com/damianzupel-commits/JarvisRemote). Nació como herramienta de
**auditoría de código / pentesting manejada por un LLM** y creció hasta ser un
**asistente personal de propósito amplio** que ejecuta acciones reales sobre la
PC y el celular: controla la pantalla, corre shell real, investiga enlaces y
evidencia forense, protege contra malware, audita y repara código, hace
pentesting, completa formularios, ingiere conocimiento de la web/YouTube y
analiza mercados para trading.

El nombre viene de **Tensura** (anime que le gusta a Damian): la habilidad "Gran
Sabio / Raphael" es el norte del proyecto — un asistente que percibe, recuerda,
razona y, con el tiempo, avisa de forma proactiva (hoja de ruta por etapas 0→6,
ver `vision/HACIA-RAPHAEL.md`).

**Filosofía de diseño recurrente** (aparece en todo el código):
- **Acciones reales sobre la PC, no simuladas.** Si una tool dice que hace algo,
  lo hace de verdad.
- **"Sin fricción" por default**, a pedido explícito de Damian: cada capacidad
  invasiva viene prendida.
- **Pero con gates donde el daño sería irreversible** (ver §9). El patrón
  universal es dry-run → confirmación explícita.
- **Flags para apagar cada capacidad invasiva sin tocar código.**
- **"La IA redacta, vos verificás"** — y a futuro, "invertir la relación": que
  Raphael haga el trabajo pesado y la supervisión humana corrija.

**Nombre: producto vs código.** "Raphael" es el **nombre de producto**; en el
**código, el nombre interno sigue siendo "jarvis"** — módulos, loggers
(`jarvis.agent`), variables de entorno (`LMSTUDIO_MODEL`), prompts (dicen literal
"Sos Jarvis…") y tools (`jarvis_reflect`). Cuando este doc dice "Raphael" habla del
sistema; cuando cita un identificador, ese es el nombre real a buscar en el repo.

**Proyecto primo: co-host de stream.** En `proyectos/co-host-stream/` vive un
proyecto SEPARADO (su propio repo/proceso): un co-host de stream con IA que mira la
pantalla en vivo (modelo de visión) y comenta con personalidad. Reusa patrones de
Raphael pero no es Raphael. Receta: `recetario/07-cohost-stream.md`.

**No confundir** (fuente recurrente de errores):
- ESTE repo (`JarvisRemote`) = el proyecto activo.
- `C:\Users\dam\cerebro-fenix\_Jarvis-Local` = prototipo VIEJO de asistente de
  voz, **congelado el 2026-07-20**. No copiar de ahí.
- `C:\Users\dam\Vault-Fenix` = vault unificado que Raphael indexa (técnico +
  estudio + personal). `backend/obsidian_vault/` es OTRO vault distinto (el de
  seguridad/conocimiento histórico).

---

## 2. Los tres componentes

| Componente | Stack | Rol |
|---|---|---|
| **`backend/`** | Python + FastAPI | El cerebro. Loop del agente (tool-calling), ~115 tools, routers HTTP (`codebase`/`obsidian`/`investigation`), WebSocket del celular. Entrypoint `run.py`, default `:8000`. |
| **`tray-app/`** | Python + pystray + PySide6 | Ventana de escritorio (pestañas Codebase/Obsidian, tema oscuro). Administra el backend como subproceso, selector de modelo por tiers, escucha de voz continua. |
| **`android-app/`** | Kotlin + Jetpack Compose | Chat + foreground service con WebSocket saliente hacia el backend. Control de pantalla (Accessibility Service), shell real (Termux), cámara. En desarrollo; no hace falta para la auditoría de código. |

Nada se expone a internet: el backend escucha en la IP privada de Tailscale (o
LAN) y toda request exige un Bearer token (`API_KEY` en `.env`). TLS está
preparado pero **apagado** (`TLS_ENABLED=false`): el tráfico va en claro salvo
que ya viaje sobre Tailscale (cifrado por WireGuard).

---

## 3. El cerebro: modelos y ruteo

**Hay un solo modelo de chat/agente por vez**, definido por `LMSTUDIO_MODEL` en
`backend/.env` (el nombre `LMSTUDIO_*` es histórico — hoy NO implica LM Studio).
Más un modelo de **embeddings** aparte, más modelos puntuales que usan ciertas
tools.

**Historia del cerebro** (por qué cambió tantas veces): local `jarvis-text-v2`
(Qwen3-30B-A3B MoE) → `gpt-oss:120b-cloud` (nube de Ollama, pegaba límite
semanal) → `deepseek/deepseek-v4-pro-0813` vía OpenRouter → **`anthropic/claude-
sonnet-5.5` vía OpenRouter** (decisión 2026-09-30, calidad de tool-calling).
⚠️ El **selector de la tray pisa el `.env`** y lo vuelve a un `jarvis-text-*`
local — si usás un modelo cloud, no toques el selector.

> **Nota de estado (2026-10-04):** el `.env` está TEMPORALMENTE en
> `jarvis-text-v2` local para ingerir videos sin gastar OpenRouter. Hay que
> volver a Sonnet cuando termine la ingesta (líneas de revert comentadas en el
> `.env`). El modelo local es más flojo para disparar tools de forma confiable.

**Modelos locales (alternativa):** `jarvis-text-v2` (Qwen3-30B-A3B, tier
Medio/Hard), `jarvis-text-lite` (qwen3:8b, tier Lite), `jarvis-text-hard` (alias
de v2). `jarvis-text` v1 tiene bug de tool-calling: **no usar**. Se arman con
`install.ps1` usando Modelfiles con el template de tool-calling corregido.

**Embeddings (local, server aparte):** `text-embedding-nomic-embed-text-v1.5`
servido por **LM Studio real** en `:1234` (a propósito NO reusa el endpoint de
chat; Ollama en :11434 no tiene modelo de embeddings cargado). Si ese server
está caído, la búsqueda del vault degrada a keyword y lo dice en voz alta.

**Ruteo por tiers** (2026-09-30, `app/harness/routing.py` + `model_registry.py`):

| Tier | Para qué | Modelo |
|---|---|---|
| **0** | Determinista, sin modelo (cómputo puro) | — |
| **1** | Barato/repetitivo | local `jarvis-text-v2` / DeepSeek |
| **2** | Razonamiento principal (hablar, auditar, leer) | **Sonnet 5.5** |
| **3** | Planificación dura | **Opus 5.5** (tool `planear_con_opus`) |

`endpoint_for_model()` clasifica el slug (con "/" → OpenRouter global; si no →
Ollama local). `candidates_for(station, tier)` usa el override explícito primero
y después cae por tier (cascada de fallback si uno falla). El registro de
modelos persiste a disco (`MODEL_REGISTRY_PATH`, **sin escribir las keys**).
Se **retiraron** `opencode` y `cloud_expert` (Gemini): con Sonnet quedaron
redundantes (archivos dormidos en disco, skill `code_delegation` eliminado).

**Preferencia de Damian:** usar Opus 5 cuando se puede, calidad sobre costo.

---

## 4. El loop del agente y los skills

`app/agent.py` corre el loop clásico: manda mensajes + schemas de tools al LLM,
ejecuta las tool calls que pide, devuelve resultados, repite hasta texto final o
`MAX_AGENT_ITERATIONS` (30; 50 para tareas de escritura de código). El historial
se poda (`_trim_history`) y los resultados de tools se capan (`_cap_tool_result`)
para no reventar el presupuesto de contexto (bugs reales de "context exceeded").

**Skills (`app/skills.py`):** el agente NO ve las ~115 tools siempre. Ve
`CORE_TOOL_NAMES` (lo que tiene que estar disponible siempre: fs, reflect,
obsidian search/save, recall de memoria, planner, grabación) **más** las tools
de los skills que matchean el mensaje por keywords (`classify()`). Cada skill
agrupa tools + un fragmento de prompt. Skills actuales: `investigation`,
`security_audit`, `pentesting`, `malware_protection`, `desktop_control`,
`web_forms`, `phone_control`, `datos_externos`, `memoria`, **`ingesta`** (nuevo,
2026-10-04). Hay una **ablación de prompts** (variantes `slim`/`full` detrás de
flags `SYSTEM_PROMPT_VARIANT`/`SKILLS_PROMPT_VARIANT`; `full` = sin cambios) que
bajó el system prompt −80% conservando cada gate (ver `docs/ABLACION-system-prompt.md`).

> ⚠️ **Gate de diseño:** una tool registrada pero NO mapeada a CORE ni a ningún
> skill **el agente no la ve** (solo es accesible por CLI). Fue exactamente el
> bug de la ingesta de videos (ver §13). Un test (`tests/test_skills.py`) exige
> que toda tool registrada esté en CORE o en exactamente un skill.

---

## 5. Las tools (~115 activas) por categoría

**Por los números** (medición del 2026-09-25, `docs/ANALISIS-CODIGO-RAPHAEL.md`):
backend ~26.500 líneas en 19 paquetes; **104 tools** entonces (hoy ~119 registradas
tras las de memoria/ingesta de octubre); suite de **~112 archivos de test, ~21.600
líneas** (casi 1:1 con el código de la app); `agent.py` ~1.400 líneas; solo 3
marcadores TODO/FIXME en todo el repo. Código limpio y muy testeado.

| Familia | Nº | Qué hacen | Estado |
|---|---|---|---|
| **Investigación forense** (`investigation_*`) | 18 | Casos (cada uno su repo git), ingesta de CSV/chats/logs/imágenes/PDF, grafo de entidades, EXIF, log append-only firmado Ed25519 (DPAPI) | activo |
| **Celular** (`phone_*`) | 13 | tap/swipe/type/read_screen, filesystem SAF, shell Termux, cámara/video | tap/swipe/SAF OK en real; Termux y cámara con errores reportados viejos |
| **Antimalware** (`malware_*`) | 11 | YARA, ClamAV, heurística conductual, FIM, cuarentena reversible | activo |
| **Escritorio** (`desktop_*`) | 10 | mouse/teclado/ventanas (pywinauto/pyautogui) | control total, sin sandbox; no controla ventanas elevadas (UAC) |
| **Navegador** (`browser_*`) | 9 | Playwright vía Edge del sistema (no Chromium, por antivirus) | activo |
| **Filesystem PC** (`fs_*`) | 6 | list/read/write/create/move/delete, sandbox `FS_ALLOWED_ROOT` | activo |
| **Web / datos externos** (`web_*`) | 5 | `web_get` (sensor web autoescalante HTTP→anti-bot→JS→proxy), `web_scrape`, custodia de credenciales + login gated | `web_get` activado 2026-10-04 (Scrapling) |
| **Conocimiento Obsidian** (`obsidian_*`) | 5 | guardar/listar/buscar notas, **búsqueda asociativa (spreading)**, **ingesta web** | activo; spreading/ingesta nuevos |
| **Memoria episódica** (`memoria_*`) | 5 | recordar (CORE) + listar/corregir/olvidar/verificar | activo |
| **Auditoría código** (`security_*`, `quality_*`, `audit_*`, `codebase_*`, `code_*`) | ~13 | escaneo (Semgrep/Bandit/cppcheck/clang-tidy/Trivy/Ruff/mypy), triage, fix+verify, reporte, brigada | activo, validado en 3 repos |
| **Pentesting** (`nmap`, `sqlmap`, `zap`, `packet_*`) | ~5 | recon + inyección SQL + ZAP + captura de paquetes, todo detrás de `authorized_targets.yaml` | activo |
| **Ingesta de conocimiento** (`youtube_*`) | 2 | playlist entera + **video suelto** (nuevo), transcripción→resumen→nota | activo |
| **Grabación** (`recording_*`) | 2 | pantalla (ffmpeg) alrededor de tools de auditoría/fix/test | activo |
| **Otros** | varios | `research_topic`, `planear_con_opus`, `pc_run_command`, `shell_exec`, `jarvis_reflect`, `ocr_document`, `ip_geolocate`, `crypto_address_trace`, `selfrepair_propose_fix` | activo |
| **Generación** (`generate_image`/`generate_video`) | 2 | ComfyUI (Flux/Wan) en GPU | 🔴 **DESACTIVADAS** (apagados físicos de la PC por consumo; ver §10) |
| **Dormidas** (`opencode`, `cloud_expert_*`) | 3 | delegación a OpenCode / Gemini | retiradas (Sonnet las volvió redundantes) |

El detalle tool por tool está en `docs/raphael/03-tools-registro-catalogo.md`.

---

## 6. Los sistemas de memoria

Raphael tiene, en piezas, los **cuatro sistemas de memoria** del cerebro, y
desde 2026-10-04 se le está sumando la **dinámica** que los hace funcionar como
uno solo (spec: `docs/SPEC-estructura-informacional-cerebro.md`).

| Sistema (cerebro) | En Raphael |
|---|---|
| **Semántica** (hechos) | el **vault** Obsidian (embeddings + coseno, keyword de fallback) |
| **Episódica** (autobiográfica) | `app/memory/` — captura al cierre de turno, recall automático, log firmado Ed25519+DPAPI, espejo en el vault (spec `SPEC-memoria-episodica.md`) |
| **De trabajo** (lo de ahora) | el contexto de la conversación |
| **Procedural** (habilidades) | tools + skills + brigadas |

**Dinámicas cerebro-símil (en construcción):**
- **Fase 1 — Spreading activation (HECHA, tier 0 puro):** `app/obsidian/spreading.py`.
  Recupera por asociación: una query activa notas semilla (por coseno) y la
  activación se propaga por los `[[wikilinks]]` del grafo con decaimiento; lo que
  está conectado a varias semillas "emerge" aunque no matchee literal. Tool
  `obsidian_buscar_asociativo`.
- **Fase 2 — Pesos Hebbianos (HECHA, tier 0):** `app/obsidian/hebbian.py`. "Lo
  que se activa junto, se cablea junto": notas usadas juntas fortalecen su arista
  y el spreading propaga más fuerte por ahí. El grafo se auto-organiza con el uso.
  Falta la reconsolidación de *contenido* (reescribir la nota con lo aprendido).
- **Ingesta web directa (HECHA):** `app/obsidian/web_ingest.py` (tool
  `obsidian_ingerir_web`). URL → fetch (`web_get`) → chunk → embeber (nomic) →
  indexar en el vault con provenance. Sin modelo de chat (tier 0 + embeddings):
  barato, idempotente. Es la "biblioteca para IA a escala personal".
- **Pendiente:** Fase 3 (job de consolidación "sueño", tier 1 local) y Fase 4
  (olvido adaptativo).

**Fundamento científico** (del material que aportó Damian): Complementary
Learning Systems (McClelland et al. 1995), spreading activation (Collins &
Loftus 1975), memoria reconstructiva y confabulación (Bartlett, Loftus), Hebb/
LTP, y anclajes filosóficos (Wittgenstein: el significado viene del uso; Peirce:
abducción; Gödel: humildad de diseño). Idea a futuro de Damian: una biblioteca
vertical servida por **MCP** (ver §7 del spec de estructura informacional).

También existe `jarvis_reflect` (memoria de reflexión vieja, JSONL append-only).

---

## 7. El harness multiagente / las brigadas

`app/harness/` es la capa de orquestación multiagente (spec
`docs/SPEC-HARNESS-MULTIAGENTE.md`, metáfora de cocina en `docs/LA-BRIGADA.md`):
`orchestrator.py`, `blackboard.py` (memoria compartida tipo pizarra), `a2a.py`
(agente-a-agente), `contracts.py`, `routing.py` + `model_registry.py` (ruteo de
§3), `worktrees.py` (git worktrees aislados), y dos brigadas concretas:

- **Brigada de auditoría (`audit_brigade.py`):** estaciones (E1…E6) que encadenan
  escaneo → triage → fix → verificación. Las estaciones LLM (E3/E5/E6) corren por
  candidatos con fallback en cascada por tier.
- **Brigada de trading (`trading_brigade.py`):** T1–T7 deterministas + **T8
  "Lectura Esses"** (tier 2): el LLM lee los datos deterministas de T1–T7 y da una
  lectura discrecional con las **reglas de Fede Esses** (IFVG). Best-effort: nunca
  bloquea la señal. El motor de trading propio vive en `app/trading/` (`engine.py`,
  `signals.py`, `backtest.py`).

---

## 8. Capacidades por dominio

- **Auditoría de código** (`security/`+`quality/`+`findings/`+`codeedit/`+
  `selfrepair/`+`testing/`): indexa cualquier proyecto en un grafo (tree-sitter),
  corre escáneres reales (Semgrep, Bandit, cppcheck, clang-tidy, Trivy = seguridad;
  Ruff/mypy = calidad), triage de falsos positivos, fixes reversibles (cada uno su
  commit), testing automático (cierra el gap "compiló ≠ funciona"), benchmark OWASP,
  e **informe client-facing** (validado en pygoat/flask-realworld/studybud). Es lo
  monetizable. `selfrepair/` propone fixes al **propio** código de Raphael (dry-run
  libre; aplicar exige `proposal_id` que confirma Damian).
- **Antimalware** (`malware/`): YARA + ClamAV + heurística conductual (watchdog/
  psutil) + FIM + monitor del proceso propio + Sysmon (experimental, apagado).
  Escaneo diario en background + on-access de Descargas/Escritorio/Temp.
  Cuarentena reversible.
- **Pentesting** (`pentest/`+`network/`): nmap (recon) + sqlmap + OWASP ZAP +
  captura de paquetes (scapy). TODO validado contra `authorized_targets.yaml`
  (solo Damian lo edita a mano) antes de correr.
- **Investigación forense** (`investigation/`): casos como repos git, artifact
  store por sha256, log append-only firmado Ed25519 (claves con DPAPI), ingesta de
  evidencia con pipeline de confirmación.
- **Web layer + OSINT + forms:** `web_get` (sensor autoescalante), `web_scrape`,
  OSINT (`ip_geolocate`, `crypto_address_trace`, reimplementados inspirados en
  Horus — Horus es GPL, no se copió código), y `forms/` (completado de formularios
  con credential store cifrado + dry-run + preview token de un solo uso antes del
  submit).
- **Control PC/celular:** `desktop_*` (Windows) + `phone_*` (Android por WS).
  Control total e invasivo, apagable por flags.
- **Ingesta de conocimiento** (`ingestion/`+`obsidian/web_ingest.py`): YouTube
  (playlist + video suelto), arXiv, y web directa. Reemplaza el flujo manual de
  NotebookLM. **Ingesta AUTOMÁTICA (2026-10-05):** un vigilante en background
  (`playlist_watcher.py`) revisa la playlist cada 3 min e ingiere solo los videos
  nuevos, solo (realiza el diseño de `vision/AUTO-INGESTA-PLAYLIST.md`).
- **Raphael Intel** (`ingestion/`, spec `SPEC-RAPHAEL-INTEL.md`): el "cerebro de
  inteligencia del mundo" — cada día sale a buscar qué cambió (geopolítica, economía,
  ciencia, tech), lo resume y lo guarda buscable en el vault. Fase 0 (base + fuente
  arXiv) ya construida; es la versión legal de "conocimiento es poder" (sobre sistemas
  y el mundo, no personas).

---

## 9. Gates de seguridad (los no-negociables)

Estos están decididos e implementados — **no se debilitan sin permiso explícito
de Damian:**

1. **Pentesting activo detrás de `authorized_targets.yaml`** (fuente única,
   2026-08-13). Ni las tools ni el LLM pueden escribir ese archivo. Por default el
   scope solo permite rangos privados/loopback/Tailscale; escanear una IP pública
   exige que Damian la agregue a mano (escanear sin autorización puede ser ilegal).
2. **Auto-reparación con gate de aprobación** (`selfrepair/`): proponer en dry-run
   libre; aplicar (`confirm=true`) exige un `proposal_id` concreto que confirma
   Damian. Guardrail de self-target en `agent.py`.
3. **Patrón dry-run → confirm=true** para todo lo destructivo: cuarentena (mover,
   no borrar), fixes de código, submit de formularios (preview token de un solo uso
   atado a selector+página+TTL).
4. **Flags para apagar cada capacidad invasiva** sin tocar código
   (`DESKTOP_CONTROL_ENABLED`, `PC_SHELL_ENABLED`, `PHONE_SHELL_ENABLED`,
   `PHONE_CAMERA_ENABLED`, `NMAP_ENABLED`, etc.). Prendidos por default a pedido de
   Damian.
5. **Sandbox de filesystem** (`FS_ALLOWED_ROOT`). ⚠️ Por default es el HOME entero,
   no solo el repo — hay una mitigación barata pendiente (achicarlo a una línea).
6. **`pc_run_command` NO es sandbox real**, es una blocklist de patrones
   destructivos. Auditoría persistente de todo lo que ejecuta.
7. **Presupuesto de contexto protegido** en varias capas (tras bugs reales de
   context-exceeded). Si cambiás de modelo, sincronizá `MODEL_CONTEXT_TOKENS`.
8. **Repo PÚBLICO → nunca commitear secretos** (`.env`, claves,
   `authorized_targets.yaml`, targets, credenciales). El `.gitignore` cubre lo
   obvio; revisar antes de pushear.
9. **Material PERSONAL de Damian** (Vault-Fenix, análisis psicológicos) NO va al
   repo público ni se expone de más.

Detalle transversal en `docs/raphael/14-seguridad-transversal.md`.

---

## 10. Laboratorio y diseños (sin implementar o apagados)

- **Generación de imagen/video (ComfyUI):** 🔴 apagada. La PC se apagó
  físicamente bajo carga sostenida de GPU (Wan 2.2) — pero el Event Log muestra un
  historial de cortes tipo pérdida de energía DC *semanas antes* de que existieran
  estas tools, así que la causa raíz apunta a fuente de poder/instalación
  eléctrica, no al software. No reactivar sin medir temperaturas/voltajes (AIDA64 ya
  loguea a CSV).
- **Cyber range** (`lab/`): laboratorio de pentesting aislado en VirtualBox (Kali
  2026.2 + Metasploitable 2 en red interna "labnet", DHCP 10.13.37.0/24). Quedó a
  mitad de armado. Guía para retomar: `lab/RETOMAR-LAB.md`.
- **Defensa "kernel-grade" gratis** (diseño): orquestar componentes de kernel que
  Windows ya trae firmados (ETW, Sysmon, AMSI, ASR, WDAC, AppLocker, WFP) sin driver
  propio. Siempre audit mode antes de block. `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`.
- **Orquestación remota** (diseño): controlar a Raphael desde el celular fuera de
  casa, solo por Tailscale, auth por dispositivo (DPAPI), tools `vm_control`/
  `ssh_guest`, cola de misiones con confirmaciones remotas.
- **Sandboxing en contenedor** (propuesto): meter `pc_run_command`+`browser_*` en
  Docker. Falta instalar Docker Desktop. Mitigación barata mientras tanto: achicar
  `FS_ALLOWED_ROOT`.
- **Escuadrón de drones** (`docs/SPEC-escuadron-drones.md`) + modelos 3D
  (NanoHornet-3D, Escuadron-3D en el Escritorio).
- **Voz:** PC funcional (openWakeWord "hey Jarvis" → Silero VAD → faster-whisper).
  Android con un bug de wake word (diagnóstico pausado). Specs `SPEC-RAPHAEL-VOZ.md`.
- **Auditoría en tiempo real** (propuesta, `PROPUESTA-Raphael-tiempo-real.md`):
  "casi tiempo real" en dos velocidades — escaneo determinista por archivo/diff al
  guardar (rápido) + triage LLM solo bajo demanda (lento, no por tecla).
- **Motor de decisiones "System 1"** (experimento, `EXPERIMENTO-JEV-motor-de-
  decisiones.md`): un modelo que devuelve decisiones TIPADAS + confianza calibrada
  (no texto) para los pasos de decisión de la Brigada (clasificar/puntuar/rutear),
  más rápido/barato que el LLM. Opción elegida = LAYA; quedó **parkeado** (falló la
  eval de triage). Fundamentos en `FUNDAMENTOS-caja-negra-y-verificacion.md`.
- **Harness multiagente** (`SPEC-HARNESS-MULTIAGENTE.md`): el spec lo ponía como
  diseño a futuro, pero el motor YA está construido (`app/harness/`, commits
  `bc11a07`/`46c49b6`): DAG, pizarra, routing, worktrees, A2A, consola multiagente.
- **Harness de voz** (`SPEC-RAPHAEL-VOZ.md`), **app de celular / Dispatch móvil**
  (`VISION-APP-CELULAR.md`), **capa de navegación de agente** (ya implementada como
  `web_get`, `SPEC-capa-navegacion-de-agente.md`).
- **Roadmap** (`ROADMAP-MEJORAS-RAPHAEL.md`): surgió de DOS análisis que convergieron
  (la autoevaluación de Raphael sobre sí mismo + el análisis del vault). Casi todo es
  endurecimiento **post primera venta**; quick-wins primero.

---

## 11. El negocio y el sistema de trabajo

**Cómo se monetiza:** el servicio que se vende ahora es **Blindaje PyME (LITE)** —
backups + Defender full/Tamper Protection + SmartScreen + updates + contraseñas/
wifi, entregable en un día (NO la versión "gourmet" kernel-grade de semanas).
Herramienta de venta: `Escritorio/Blindaje-PyME-Checklist-15min.md`. La app de
auditoría de código es el otro camino monetizable. Plataformas freelance:
Fiverr (gig publicado; trabado por verificación de DNI) y Workana (perfil sin
verificar). Instagram `@raphaelseguridad` creada, primer post pendiente.

**Sistema de trabajo "cocina"** (cómo Damian ordena el trabajo — él es cocinero
profesional): `COMANDAS.md` (riel de tareas, 4 pasos, UNA en el fuego a la vez),
`TABLA.md` (ideas crudas), `recetario/` (procedimientos repetibles), `PROVEEDORES.md`,
`docs/LA-BRIGADA.md` (los agentes como brigada de cocina). La tesis: *procedimiento
repetible = consistencia = escalabilidad* (lo que deja vender un servicio).

**El recetario** (`recetario/`, 9 recetas): 01 Blindaje PyME · 02 cambiar el cerebro
(modelo LLM) · 03 ingesta YouTube al vault · 04 montar el cyber range · 05 estrés/
detección nocturna · 06 hardening/auditar sistema · 07 co-host de stream · 08 shell
del celular por SSH/Tailscale · 09 respaldo del proyecto.

**Estrategia (de la charla de midudev, `INSIGHTS-...`):** los modelos son un
commodity (cambiar uno por otro da casi igual en el 90-95%); el negocio no está en el
modelo sino en **saber implementarlo**. Self-hosting = ahorro brutal. Es la tesis que
sostiene el enfoque de Raphael como servicio, no como modelo.

---

## 12. La visión

El norte es la habilidad **"Gran Sabio / Raphael" de Tensura**: un asistente que
percibe, recuerda, razona y avisa proactivamente. Hoja de ruta por etapas
(`vision/HACIA-RAPHAEL.md`): 0 = percibe/recuerda (hoy) → 6 = avisa proactivo.
Meta de fondo: **invertir la relación** — que Raphael haga el trabajo pesado y la
supervisión humana corrija (requiere el doble modo supervisado/autónomo, pendiente).

---

## 13. Estado actual (2026-10-05) y pendientes

**Hecho en las últimas sesiones:**
- Ruteo de modelos por tarea (tiers 0-3, Sonnet/Opus, planner, persistencia,
  fallback), retiro de opencode/cloud_expert, ablación de prompts.
- Memoria episódica (captura + recall + firma).
- `web_get` activado end-to-end (Scrapling).
- **Estructura informacional cerebro-símil:** Fase 1 (spreading) + Fase 2
  (Hebbian) + ingesta web directa, todo tier 0 + embeddings, con tests.
- **Bug de ingesta de videos arreglado:** no existía tool de video suelto y la de
  playlist no estaba en ningún skill (el agente nunca la veía → caía a `web_get` y
  devolvía los capítulos). Fix: `youtube_ingest_video` + pipeline `ingest_video` +
  **nuevo skill `ingesta`** que expone video/playlist/web; mapeado también
  `audit_report_brigade` (hueco preexistente). **Requiere reiniciar el backend.**
  (La ingesta manual en realidad nunca estuvo rota: el "Read timed out" de la tray es
  que la playlist entera en el modelo local tarda >30 min; el backend sigue atrás y
  crea las notas igual — se verificaron 13 notas de video creadas.)
- **Ingesta AUTOMÁTICA de la playlist:** vigilante en background
  (`app/ingestion/playlist_watcher.py`) que revisa **cada 3 min** e ingiere solo los
  videos nuevos, sin pasar por la tray (sin timeout). Realiza el diseño viejo de
  `vision/AUTO-INGESTA-PLAYLIST.md`. **Requiere reiniciar el backend.**

**Git:** rama `opt/system-prompt-ablacion`, último commit `26c9a1a` (ruteo de modelos
+ web_get + housekeeping). TODO el trabajo de octubre (estructura cerebro, ingesta de
video, skill `ingesta`, vigilante de playlist, este resumen) está **sin commitear** —
Damian lo commitea en PowerShell (mi entorno no puede escribir a `.git`).

**Cabos sueltos:**
- Commitear el trabajo sin commitear (Damian lo hace en PowerShell).
- Volver el `.env` a Sonnet 5.5 cuando termine la ingesta de videos.
- Fase 3 y 4 de la estructura cerebro-símil.
- Mitigación barata de sandbox (`FS_ALLOWED_ROOT`); decidir Docker.
- Cyber range (retomar), Nessus (registrar), pentest WiFi propio.
- Primera venta (Blindaje PyME); publicar IG; verificación Fiverr (DNI 13/10).
- Decidir merge de `opt/system-prompt-ablacion` a master.

**Respaldo:** hay una tarea programada horaria (`jarvis-backup-hourly`) que
auto-commitea y pushea las carpetas clave.

---

## 14. Mapa de documentación — dónde vive cada cosa

- **Reglas estructurales / arquitectura / modelos / gates:** `CLAUDE.md`
- **Estado operativo y prioridades:** `ESTADO.md`
- **Doc módulo por módulo:** `docs/raphael/00-INDICE.md` … `15-configuracion.md`
- **Manual histórico (2026-07-27, viejo pero útil para el origen):** `INFORME_COMPLETO.md`
- **Specs de diseño:** `docs/SPEC-*.md` (harness, memoria episódica, estructura
  cerebro, capa navegación, intel, voz, tiempo real, drones)
- **Brigada / sistema de trabajo:** `docs/LA-BRIGADA.md`, `COMANDAS.md`, `TABLA.md`
- **Procedimientos repetibles (vendibles):** `recetario/` (9 recetas)
- **Análisis del código real:** `docs/ANALISIS-CODIGO-RAPHAEL.md` + `PLAN-OPTIMIZACION-CODIGO.md`
- **Base de conocimiento (notas):** `backend/obsidian_vault/jarvis/` y `Vault-Fenix`
- **Laboratorio y defensa:** `lab/` (cyber range, kernel-grade, orquestación remota)
- **Visión:** `vision/HACIA-RAPHAEL.md`, `CAPACIDADES-REALES-DE-JARVIS.md` (auditoría
  honesta), `ORQUESTACION-ESTRUCTURA.md`, `AUTO-INGESTA-PLAYLIST.md`, `VISION-APP-CELULAR.md`
- **Instalación / arranque:** `install.ps1`, `QUICKSTART.md`, `backend/README.md`
- **Config y secretos:** `backend/.env` (NO se commitea — repo público)
