# Familia Raphael — Fase 0: inventario, secretos y línea base de tests

Fecha: 20/11/2026 · Constructor: Claude · Spec: "Spec: Familia Raphael (orquestador + 5 Raphaels)"

## Resultado de la puerta

**La puerta de la fase 0 pasa** (`obra/puerta-fase-0.sh` termina en 0; si algo falla termina en 2). Damián eligió A + B el 20/11:
se congeló la línea base de JarvisRemote (`linea-base-jarvis-fallas.txt`: 31 fallas + 1 timeout) y después se arreglaron todas
en la copia, con 13 commits chicos.

| Puerta | Estado |
|---|---|
| Inventario escrito | Hecho (este archivo) |
| Copias de trabajo | En `Documents\Raphael-Familia\obra\copias`, originales sin tocar |
| Secretos en el historial de git | Sin claves reales en ningún historial |
| Tests de Raphael Empresas | **Verde**: 111 de 111 (Linux, Python 3.11) |
| Tests de JarvisRemote | **Verde**: 163 archivos, 2074 passed, 0 failed, 5 skipped (Windows, Python 3.12.10) |

## 1. Copias de trabajo

- `Documents\Raphael-Familia\obra\copias\raphael\` — copia de `Documents\raphael` (11 repos + `_transferencia` + `raphael-nube.tgz`), sin `.venv` ni cachés.
- `Documents\Raphael-Familia\obra\copias\JarvisRemote\` — copia de `Documents\JarvisRemote`, sin `.venv`, cachés ni `android-app\app\build` (salida de compilación, 445 MB).
- Verificado con `rsync --dry-run`: la copia coincide con el original salvo `.git/config` (ver abajo).
- En **cada copia** se bloqueó el push: `remote.origin.pushurl = NO-PUSH-esto-es-una-copia`. Así un `git push` desde una copia falla en vez de subir algo a los repos reales. El fetch sigue apuntando a GitHub.
- `copias\_to_delete\` tiene 5 archivos temporales de una copia cortada a mitad y un pedazo de `android-app\app\build`. No se pudieron borrar (el borrado está apagado en esta sesión): se pueden borrar a mano.
- Las copias traen los archivos ignorados del original, incluidos `backend\.env`, sus 12 `.env.bak-*` y `backend\certs\key.pem` de JarvisRemote, y `raphael-android\claves\` (keystore y su `firma.properties`). Están ignorados por git, pero son secretos reales en disco: no comprimas ni compartas la carpeta `copias` tal cual.
- Los originales no se modificaron. Solo se leyeron (y el venv original de JarvisRemote se usó como intérprete, sin escribir `.pyc`).
- Para iterar rápido hubo una tercera copia temporal en la máquina virtual de trabajo (se borra sola al cerrar la sesión); los commits se pasaron de ahí a `copias\JarvisRemote`.

## 2. Raphael Empresas (`Documents\raphael`)

Cada `raphael-*` es un repo git propio (cuenta `damianzupel-commits`). Python ≥ 3.11. Ningún repo de brigada importa a otro: todos dependen solo de `raphael-harness`.

| Repo | Versión | Commits | Qué es | Tests |
|---|---|---|---|---|
| raphael-harness | 0.4.0 | 4 | Contrato, Policy Engine, almacén SQLite, bus de eventos, capa de modelos, uso/tope, cargador, CLI | 21 ✔ |
| raphael-orquestador | 0.3.0 | 4 | Ruteo de mensajes a brigadas + secretario con IA (`agente.py`) y por reglas (`secretaria.py`) | 28 ✔ |
| raphael-atencion | 0.1.0 | 2 | Brigada Atención | 5 ✔ |
| raphael-agenda | 0.1.0 | 2 | Brigada Agenda | 5 ✔ |
| raphael-cobros | 0.1.0 | 2 | Brigada Cobros | 4 ✔ |
| raphael-encargos | 0.1.0 | 2 | Brigada Encargos | 9 ✔ |
| raphael-avisos | 0.1.0 | 2 | Brigada Avisos | 2 ✔ |
| raphael-servidor | 0.4.0 | 6 | FastAPI: panel, login, `/webhook/meta`, licencia, backups cifrados, catálogo de brigadas descargables | 28 ✔ |
| raphael-relay | 0.1.0 | 1 | Nube: recibe webhooks de Meta y los encola por instalación | 4 ✔ |
| raphael-central | 0.1.0 | 1 | Licencias y panel de soporte | 5 ✔ |
| raphael-android | 0.1.0 | 1 | App WebView (Java), avisos por polling | sin tests |

La instalación de prueba en `Documents\Raphael-Empresas\piezas` tiene las mismas versiones que los repos.

### Piezas del harness (lo que el spec llama "harness")

- `contrato.py` — `CONTRATO = 1` (entero). Clases `Pieza`, `Brigada`, `Orquestador`, `Mensaje`, `Accion`, `Respuesta`, `Charla`, `Nivel` (`automatico`/`aprobacion`/`humano`).
- `cargador.py` — descubre piezas por entry points (`raphael.brigadas`, `raphael.orquestador`) o por carpeta (`RAPHAEL_DEV`); descarta las que declaran otro contrato.
- `harness.py` — `Harness`, `Contexto` (por pieza) y `ContextoDuena` (aprobar, rechazar, resolver, ordenar, escribir). Pendientes de aprobación, registro de auditoría, tope de uso.
- `politicas.py` — Policy Engine. Nivel efectivo = el **más estricto** entre el global, el de la brigada y el del perfil.
- `almacen.py` — SQLite con `Espacio` por pieza.
- `eventos.py` — bus con límite de profundidad.
- `modelos.py` + `modelos.yaml` — plan → rol → proveedor (OpenAI-compatible por HTTP). Roles actuales: `intencion`, `redaccion`, `resumen`, `secretaria`.
- `perfil.py` — perfil de empresa en pydantic (empresa, plan, brigadas, información, cobros, encargos, agenda, límites, políticas).

### Estado de git a tener en cuenta

- `raphael-servidor` tiene cambios **sin commitear** (app.py, config.py, index.html y 2 tests) y la carpeta `despliegue/nube/` (con `instalar-nube.sh` y `actualizar-nube.sh`, que el spec usa como base) **sin agregar al repo**. Los tests pasan con esos cambios.
- `raphael-android` tiene cambios sin commitear (versión 0.2.0 y `SERVIDOR_FIJO` en `app/build.gradle`).
- Mientras no se commiteen, el CI de GitHub no los ve.

## 3. JarvisRemote (`Documents\JarvisRemote`)

Un solo repo, 235 commits, último `10cf2f4` del 17/11/2026. Backend Python 3.12 (FastAPI) pensado para **Windows**. No tiene CI (`.github` no existe); hay un hook de pre-commit que regenera `CONTEXTO-MAESTRO-RAPHAEL.md`.

### Motor de brigadas y orquestador (lo que pide inventariar la fase 0)

Todo vive en `backend\`:

| Pieza del spec | Dónde está | Notas |
|---|---|---|
| Esquema de brigada (brigade spec) | `brigades\spec.py` | `BrigadeSpec`, `AyudanteSpec`, `RouteRule`, escena de validación. Solo dataclasses. |
| Motor genérico de jefe | `brigades\engine.py` (`GenericChief`) | Planifica → delega en ayudantes efímeros en paralelo → recibe `ResultadoAyudante` → sintetiza → `ReporteInterno`. Timeouts y fallos aislados. |
| Molde de jefe persistente | `brigades\chief.py` (`BrigadeChief`, `ChiefConfig`) | Mini-loop de tools con allowlist y estado en disco. |
| Contratos | `brigades\contracts.py` (`VERSION = 1`) | `ResultadoAyudante` y `ReporteInterno`, validación estricta, límites de tamaño, reporte degradado, "todo es dato". Solo stdlib. |
| Registro de brigadas | `brigades\registry.py` | Declarativas: `cerebro`, `investigacion`, `seguridad`, `video`. Legacy: `scout`. Más las creadas por borrador (`factory.py` + `draft_store.py`, activación firmada por hash). |
| Modelo por rol | `brigades\config.py` (`resolve_role_model`) | Overrides por variables de entorno: `ORQUESTADOR_*`, `ORQUESTADOR_MANDO_*`, `ORQUESTADOR_VOZ_*`, `BRIGADE_<ID>_*`, `AYUDANTE_<ID>_*`. Depende del SDK `openai` (AsyncOpenAI). |
| Catálogo de tools y privilegios | `brigades\tool_catalog.py` | Lee `app\tools` por AST; clasifica `ok` / `sensible` / `denegada`. |
| Turno | `orquestador\turno.py` | Jefe → reporte → voz → `final`. Solo el orquestador le habla al usuario. |
| Mando (reparto y conclusión) | `orquestador\mando.py` | Reparto con dependencias entre brigadas; código controla lo que propone el modelo; sin modelo hay salida. |
| Voz | `orquestador\voz.py` | Verificador de fidelidad determinista + plantilla de respaldo. Persona y directrices de Damián. |
| Ruteo | `orquestador\routing.py` | Override `/id`, reglas con peso, LLM solo si hay empate, default Cerebro. |
| Servidor del orquestador | `orquestador\server.py`, `launcher.py`, `watchdog.py`, `slim_tools.py` | Escucha solo en 127.0.0.1 con token efímero. `slim_tools` carga solo las tools que usan los jefes. |
| Tools | `app\tools\` (≈40 módulos, `register_tool`) | Incluye shell, escritorio, celular, pentest activo, etc. |

### Brigadas y piezas que el spec quiere reutilizar

| Spec | Código real en JarvisRemote | Ojo |
|---|---|---|
| Seguridad → Auditor de código | `app\harness\audit_brigade.py` (DAG E1–E7) + `app\tools\audit_brigade.py`, `app\security\`, `app\quality\`, `app\findings\` | **No** es `brigades\seguridad.py`: esa es la brigada de pentest **activo** (nmap, ZAP, sqlmap), que el spec deja fuera del VPS. |
| Seguridad → Antimalware | `app\malware\` (1669 líneas) + `app\tools\malware.py` | YARA + ClamAV + watchdog/psutil; 6 archivos dependen de Windows (Sysmon, DPAPI, etc.). |
| Seguridad → Forense | ayudante `investigacion-forense` + `app\investigation\` (3459 líneas) | Claves Ed25519 protegidas con DPAPI (Windows). |
| Innovación → Scout | `scout\` + ayudante `investigacion-scout` | Necesita `BRAVE_SEARCH_API_KEY` (la validación de Scout quedó "sin validar" por eso). |
| Innovación → Cerebro | `brigades\cerebro*.py`, `brigades\memory_service.py`, `app\obsidian\` | Última validación real: **pasa 4/4** (16/11). Tests de regresión ya existen: `test_cerebro_fixes.py` (mezcla de notas) y `test_validation_cerebro.py` (invención). |
| Marketer → Video | `brigades\video.py` + `app\video_edit.py`, `app\video_proyecto.py` | ffmpeg de a uno, carpeta fija, original intacto. |
| Marketer → Instagram | `app\publicaciones.py` | Ninguna tool publica; publicar exige `aprobar_y_publicar` desde el endpoint de Damián. Probado solo con cliente simulado. |

### Lo que importa para correr en el VPS (Linux)

- El monolito **no importa en Linux**: `app\tools\__init__.py` importa `desktop.py` (pywinauto) y `forms\credential_store.py` (`win32crypt`) sin guardas. Con `pytest` en Linux, los 1300+ tests caen al importar.
- En cambio, con el arranque liviano (`orquestador\slim_tools.install()`), **sí importan en Linux** `brigades.contracts`, `spec`, `engine`, `registry` y `orquestador.mando`, `turno`, `routing`, `voz` (probado con Python 3.12).
- Hay un plan previo de migración a Linux en `docs\SPEC-MIGRACION-LINUX-2026-10-19.md` (DPAPI → keyring, pywinauto → xdotool, etc.) que sirve de guía para los adaptadores.
- Ojo con el nombre: JarvisRemote también tiene `backend\app\harness\` (registro de modelos, DAG de auditoría), que **no** es `raphael-harness`.

## 4. Secretos en el historial de git

Se revisó el historial completo de los 12 repos: nombres de archivo de todos los commits y el contenido de todas las líneas agregadas, buscando patrones de claves (Anthropic, OpenAI, OpenRouter, NVIDIA, Groq, GitHub, Google, Meta, AWS, Slack, Hugging Face, Telegram, claves privadas PEM) y asignaciones del tipo `token = "…"`.

- **Ningún `.env` real ni clave real en ningún historial.** Solo `.env.example` (con valores de ejemplo) en JarvisRemote.
- Coincidencias revisadas una por una y descartadas: la clave de ejemplo de la documentación de AWS (`AKIAIOSFODNN7EXAMPLE`) en una nota del vault, un secreto de ejemplo en un dataset de prompts (`experiments\laya`), hashes de PyGoat (app vulnerable a propósito) en reportes de auditoría, y un marcador `sk-or-v1-<MAYÚSCULAS>` en `proyectos\co-host-stream\mvp\.env.example`.
- En disco (ignorados por git, no están en el historial): `backend\.env` y 12 `.env.bak-*`, `backend\certs\*.pem`, `proyectos\co-host-stream\mvp\.env`, `raphael-android\claves\*`. Bien ignorados.
- **Para revisar antes de pushear:** `CLAUDE.md` de JarvisRemote dice que el repo es **público**. Damián dice que hoy es privado. No se verificó en GitHub (pendiente de la sección 14 del spec).

## 5. Línea base de tests

### Raphael Empresas — verde

Corrido en la copia, Linux, Python 3.11.18, cada repo por separado como en su CI: **111 passed, 0 failed**.
`raphael-servidor` tarda unos 2,5 minutos sobre la carpeta de Windows (los tests de la tienda copian archivos).

`ruff` con las reglas por defecto marca entre 6 y 47 avisos por repo (161 en total, casi todos autocorregibles). El CI actual no corre `ruff`. No se corrigió nada: queda para la fase 7.

### JarvisRemote — verde después de los arreglos

Corrido en Windows, sobre la copia, con el Python del venv original (3.12.10), **un proceso por archivo** (en Windows
`pytest-timeout` corta todo el proceso cuando un test pasa de 15 s). Se lanza con `fase0\correr-tests-jarvis.bat`.

- Línea base (antes): 162 archivos · 2001 passed · 31 failed · 4 skipped · 1 archivo cortado por timeout. Log: `tests-jarvis-windows-linea-base.log`; lista: `linea-base-jarvis-fallas.txt`.
- Ahora: **163 archivos · 2074 passed · 0 failed · 5 skipped**. Log: `tests-jarvis-windows.log`.

Ajustes de entorno solo para estas corridas (no tocan código ni tests):
- `OBSIDIAN_VAULT_PATH` → carpeta temporal, para que ningún test escriba en `Vault-Fenix`.
- `FS_ALLOWED_ROOT` → `%TEMP%`.
- `os.symlink` falla al instante (plugin `fase0_sin_symlink.py`): en esta PC se **cuelga** en vez de fallar y tumbaba la suite.
- Por esos ajustes, 3 de los 5 skips son del entorno y no del código: 2 tests de symlinks y 1 que solo corre sin `FS_ALLOWED_ROOT`. Los otros 2 piden cosas que no hay (NodeGoat clonado, `RUN_VOICE_REAL=1`).

Arreglos (13 commits en `copias\JarvisRemote`, rama `master`, desde `10cf2f4`; ninguno pusheado):

| Commit | Qué |
|---|---|
| 83b753e | Tests de prompt de sistema esperan la persona (`_with_persona`) y la personalización |
| 9363ab6 | Tests del reporte para cliente prueban el pipeline lineal directo (antes le pegaban a los modelos reales de la brigada) + test de que cae al lineal |
| 350f72d | Tests async de chat_link y mission_control usan `anyio` (estaban con `asyncio` sin el plugin) |
| a59dea3 | El Centro de Mando tiene 10 brigadas (suma Contenido, futura) |
| 43db64f | Las tools `video_*` son de la brigada de Video, no de los skills del agente |
| f462578 | El skill `code_delegation` se retiró el 30/09; el test lo documenta |
| be84752 | `test_llm_client` no lee el `.env` real en el subproceso |
| 677607a | Una estación sin override usa el primario de su tier |
| 9a35e46 | `test_feedback` registraba el primer incremento en vez del último |
| 29ecb40 | El fallback de tier se prueba con una lista propia (no depende del `.env`) |
| f0b6a76 | **Código:** vuelven las reglas YARA (`starter.yar`), con EICAR en hexadecimal |
| 0fc6b51 | Vuelve `test_malware_yara_scanner.py` (7 tests), con EICAR armado en dos partes |
| 1408064 | Los tests con ffmpeg real tienen 120 s de margen |

Doce commits son de tests desactualizados o mal aislados. Uno arregla código de verdad: **el antimalware estaba sin reglas YARA
desde el 24/08**. `starter.yar` tenía el texto EICAR literal, el antivirus de Windows borró el archivo (y su test), y el commit
`00c4c8a` ("respaldo del trabajo del día") registró el borrado. En tu original sigue pasando: `JarvisRemote\backend\app\malware\rules\`
está vacía.

Hallazgo para tener en cuenta (no se arregló, no hace fallar nada): **la suite de JarvisRemote escribe en `backend\data` real**.
Una corrida dejó 311 archivos nuevos (memoria episódica de sesiones de test) y modificó 6 (`model_registry.json`,
`ingestion_sources.json`, `retrieval_strength.json`, `brigades\cerebro.json`, `episodic_memory\memory_log.jsonl`,
`watchdog\intervenciones.jsonl`). Cada vez que corrés `pytest` en tu original, ensucia tus datos reales (incluida la memoria que
usa Cerebro). En la copia se restauraron desde el original y lo nuevo se movió a `copias\_to_delete\datos-escritos-por-tests\`.
Conviene aislarlo en `tests\conftest.py` cuando se envuelva Cerebro (fase 4).

## 6. Diferencias entre el spec y el código (regla 9: gana el código que anda)

1. **Pisos de autonomía.** El spec dice "sin pisos fijos: el cliente puede dejar cualquier acción en automático". El Policy Engine de `raphael-harness` hace lo contrario: "el perfil puede endurecer, nunca relajar", y las acciones con piso (por ejemplo `devolver_dinero` en `humano`, `confirmar_pago` en `aprobacion`) no bajan. Cumplir el spec exige cambiar el harness o envolverlo en `raphael-familia-core`, y el spec dice que el harness no se modifica. **Lo tiene que decidir Damián.**
2. **Versión de contrato.** El spec pide versionado semántico. El harness usa un entero (`CONTRATO = 1`) y rechaza cualquier pieza con otro número. JarvisRemote también usa un entero (`VERSION = 1`).
3. **Roles de modelo.** El spec usa `mando`, `voz`, `ruteo`, `jefe`, `cocinero`, `efimero`. El `modelos.yaml` del harness usa `intencion`, `redaccion`, `resumen`, `secretaria`, y JarvisRemote resuelve modelos por variables de entorno, no por YAML. Habrá que mapear.
4. **Modelos locales.** El spec dice "sin modelos locales, todo por API". El plan `privado` del harness usa `local` (Ollama), y Cerebro y Forense de JarvisRemote corren con modelo local y embeddings de LM Studio.
5. **Seguridad pasiva.** La "brigada de Seguridad" de JarvisRemote (`brigades\seguridad.py`) es de pentest activo. Para el VPS se reutiliza la brigada de **auditoría** (`app\harness\audit_brigade.py`) y no se carga `seguridad.py` ni sus tools (`nmap_scan`, `zap_scan`, `sqlmap_scan`).
6. **Publicación en Instagram.** El spec describe que Meta descarga el archivo desde una URL pública firmada. `app\publicaciones.py` usa carga resumible en 3 pasos (contenedor → subir bytes → publicar), sin URL pública. Las dos formas existen en la API; se mantiene la del código salvo que decidas otra.
7. **Windows.** El spec da por hecho que lo de JarvisRemote se envuelve tal cual en el VPS. Antimalware, Forense y el monolito dependen de Windows (DPAPI, pywinauto, Sysmon). Los adaptadores van a tener que reemplazar esas dependencias.
8. **`instalar-nube.sh`** existe, pero no está commiteado en `raphael-servidor`.

## 7. Decisiones que tomé

- Copias en `Documents\Raphael-Familia\obra\copias` con el push bloqueado.
- En los originales no modifiqué nada. En la copia de JarvisRemote, solo los 13 commits de la sección 5; en las copias de Empresas, nada.
- Copias movidas de `Documents\Familia-Raphael` (donde empecé) a `Documents\Raphael-Familia\obra` cuando llegó `PROMPT-OPUS.md`. `Documents\Familia-Raphael` quedó vacía y no la pude borrar.
- **Antes de recibir la regla 4 de `PROMPT-OPUS.md` leí parte de `backend\.env` de la copia:** los nombres de las variables y el valor de tres rutas (`FS_ALLOWED_ROOT`, `OBSIDIAN_VAULT_PATH`, `FS_DENIED_PATHS`), para que los tests no escribieran en tu vault. No leí ni imprimí ninguna clave, y los `.env.bak-*` solo los listé por nombre. Desde que llegó la regla no volví a abrir ningún `.env`.
- Un test que falló imprimió el principio y el final de tu clave de NVIDIA en el log; lo taché en todos los logs.
- Corrí JarvisRemote en Windows con el intérprete del venv original, sin escribir `.pyc`, y con el vault y la raíz de archivos redirigidos a `%TEMP%`.

## 8. Antes de la fase 1

- **Pisos de autonomía** (sección 6, punto 1): `ESTADO.md` confirma "sin pisos", pero el Policy Engine de `raphael-harness` no deja bajar niveles y el harness no se modifica. Si no decidís otra cosa, en la fase 1 lo resuelvo en `raphael-familia-core` envolviendo el Policy Engine (sin tocar el harness) y lo marco en el informe.
- **Commits pendientes en los originales** (vos): `raphael-servidor` (cambios + `despliegue/nube/` sin agregar) y `raphael-android`.
- **Reglas YARA en tu original:** si querés el antimalware andando en tu PC, hay que llevar `starter.yar` (versión en hexadecimal) al original. No lo hice (los originales no se tocan).
- JarvisRemote es privado (confirmado por Damián el 20/11); el `CLAUDE.md` que dice "público" está desactualizado.
