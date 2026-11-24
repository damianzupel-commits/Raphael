# 📓 Bitácora de sesión — 2026-09-03 / 04

> Resumen completo de una sesión larga de trabajo (Damian + asistente Cowork/Claude)
> para que **Raphael retome con el máximo contexto durable**, sin depender de la
> memoria de Damian ni de la transcripción del chat (que vive en Cowork, no en la PC).
>
> ⚠️ **Este doc es solo lo TÉCNICO / de decisiones.** Lo personal/filosófico de la
> sesión se dejó afuera a propósito (el repo es público). No mezclar.

---

## 1. Ingesta de YouTube — RESUELTA definitivamente

- **Causa raíz del bloqueo anterior:** YouTube bloqueó a la librería
  `youtube-transcript-api` a nivel IP (`IpBlocked`), incluso desde IPs móviles.
- **Fix aplicado (`backend/app/ingestion/youtube_playlist.py`):** se reemplazó por
  **yt-dlp** (`extract_info` para listar subtítulos manuales/auto, se elige la mejor
  pista es→en→pt, se baja el `.vtt` con el propio cliente de yt-dlp y se parsea a
  texto plano). Helpers: `_select_subtitle_track`, `_pick_vtt_url`, `_parse_vtt`.
  Se fue el fallback de traducción (ahora el PT entra directo, DeepSeek resume igual).
- **429 (rate-limit):** reintento con backoff (3s/6s/12s) + respiro de 1.5s entre
  videos. El 429 se reintenta; otros errores propagan.
- **Estado:** playlist completa (creció 91→93→95, todo al día). Validado también
  **remoto desde el celular por Tailscale** (el backend corre en la PC, YouTube
  funciona ahí). Tests reescritos, pasan.

## 2. Memoria persistente

- **Backend:** el historial de chat se persiste en `backend/data/conversations.json`
  (gitignoreado) y se recarga al arrancar (`agent._persist_conversations` /
  `_load_conversations`). Config: `CHAT_PERSIST_ENABLED`, `CONVERSATIONS_PATH`.
- **Tray:** transcript visible compartido en `backend/data/tray_chat_history.json`
  (append-based) — la ventana Y la barra flotante del orbe escriben al mismo archivo.

## 3. Rediseño de UI a "Raphael" (tray-app)

