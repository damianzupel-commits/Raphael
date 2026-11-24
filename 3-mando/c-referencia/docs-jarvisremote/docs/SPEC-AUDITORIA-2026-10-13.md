# SPEC — Auditoría de Raphael: problemas, bugs y deuda técnica

> **Qué es esto:** una auditoría completa del estado real de Raphael (JarvisRemote)
> para trabajar sobre ella cuando vuelva el límite de Claude. Cada problema trae
> **severidad, dónde vive (archivo\:línea cuando aplica), impacto y fix propuesto**.
>
> **Cómo se produjo:** auditoría ESTÁTICA — lectura del código, `ruff` (pyflakes +
> bugbear), y cruce con `ESTADO.md` / `INFORME_COMPLETO.md`. **No se corrió el backend
> ni `pytest` en Windows** (el entorno de la auditoría es un sandbox Linux sin
> `win32crypt`/pywinauto/DPAPI). Por eso varios ítems dicen **"verificar vigencia"**:
> salen de docs que pueden estar desactualizadas — confirmá corriendo en la PC.
>
> **Auditoría iniciada:** 2026-10-13 · **HEAD auditado:** `9ed7a7b`.
> Análisis estático: **sin errores de sintaxis ni nombres indefinidos** en `backend/app`
> (el código importa/parsea bien; los problemas son de comportamiento y de operación).

---

## Resumen ejecutivo — por severidad

| # | Severidad | Problema | Dónde |
|---|---|---|---|
| P0-1 | 🔴 Crítico (operativo) | Trabajo grande posiblemente sin commitear / rama sin mergear → riesgo de pérdida | git / `ESTADO.md` |
| P0-2 | 🔴 Crítico (operativo) | Mucho código nuevo "requiere reiniciar / no validado en vivo" → estado real desconocido | varias sesiones |
| P0-3 | 🔴 Crítico (operativo) | App Android: todo lo nuevo SIN compilar/deployar | `android-app/` |
| P0-4 | 🟠 Alto | Dependencias pendientes de instalar → features fallan | `.env` / ESTADO |
| P1-1 | 🟠 Alto | El selector de modelo de la tray PISA la config del `.env` | `tray-app/process_manager.py` |
| P1-2 | 🟠 Alto | `phone_run_command` (Termux): "app is in background uid null" | `android-app` Termux |
| P1-3 | 🟠 Alto | Cámara del celular: timeout / "Camera is closed" | `android-app` CameraX |
| P1-4 | 🟡 Medio | Wake word Android intermitente, sin causa raíz | `android-app/.../voice/` |
| P1-5 | 🟡 Medio | `generate_image/video` apagadas por apagados físicos de la PC | hardware |
| P1-6 | 🟡 Medio | Click del ⚙ de config / `desktop_*` no validados contra GUI real | `tray-app`, `tools/desktop.py` |
| P2-1 | 🟠 Alto | Loops de fondo (proactivo/playlist) consumen el LLM solos → queman la cuota free | `main.py` startup |
| P3-1 | 🟠 Alto | `FS_ALLOWED_ROOT` = HOME entero (`C:\Users\dam`) | `backend/.env` |
| P3-2 | 🟡 Medio | `FS_ALLOW_DELETE=true` (borrado de archivos habilitado) | `backend/.env` |
| P3-3 | 🟡 Medio | `pc_run_command` = blocklist de texto, no sandbox real | `tools/pc_command.py` |
| P4-* | 🟢 Bajo | Deuda de código: features a medias, lint, ruteo del agente, A/B sin medir | varios |
| P5-* | 🔵 Diseño | Lab/sandbox/defensa/orquestación: diseñado, sin implementar | `lab/` |

---

## P0 — Riesgos operativos (lo más urgente; no son bugs de código)

### P0-1 · 🔴 Trabajo sin commitear / rama sin mergear
- **Impacto:** `ESTADO.md` (líneas 9-13, 19, 375) marca que **toda la tanda 2026-10-11/13**
  (app móvil, Centro de Mando nativo, autoconciencia) estaba **SIN COMMITEAR**, el ruteo de
  modelos 2026-09-30 **sin commitear**, y la rama `opt/system-prompt-ablacion` **sin mergear a
  master**. Ya se perdió contexto una vez (ago-2026). Esto es lo primero a blindar.
