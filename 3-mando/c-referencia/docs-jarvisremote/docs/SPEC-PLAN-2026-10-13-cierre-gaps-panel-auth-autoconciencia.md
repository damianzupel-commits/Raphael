# SPEC / PLAN — Cierre de gaps + Auth por dispositivo + Capa de autoconciencia

> Creado 2026-10-12 (sesión nocturna con Claude). **Objetivo: terminar esto SÍ o SÍ en la
> próxima sesión.** Es un plan de ejecución, no un spec abierto: cada ítem trae QUÉ, DÓNDE
> (archivos), CÓMO, criterio de TERMINADO y esfuerzo (S/M/L).
>
> Contexto previo: ver el inventario de trabajo olvidado que salió de `ESTADO.md` + specs.
> Este plan es el subconjunto que **sirve** a las dos direcciones reales: **(a) producto**
> (app móvil + multiusuario + remoto) y **(b) autoconciencia/robot**. Lo descartado y lo
> aparcado están al final para no re-discutirlos.

---

## Estado de dónde venimos (sesión 2026-10-11/12, NO reflejada aún en ESTADO.md)

Construido y verificado esta sesión (todo SIN commitear, a pedido de Damian):
- **Config amigable** web (`/configuracion`) data-driven + **APIs por tier** con secretos enmascarados (`backend/app/user_config.py`, `config_dialog.py`, `docs/raphael/configuracion-raphael.html`).
- **Etapa 1 sync por QR** (`backend/app/pairing.py`, `/vincular`, tray `pair_dialog.py`, Android `PairScanScreen.kt` + `PairingPayload.kt`). Requiere `pip install qrcode`.
- **Centro de Mando NATIVO en Android** (`ui/mando/`): grilla de 9 brigadas en vivo (WS), detalle con escuadrón/tiers, **monitor de tools en vivo**, **grafo 3D de Obsidian** (~410 notas), secciones interactivas de **Ingesta / Investigación / Trading**.
- **Operaciones**: supervisor Sonnet (`ops_supervisor.py`, flag `OPS_SUPERVISOR_ENABLED`) + watchdog (`OPS_WATCHDOG_ENABLED`), ambos default OFF.
- **Ingesta**: watchlist de fuentes + registro de ingeridos (`ingestion/sources.py`).
- **Investigación**: casos de research retenidos (`research_cases.py`).
- **Trading**: watchlist + estado por símbolo (`trading_watch.py`).

Dependencias a instalar en la PC antes de probar: `pip install qrcode` (QR), `pip install ccxt`/`yfinance` (datos reales de trading; sin eso = DEMO).

---

## ORDEN DE EJECUCIÓN (hacer en este orden)

1. Hooks de fondo del panel  (S)
2. Gaps de la sesión: Investigación-hallazgos (S), Ingesta-web (S, depende de web_get), Trading 3/5 (M)
3. Token de auth por dispositivo DPAPI  (M)
4. Paridad del panel de la PC (HTML)  (M)
5. Discernimiento proactivo  (M)
6. Capa de metacognición / autoconciencia  (L, por fases)
7. Actualizar ESTADO.md  (S)

---

## 1. Hooks de fondo del Centro de Mando  —  S

**Problema:** solo las brigadas que tocan una tool se encienden. Las de **jobs de fondo**
quedan "en espera" para siempre y parecen rotas (pasó con Investigación).

**Qué:** que cada job de fondo reporte a su brigada vía `mission_control.report(...)`, igual
que ya hace `playlist_watcher` con `"ing"`.

**Dónde + cómo:**
- `app/obsidian/consolidation.py` (loop `consolidation_loop`): al correr una consolidación →
  `await mission_control.report("mem", f"🧠 consolidadas {n} notas")` (o "sin clusters nuevos", inc=0).
- `app/obsidian/curiosity.py` (loop `curiosity_loop`): al detectar huecos →
  `await mission_control.report("mem", f"🔎 {k} huecos detectados")`.