- **Rename Jarvis→Raphael:** en la UI (título, saludo, "Raphael está pensando…",
  bandeja) Y en la **identidad del cerebro** (`agent.py` SYSTEM_PROMPT: "Te llamás
  Raphael"; el proyecto sigue siendo JarvisRemote). Antes se presentaba como Jarvis.
- **Orbe flotante** (`ui/orb.py`) como interfaz principal: **dibujado desde cero y
  animado** (núcleo incandescente + halo que respira + remolino cónico + anillos
  orbitando + partículas). La ventana grande queda oculta; se abre por secciones
  desde el menú del orbe.
- **Barra de chat flotante** debajo del orbe: input + **🎙 mic** (voz, reusa
  VoiceListener), **resize** con agarradera visible (QSizeGrip), **scroll** en la
  respuesta, muestra solo el último mensaje. Comparte conversación y transcript con
  la ventana.
- **Menú del orbe:** Historial, Codebase, Obsidian, Investigación, Configuración, Voz
  (Chat NO — vive en la barra flotante).
- **Encabezado de secciones** "Raphael · <sección>" + ✕, sin la barra de modelo ni
  pestañas (navegación por el orbe). Fondo de la imagen de Raphael a nivel ventana.
- **Nota:** el selector de la tray muestra "Lite" pero es cosmético — el `.env` está
  en DeepSeek. NO tocar el selector (pisa la config; bug conocido).

## 4. Robustez de arranque backend/tray (anti-10048)

- `stop()` espera a que el puerto 8000 quede libre antes de volver; `start()` confirma
  que el backend levantó (o avisa el fallo); cerrar la tray solo baja el backend que
  ELLA lanzó (`only_own=True`) — no mata uno externo de PowerShell. Un solo backend,
  clientes se atan. Tests actualizados.

## 5. AUDITORÍA — el gran avance del día

### 5a. Informe CLIENT-FACING (`backend/app/audit_report.py`)
- Nueva función `generate_client_report` (async) que usa la tool `audit_generate_report`:
  narrativa del LLM (**Resumen ejecutivo** en lenguaje de negocio + **Riesgos
  prioritarios** en criollo: qué es / por qué importa / cómo se arregla), con las
  tablas crudas como **Anexo técnico**. `generate_report` (mecánico) quedó intacto.

### 5b. TRIAGE automático de falsos positivos (la mejora de RAÍZ)
- `generate_client_report` corre `security.triage.triage_findings` sobre los hallazgos
  critical/high/medium no triageados (tope 30): el LLM **lee el código real** y descarta
  los no explotables con su razón. Los falsos positivos NO entran en los riesgos
  prioritarios — van a una sección "Descartados por triage". Tests agregados.

### 5c. Tests contra repos reales (en `C:\Users\dam\Downloads\audit-targets\`)
- **pygoat** (lab OWASP, calibración): cazó las vulns conocidas (command injection,
  MD5, Flask debug, Docker root). 200-347 hallazgos (muchos intencionales).
- **flask-realworld** (app real): **descubrimos un FALSO POSITIVO** — Semgrep marcó un
  `subprocess` como "posible RCE", pero era un comando CLI de dev (`flask lint`
  corriendo flake8), sin input de usuario. Esto motivó el triage automático (5b).
- **studybud** (Django, con triage ya integrado): el triage **acertó las dos** — descartó
  un falso positivo de CSRF (el form tenía `{% csrf_token %}`) y confirmó la SECRET_KEY
  hardcodeada. PERO los escáneres se escaparon `DEBUG=True`, `ALLOWED_HOSTS=[]` y una
  `db.sqlite3` commiteada → **gap de COBERTURA** (motivó el config checker, QW-4).

### 5d. Lecciones clave (de negocio)
- **"La IA redacta, vos verificás":** el paso de verificación humana es tu valor, no opcional.
- **"1 hallazgo ≠ 1 problema":** precisión ya resuelta (triage); falta cobertura (config).
- **El informe ES el producto vendible.** Validado en 3 repos.

## 6. Roadmap de mejoras → `docs/ROADMAP-MEJORAS-RAPHAEL.md`

Surge de DOS análisis independientes que convergieron: la **autoevaluación de Raphael
sobre sí mismo** + el **análisis del vault** (~93 notas) por Claude. Quick-wins:
QW-1 tool routing por dominio (costo), QW-2 anclar el cerebro (bug del selector),
QW-3 **citar fuentes en el informe** (credibilidad — toca la venta), QW-4 config
checker (cobertura). Fase 1: F1-1 **retrieval** (el de más impacto), F1-2 **la brigada**,
F1-3 memoria de criterio automática, F1-4 proactividad/background, F1-5 spec-driven,
F1-6 model routing por tiers, F1-7 benchmark curado. **Todo post primera venta.**

## 7. Diseño de la brigada (multi-agente) — en el roadmap (F1-2/F1-6)

- Patrón: **Sous-Chef/orquestador (reparte) → estaciones especializadas (cada una su
  contexto chico) → Pase/Agregador → Catador/QA.** Modelo formal: grafo (DAG) con
  orden topológico.
- Estaciones: Reconocimiento (escáneres, determinista) · Triage · Config · Redacción ·
  Pase · Catador. Ya existe ~60% (reconocimiento, triage, redacción).
- Paralelismo para codebases gigantes: **git worktrees** (cada agente en copia aislada).
- **Model routing por tiers:** Tier 0 sin modelo (escáneres) · Tier 1 chico/rápido
  (router, config) · Tier 2 potente (redacción, orquestador, catador, triage high).
  Routear por ESTACIÓN (fijo), no por juez dinámico. Sube calidad solo INDIRECTO
  (deja affordear el modelo fuerte donde el LLM razona). La plomería multi-modelo ya
  existe (`cloud_expert`=Gemini, embeddings=nomic).

## 8. Test C — Raphael se audita a sí mismo (agendado, ver COMANDAS)

Apuntar `security_scan_project` + `audit_generate_report` al propio `backend/`. Es
"**PyGoat al revés**": las capacidades peligrosas intencionales (`pc_run_command`,
`subprocess`, tools ofensivas) saltan como hallazgos — el triage + verificación de
Damian separa "intencional" de "bug real". Aplicar fixes (`selfrepair/`) SOLO con
confirmación manual. Usar como test/demo, no como refactor infinito.

## 9. Cola "apenas llegue a la PC" (en orden)

1. **Verificar la tray** (orbe animado, resize, mic, historial) tras los cambios.
2. **Test C** (Raphael se audita a sí mismo) — validación + demo de marketing.
3. **QW-3** (citar fuentes en el informe) — implementar + testear contra los 3 repos.
4. **La venta** 🎯 — con el informe mejorado + una muestra limpia, empujar el Gig de
   Fiverr + outreach.

## 10. Estado del negocio

- **Gig de Fiverr publicado.** Producto de auditoría **validado en 3 repos**.
- **Prioridad = la PRIMERA VENTA.** El producto ya es vendible; lo que falta es un
  cliente, no una herramienta mejor. Los fixes técnicos sirven pero no deben comerse
  el tiempo de vender. Regla: la venta puede solaparse con el endurecimiento, no ser
  estrictamente después.