- **A verificar:** HEAD hoy es `9ed7a7b` (hubo commits desde que se escribió ESTADO, que
  registraba `6b68e68`). Confirmá con `git status` / `git log --oneline -20` **qué quedó
  realmente sin commitear** y si la rama se mergeó.
- **Fix:** commitear el working tree, pushear a `origin` (repo público → revisar que no se
  cuele ningún secreto), y decidir el merge de `opt/system-prompt-ablacion` → `master`.
  Actualizar `ESTADO.md` al cerrar.

### P0-2 · 🔴 Código nuevo "requiere reiniciar / no validado en vivo"
- **Impacto:** `ESTADO.md` repite decenas de veces *"Requiere reiniciar el backend"*,
  *"NO compilado"*, *"no se pudo correr en el sandbox"*, *"se prueba al redeploy"*. Mucha
  funcionalidad (memoria episódica, estructura cerebro-símil Fases 1-8, ruteo de 5 tiers,
  mission-control, geo/globo, trading, proactive, self-model) está **construida pero nunca
  corrida de punta a punta en la PC real**. El estado real es **desconocido** hasta ejecutarla.
- **Fix:** reiniciar backend + tray, **correr `cd backend && pytest`** (ESTADO dice que el
  sandbox no pudo), y validar en vivo las features clave. Cualquier import roto o regresión
  aparece acá.

### P0-3 · 🔴 App Android sin compilar/deployar
- **Impacto:** `ESTADO.md` (líneas 282-292, 43-46) marca que **el espejo de chat, el rebrand
  Jarvis→Raphael, el Centro de Mando nativo, el grafo 3D y el avatar** fueron construidos
  **"NO compilado (sin SDK en el entorno)"**. Pueden necesitar una o más iteraciones de build.
- **Fix:** conectar el celular por USB → `.\gradlew.bat installDebug` (o `deploy.ps1`),
  corregir los errores de compilación que aparezcan, validar en el Moto G72.

### P0-4 · 🟠 Dependencias pendientes de instalar
- **Impacto:** ESTADO (72, 344, 237) lista dependencias **a cargo de Damian** que, sin
  instalar, hacen fallar features: `qrcode` (vinculación QR), `ccxt`/`yfinance` (trading real),
  `scrapling` + `scrapling install` (`web_get` dinámico). OmniRoute (`npm i -g omniroute`) quedó
  **abandonado** (bug de auth) → no instalar.
- **Fix:** en el venv del backend: `pip install qrcode ccxt yfinance scrapling` y
  `.\.venv\Scripts\scrapling.exe install`. Verificar cuáles ya están.

---

## P1 — Bugs / comportamientos rotos (verificar vigencia)

### P1-1 · 🟠 El selector de modelo de la tray PISA la config del `.env`
- **Impacto:** bug REAL documentado varias veces (`ESTADO.md` 360, 403-404; `TABLA.md`). El
  selector Lite/Medio/Hard reescribe `LMSTUDIO_MODEL` en el `.env` (lo vuelve a `jarvis-text-v2`)
  y reinicia el backend. Si configurás a mano otro modelo (Sonnet/DeepSeek/gpt-oss) y después
  tocás el selector, **te pisa la config y perdés el modelo elegido sin darte cuenta**.
- **Dónde:** `tray-app/process_manager.py::set_active_model()` (reescribe `.env`).
- **Fix:** que el selector detecte cuando hay un modelo "manual" (no uno de los 3 tiers) y
  (a) no lo pise, o (b) muestre el modelo actual y pida confirmación antes de cambiarlo.
  Alternativa: un cuarto estado "Custom (.env)" en el selector.