- `app/malware/fullscan.py` (`full_scan_loop`) y `behavioral_watcher`: al escanear / detectar →
  `await mission_control.report("mal", "escaneo diario · limpio" | f"⚠️ {amenaza}")`.
- Patrón: `try: from .. import mission_control; await mission_control.report(...) except Exception: pass` (best-effort, nunca rompe el job).

**TERMINADO cuando:** con los jobs prendidos, las brigadas Memoria y Antimalware muestran
actividad real en el panel (count + "actividad en vivo"). Test: mockear `report` y verificar
que cada loop lo llama (como `test_playlist_watcher`).

**Nota:** el "orquestador maestro (Opus) coordinando" NO entra acá — hoy el maestro es una
etiqueta estática; coordinar de verdad necesita un mecanismo de orquestación que todavía no
existe. Es un ítem aparte (aspiracional), no un hook.

---

## 2. Gaps de la sesión

### 2a. Investigación — poblar los hallazgos  —  S
**Problema:** los casos se crean pero `findings` siempre queda en 0 (guardo la pregunta, no la respuesta).
**Qué/Dónde:** en `agent.py`, al cerrar el turno, si hay un caso de research recién creado en
este turno (o abierto que matchea la pregunta), llamar `research_cases.add_finding(case_id, resumen)`
con un resumen corto de la respuesta final. Guardar el `case_id` creado en una var del turno
(cerca del hook de creación que ya existe tras `history.append(... user ...)`).
**TERMINADO:** tras una pregunta "investiga X", el caso muestra ≥1 hallazgo con texto en la app.

### 2b. Ingesta — páginas web  —  S (depende de web_get activado, ver ítem 5/deps)
**Problema:** solo YouTube se registra; agregar una URL web no se ingiere ni aparece.
**Qué/Dónde:** en la tool `obsidian_ingerir_web` (`app/obsidian/web_ingest.py`), tras ingerir,
llamar `ingestion/sources.log_ingested(titulo, url, "web")`. Para auto-ingesta de fuentes web
recurrentes: que el watcher distinga el tipo de fuente (YouTube → `ingest_playlist`; web →
`obsidian_ingerir_web`) en `playlist_watcher.run_once`, o un loop web aparte. V1: al menos
registrar lo que se ingiere a mano por la tool, para que aparezca en "ingerido recientemente".
**TERMINADO:** una página ingerida aparece en la sección Ingesta con su link.

### 2c. Trading — completar la propuesta (faltan 3/5)  —  M
Hoy hay watchlist + tarjeta de setup. Faltan:
- **Track record:** reusar `app/trading/backtest.py` (`simulate` → win rate / expectativa) por
  símbolo. Endpoint `POST /api/trading/watch/backtest {instrument}` → stats; mostrarlo en el
  detalle del símbolo. (M)
- **Panel de riesgo:** `signals.py` ya calcula `units`/`risk_cash` vía `RiskConfig`; exponer el
  sizing sugerido en la tarjeta de setup (solo informativo). (S)
- **Alertas al cel:** cuando un refresh deja un símbolo en "señal activa", mandar notificación.
  Necesita un **loop de refresh en background** (hoy es on-demand) + push. Opción simple sin FCM:
  empujar por el WebSocket que ya existe (`phone_link`/notificación local Android). (M)
**TERMINADO:** detalle de símbolo con win rate + sizing; notificación al pasar a "señal activa".
**Gate de seguridad:** TODO esto es SOLO análisis. Nunca ejecuta órdenes ni mueve dinero.

---

## 3. Token de auth por dispositivo (DPAPI, revocable)  —  M

**Por qué:** hoy todo usa un único `API_KEY` en claro. Esto resuelve **3 cosas de una**:
(a) token del panel/mission-control, (b) auth del acceso remoto del producto, (c) multiusuario.
Reemplaza al token ad-hoc del panel (descartado) y a exponer el API_KEY en el QR.