### P1-2 · 🟠 `phone_run_command` (Termux): "app is in background uid null"
- **Impacto:** `INFORME_COMPLETO.md` (§4.4) — al correr un comando en el celular, error
  *"app is in background uid null"*. Probable restricción nueva de Android que bloquea el
  intent `RUN_COMMAND` de Termux cuando la app no está en foreground. **Sin diagnosticar.**
- **Dónde:** `android-app/.../phone/TermuxCommandRunner.kt` + `TermuxResultService.kt`.
- **Fix a investigar:** disparar el `RUN_COMMAND` desde un foreground service / con la app en
  primer plano; o revisar permisos `com.termux.permission.RUN_COMMAND` + `allow-external-apps`.

### P1-3 · 🟠 Cámara del celular: timeout / "Camera is closed"
- **Impacto:** `INFORME` (§4.4) — `phone_take_photo`/`phone_record_video` devolvían *"El
  celular no respondió a tiempo"* y *"Camera is closed"*. **Sin diagnosticar.**
- **Dónde:** `android-app` CameraX + el pipeline de frames (el video se manda como frames).
- **Fix a investigar:** ciclo de vida de CameraX (abrir/cerrar la cámara por captura),
  timeouts del lado backend, y la conversión a frames (`video_frames.py`).

### P1-4 · 🟡 Wake word Android intermitente
- **Impacto:** `INFORME` (§6.2) — mismo modelo da score 1.0 en Python pero falla intermitente
  en vivo en el celular; en una prueba funcionó sin saber qué cambió. **Diagnóstico pausado.**
- **Fix sugerido (del propio informe):** instrumentar `VoiceListenerService.kt` con timestamps
  por frame para detectar drops/desincronización del stream de `AudioRecord` en los intentos
  que fallan.

### P1-5 · 🟡 `generate_image` / `generate_video` desactivadas por apagados físicos
- **Impacto:** `INFORME` (§4.5) — la PC se **apagó físicamente** bajo carga sostenida de GPU
  (ComfyUI/Wan 2.2). Investigación extensa: la causa raíz apunta a **entrega de energía**
  (fuente al límite o instalación eléctrica), no a software. Hay historial de apagados
  `Kernel-Power 41 / BugcheckCode 0` casi diarios previos.
- **Dónde:** desactivadas a propósito en `backend/app/tools/__init__.py` (líneas ~286-287,
  `video_gen`/`image_gen` NO importados).
- **Fix:** **NO reactivar** sin antes diagnosticar el hardware (AIDA64 ya loguea temps/voltajes
  a `backend/hw_monitor_logs/`). Hacer una generación controlada y vigilada, revisar el log.

### P1-6 · 🟡 Click del ⚙ y `desktop_*` sin validación visual
- **Impacto:** `INFORME` (§5, §8) — el diálogo de config (⚙) y las tools `desktop_*` (control
  de ventanas) tienen tests unitarios pero **no se validaron clickeando una GUI real**. Riesgo
  de "pasa el test, no funciona de verdad".
- **Fix:** prueba manual en vivo: abrir el ⚙ y guardar; pedirle a Raphael que clickee algo en
  una app abierta y verificar que lo hace.

---

## P2 — Riesgos de consumo (importante para "dejarlo corriendo")

### P2-1 · 🟠 Loops de fondo consumen el LLM por iniciativa propia
- **Impacto:** `main.py` (startup) lanza al arrancar: `playlist_watcher.watch_loop`,
  `consolidation_loop`, `curiosity_loop`, `trading_watch.watch_loop`, **`proactive.proactive_loop`**,
  `geo_ships.ais_loop`, `full_scan_loop`. En el `.env`: `PROACTIVE_LEARNING_ENABLED=true`,
  `CONSOLIDATION_ENABLED=true`, `CURIOSITY_ENABLED=true`, `TEST_MODE=true`.
  - **`proactive_loop`** (amplía casos / llena huecos del vault vía `run_agent`) **consume el
    modelo de chat por su cuenta**. Con `TEST_MODE=true`, el chat y lo proactivo salen por
    **OpenRouter free (20/min, 1000/día)** → el loop de fondo puede **agotar la cuota diaria
    antes de que vos chatees**, o chocar contra el rate-limit.
  - `consolidation` corre en **local tier-1 (gratis)** — ok. `curiosity` es solo-avisar — ok.
    `playlist_watcher` consume el LLM activo con cada video nuevo (idempotente, solo nuevos).
- **Fix para 5 días free:** dos opciones:
  1. **Chat 100% local (gratis ilimitado):** `TEST_MODE=false` + `LMSTUDIO_MODEL=jarvis-text-v2`
     → el chat usa Ollama local, sin cuota. (Verificar que Ollama corra con `jarvis-text-v2`.)
  2. **Mientras no estés, apagar lo proactivo:** `PROACTIVE_LEARNING_ENABLED=false` y/o
     `PLAYLIST_WATCH_ENABLED=false`, para que nada consuma el LLM solo.
- **Nota:** cambios de `.env` **requieren reiniciar el backend**.

---

## P3 — Seguridad / gates (deuda; decisiones de Damian)

### P3-1 · 🟠 `FS_ALLOWED_ROOT` = HOME entero
- **Impacto:** en el `.env` real: `FS_ALLOWED_ROOT=C:\Users\dam`. Las tools de filesystem
  pueden leer/escribir/mover en **toda tu carpeta de usuario**, no solo el proyecto. Superficie
  de daño enorme si el modelo se equivoca o lo manipulan. `CLAUDE.md` y `ESTADO.md` (496-499)
  ya marcan esta mitigación como **barata y pendiente**.
- **Fix (una línea, cero riesgo):** acotar `FS_ALLOWED_ROOT` a
  `C:\Users\dam\Documents\JarvisRemote` (+ carpetas de proyectos que Raphael cree).

### P3-2 · 🟡 `FS_ALLOW_DELETE=true`
- **Impacto:** el borrado de archivos vía `fs_delete_path` está **habilitado** (el default del
  `.env.example` es `false`). Combinado con P3-1 (HOME entero), Raphael puede borrar archivos
  en toda tu carpeta de usuario.
- **Fix:** considerar `FS_ALLOW_DELETE=false` salvo que lo necesites activamente; o al menos
  después de acotar `FS_ALLOWED_ROOT`.

### P3-3 · 🟡 `pc_run_command` = blocklist, no sandbox
- **Impacto:** `CLAUDE.md` lo dice explícito: es una blocklist de patrones destructivos, **no
  un sandbox real**. Un comando fuera de la blocklist corre igual.
- **Fix (diseñado, sin implementar):** propuesta de container Docker para `pc_run_command` +
  `browser_*` (`backend/obsidian_vault/jarvis/propuesta-sandboxing-...md`). Requiere Docker
  Desktop (no instalado) y 2 decisiones de arquitectura (ver `ESTADO.md` 501-506).
- **Nota positiva (resuelto):** el panel/globo/mission-control **ya piden token** (`verify_read`
  / `_ws_read_ok` con `?key=`, `main.py` 226-249, 438, 458). La nota vieja de "SIN auth" quedó
  obsoleta. El gate de pentest (`authorized_targets.yaml`) y el de self-repair (líneas rojas en
  `selfrepair/guardrail.py`) están intactos.

---

## P4 — Deuda de código / features a medias (baja severidad)

- **P4-1 · Memoria, destilado LLM sin implementar:** `memory/distiller.py:142` — `# TODO Fase 2:
  llamada real al modelo`. El destilado de episodios está stubbeado.
- **P4-2 · Timestamp real por mensaje:** `memory/schema.py:39` — instrumentar el timestamp por
  mensaje en `agent.py` es un TODO (hoy usa el del turno).
- **P4-3 · Fabric reference incompleto:** `tools/fabric_reference.py:34` — `TODO: mappings de
  Yarn, no Mojang`.
- **P4-4 · Dead code:** `harness/orchestrator.py:81` — `node_by_name` se calcula y nunca se usa
  (ruff F841). Borrar.