**Diseño base ya escrito:** `lab/ORQUESTACION-REMOTA-DESIGN.md`. Patrón de cifrado a reusar:
`app/forms/credential_store.py` (DPAPI) e `app/investigation/keys.py` (Ed25519+DPAPI).

**Qué/Dónde:**
- Nuevo `app/device_tokens.py`: store cifrado con DPAPI de tokens por dispositivo
  `{token_id, label, scope, created, last_seen, revoked}`. Funciones: `issue(label, scope)`,
  `verify(token) -> scope|None`, `revoke(token_id)`, `list()`.
  - `scope`: `"full"` (chat + control) o `"read"` (solo panel/lectura).
- `app/auth.py` (`verify_api_key`): aceptar **o** el `API_KEY` maestro **o** un device token
  válido. Variante `verify_read` para endpoints de solo-lectura (panel).
- **Emparejamiento (`pairing.py`):** al generar el QR, **emitir un device token** (`issue`)
  y meter ESE en el payload en vez del `API_KEY` maestro. Así cada cel pareado tiene su token
  revocable; si se pierde el cel, se revoca sin rotar la key de todos.
- **Mission-control** (`/ws/mission-control`, `/api/mission-control/state`, `/centro-de-mando`):
  pasar de "sin auth" a exigir token `read`. La app ya manda `Authorization: Bearer <token>`.
- **Gestión:** endpoint + sección en `/configuracion` para listar/revocar dispositivos.

**TERMINADO:** parear por QR crea un token por dispositivo; el panel exige token; se puede
revocar un dispositivo desde Configuración sin romper los demás. Tests: `test_device_tokens`.
**Seguridad:** los device tokens NUNCA dan scope para tocar líneas rojas (gates intactos).

---

## 4. Paridad del panel de la PC (HTML)  —  M

**Problema:** las secciones interactivas nuevas (fuentes de Ingesta, casos de Investigación,
watchlist de Trading, grafo) las hicimos NATIVAS en Android; el panel de la PC
(`docs/raphael/centro-de-mando-raphael.html`, en el webview de la tray) quedó atrás.

**Qué:** agregar al detalle del HTML las mismas secciones, consumiendo los mismos endpoints
(`/api/ingest*`, `/api/investigation*`, `/api/trading/watch*`, `/api/obsidian/graph`) con la
key que ya recibe por `?key=`. El grafo 3D: el panel de la PC ya tiene un grafo 3D propio
(`graph3d.html` / `GraphView`) — reusar ese, no reimplementar.

**TERMINADO:** desde la tray, el detalle de cada brigada tiene las mismas acciones que el cel.
**Alternativa más barata:** si no vale el doble mantenimiento, evaluar que la tray embeba las
mismas vistas — decidir en el momento.

---

## 5. Discernimiento proactivo de conocimiento  —  M

**Por qué:** visión app #4 + el "que siga investigando sola". `curiosity.py` ya detecta huecos
(notas citadas que no existen, huérfanas) pero **solo avisa**.

**Qué/Dónde:**
- Extender `curiosity_loop`: para huecos de tipo "nota faltante citada", opcionalmente
  **buscar + ingerir** el conocimiento faltante (web_get / research_topic → `obsidian_ingerir_web`).
- Para casos de Investigación abiertos (`research_cases`): un paso que cada tanto re-investiga
  un caso abierto y le suma hallazgos (`add_finding`).
- **Gate:** flag nuevo `PROACTIVE_LEARNING_ENABLED` (default **OFF** — gasta LLM/red). Respeta la
  compuerta de privacidad (`privacy.py`): lo personal nunca sale al tier 2.
**TERMINADO:** con el flag ON, un hueco citado se llena solo; un caso abierto suma hallazgos con el tiempo.

---

## 6. Capa de metacognición / autoconciencia (capa 2)  —  L, por fases