- **P4-5 · Ruteo del AGENTE PRINCIPAL por tarea, pendiente:** hoy el ruteo de tiers aplica a
  brigadas/jobs, **no al chat**. El `difficulty_router.py` está construido pero **OFF**
  (`DIFFICULTY_ROUTER_ENABLED=false`). Falta que el chat elija modelo por dificultad.
- **P4-6 · `web_get` necesita `scrapling`:** la capa de navegación autoescalante no está
  activada (ver P0-4).
- **P4-7 · Ablación de prompts sin medir:** `SYSTEM_PROMPT_VARIANT`/`SKILLS_PROMPT_VARIANT`
  (default `full`). Falta correr el A/B (`=slim`, reiniciar, comparar) — `docs/ABLACION-system-prompt.md`.
- **P4-8 · Lint (correr `python -m ruff check backend/app --fix`):** 13 imports sin usar (F401),
  2 variables sin usar (F841), 2 f-strings sin placeholder (F541). Además, **no auto-fixeables,
  revisar a mano:** 3 × `zip()` sin `strict=` (B905 — riesgo de truncado silencioso si las
  longitudes no coinciden) y 24 × `raise ... from` faltante dentro de `except` (B904 — se pierde
  la causa original en los tracebacks). Ninguno es crítico, pero el B905 puede esconder bugs.

---

## P5 — Infra / laboratorio (diseñado, sin implementar)

- **Cyber range a medias** (`lab/RETOMAR-LAB.md`): VirtualBox + Kali + Metasploitable montados;
  quedó **Metasploitable booteando**, falta loguear, sacar IP, encender Kali, verificar
  conectividad y **tomar snapshots BASE**. Agregar `10.13.37.0/24` a `authorized_targets.yaml`
  (a mano) antes de que Raphael toque los blancos. Registrar Nessus Essentials.
- **Sandboxing en container** (P3-3): Docker Desktop sin instalar; 2 decisiones de arquitectura.
- **Defensa kernel-grade** (`lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`): diseño por fases
  (Sysmon→ETW→AMSI→ASR/AppLocker/WDAC/WFP), sin implementar.
- **Orquestación remota** (`lab/ORQUESTACION-REMOTA-DESIGN.md`): control del cyber range desde
  el celular por Tailscale; `vm_control`/`ssh_guest`/cola de misiones (spec, sin código).

---

## Plan de ataque sugerido (cuando vuelva el límite)

Orden por riesgo/dependencia:

1. **Blindar el trabajo (P0-1):** `git status` → commitear → pushear → decidir merge de la rama.
2. **Validar que todo arranca (P0-2):** reiniciar backend + tray, `pytest`, probar chat + una
   feature de cada área (memoria, geo/globo, mission-control, trading).
3. **Android (P0-3):** `gradlew installDebug`, arreglar errores de build, validar en el Moto G72.
4. **Instalar dependencias (P0-4).**
5. **Arreglar el selector que pisa el modelo (P1-1)** — es el bug que más fricción diaria causa.
6. **Diagnosticar Termux (P1-2) y cámara (P1-3)** en el celular.
7. **Acotar `FS_ALLOWED_ROOT` + revisar `FS_ALLOW_DELETE` (P3-1/P3-2)** — una línea, mucho upside.
8. **Limpieza de lint (P4-8)** con `ruff --fix` + revisar los B905 a mano.
9. Resto de deuda (P4) e infra (P5) según prioridad de negocio.

---

## Límites de esta auditoría (honestidad)

- Es **estática**: no corrió el backend ni los tests en Windows. Los ítems "verificar vigencia"
  (P1-*, parte de P0-2) vienen de `INFORME_COMPLETO.md` (jul-2026) y `ESTADO.md`, que **pueden
  estar desactualizados** — algunos bugs quizás ya se arreglaron. Confirmá en la PC.
- No audité línea por línea los ~660 archivos del backend ni el Kotlin del Android; me concentré
  en los issues conocidos, el análisis estático (ruff, limpio de sintaxis/nombres) y los módulos
  de mayor riesgo. Una pasada de `pytest` en la PC es el complemento natural de este documento.