Esto ES el esqueleto de la autoconciencia funcional (ver la charla: "sabe qué sabe"). Piezas,
apoyadas en lo que ya existe (`confidence.py`, `feedback.py`, `strength.py`, `testing/`):

- **F1 — Confianza calibrada (LAYA):** estimador encima de `confidence.py` que calibra la
  confianza reportada contra resultados reales (no solo señal de grafo). (M)
- **F2 — Cerrar el lazo de aprendizaje:** auto-detectar tests/correcciones (pipeline `testing/`)
  → refuerzo POSITIVO automático (hoy el positivo es explícito vía `obsidian_resultado`; el
  negativo ya es automático en el `finally` de `run_agent`). (M)
- **F3 — Reconsolidación de CONTENIDO (Fase 2 §3.5 del spec cerebro):** reconsolidar el texto de
  las notas, no solo los links. (M)
- **Self-model unificado (capa 1 de la arquitectura):** un "modelo de sí mismo" consultable que
  junte capacidades + config + estado en vivo (introspección + `config` + mission_control). Es
  el esqueleto del que cuelgan las otras capas; evaluarlo como primer paso de esta sección. (M)

Spec de referencia de la arquitectura completa de autoconciencia (6 capas): ver la conversación
de esta sesión + `docs/SPEC-estructura-informacional-cerebro.md` y `vision/RAPHAEL-CEREBRO-NO-BIOLOGICO.md`.

---

## 7. Actualizar ESTADO.md  —  S

`ESTADO.md` quedó en 2026-09-30. Agregar la sesión 2026-10-11/12 (config amigable, APIs por tier,
QR sync, Centro de Mando nativo + grafo 3D, supervisor/watchdog, Ingesta/Investigación/Trading,
y este plan). Marcar qué quedó SIN commitear.

---

## DESCARTADO (no hacer — ya hay algo mejor)

- **Token del panel ad-hoc** → absorbido por el token DPAPI (ítem 3).
- **Tailscale como transporte del PRODUCTO** → reemplazado por QR (hecho) + relay/Headscale (Etapa 2). Para uso personal de Damian, Tailscale sigue bien.
- **Medir A/B de prompts (slim)** → superado por el ruteo de 5 tiers (el slim era para el 8B local).
- **"Mandar menos de 103 tools por llamada"** → ya lo hace el sistema de skills (subsetea por tarea).
- **Achicar `FS_ALLOWED_ROOT` en la instancia de Damian** → lo castraría (necesita toda la PC para ser extensión de su cerebro). SOLO aplica al build que se venda a terceros.

## APARCADO (real, fuera del rumbo producto/robot — retomar si cambia la prioridad)

- Defensa kernel-grade (`lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`), cyber range (a medias),
  Docker sandbox, biblioteca vertical por MCP, automejora de la app Android.
- **Escuadrón de drones** (`docs/SPEC-escuadron-drones.md` + modelos 3D): reencuadrado como
  posible **cuerpo físico** de Raphael (embodiment), no como side-project muerto.

## PENDIENTES DE DAMIAN (no código)

- `pip install qrcode`, `pip install ccxt`/`yfinance`, `pip install scrapling` + `scrapling install` (activa web_get).
- Primer post de `@raphaelseguridad`.
- Decidir merge de `opt/system-prompt-ablacion` → master (chequear si sigue vigente).
- Reiniciar backend + `.\gradlew.bat installDebug` para ver todo lo de esta sesión.
- **Commitear** (nada commiteado todavía).

---

## Recordatorios de ejecución

- **No commitear** hasta que Damian lo diga.
- Backend: verificar por `py_compile` + tests aislados (el sandbox no importa la app por `win32crypt`).
- Android: no compila en el sandbox (sin SDK) — verificar por estructura; Damian buildea con `installDebug`.
- Flags nuevos: **default OFF** si gastan plata/red o cambian comportamiento (patrón de todo el repo).
