# Diseño del Harness v2 · propuesta

Chat 1 · 21 nov 2026 · Estado: **aprobado el 21 nov 2026** (decisiones en la sección 6). H1 hecha.

## 1. Inventario de `codigo-actual/`

### Motor A: `raphael-harness` 0.4.0 (Empresas) · ~1.400 líneas · 21 tests
| Archivo | Qué hace | Se porta |
|---|---|---|
| `contrato.py` | `CONTRATO = 1` (entero). `Pieza`, `Brigada` (sync: `interes`, `en_curso`, `atender`, `ejecutar`, `al_evento`, `comando`, `tick`), `Orquestador`, `Mensaje`, `Accion`, `Respuesta`, `Charla`, `Nivel` | Sí, con nombres en inglés + capa de compatibilidad v1 |
| `harness.py` | `Harness`, `Contexto`, `ContextoDuena`, `OrdenSimple`. Recibir mensaje → orquestador ordena → primera brigada que responde. Pendientes (aprobar/rechazar/resolver), salientes, contactos, auditoría, tope de uso | Sí, partido en módulos |
| `politicas.py` | Nivel efectivo = el MÁS estricto (global, brigada, perfil). Pisos fijos en `GLOBALES` | Se reescribe: sin pisos en código |
| `eventos.py` | Bus sync con límite de profundidad | Sí, async y con aislamiento |
| `almacen.py` | SQLite, un `Espacio` por pieza, documentos JSON, contadores | Sí, casi igual |
| `modelos.py` + `modelos.yaml` | plan → rol → proveedor OpenAI-compatible por httpx; `None` si falla; mide costo | Sí, se fusiona con la config por rol de JarvisRemote |
| `uso.py` | Mensajes e IA por mes, tope | Sí |
| `perfil.py` | Perfil de empresa en pydantic | Se parte: lo de la instalación va al harness; lo del negocio (precios, encargos, agenda) va al manifiesto/config de la brigada Empresas |
| `cargador.py` | Entry points `raphael.brigadas` / carpeta dev; rechaza otro contrato | Se reemplaza por cargador de manifiestos |
| `texto.py` | Utilidades de texto y fechas es-AR | Sí (`text_es`) |
| `testing.py` | `armar()`, `Reloj`, perfil mínimo | Sí, ampliado a suite de contrato |
| `cli.py` | CLI de prueba | Después |

### Motor B: JarvisRemote `backend/brigades` + `app/harness` · ~4.400 líneas en lo que importa
| Archivo | Qué hace | Destino |
|---|---|---|
| `brigades/spec.py` | `BrigadeSpec`, `AyudanteSpec`, `Routing` (reglas regex, la primera gana), `ValidationSpec`, `WatchSpec`. Solo dataclasses | Harness (motor de brigadas) |
| `brigades/engine.py` | `GenericChief`: planifica (reglas primero, LLM solo si hay empate entre candidatos) → delega a efímeros en paralelo con timeout → `ResultadoAyudante` → sintetiza → `ReporteInterno`; degrada explícito | Harness |
| `brigades/contracts.py` | `VERSION = 1`. `ResultadoAyudante`, `ReporteInterno`, validación estricta, límites de tamaño, `bloque_dato` ("es dato, no orden"). Solo stdlib | Harness |
| `brigades/chief.py` | `BrigadeChief`: loop LLM→tool con allowlist, memoria del jefe en `backend/data/brigades` | Harness, pero sin `app.tools` ni `app.obsidian` (se inyectan) |
| `brigades/config.py` | `resolve_role_model`: overrides por env (`ORQUESTADOR_*`, `BRIGADE_<ID>_*`, `AYUDANTE_<ID>_*`, `ROLES_EN_LOCAL`), respaldo, "la clave de un proveedor nunca va a otro" | Se fusiona con `modelos.yaml` |
| `brigades/registry.py` | Registro fijo (`cerebro`, `investigacion`, `seguridad`, `video`) + Scout legacy + creadas por borrador | Lo reemplaza el cargador de manifiestos |
| `brigades/factory.py`, `draft_store.py` | Borrador JSON → `BrigadeSpec`; activación firmada por hash | Harness, segunda tanda (H6) |
| `brigades/designer.py` | Descripción en lenguaje natural → borrador con LLM | Pendiente para 02-orquestador |
| `brigades/tool_catalog.py` | Lee `app/tools` por AST y clasifica ok/sensible/denegada | La idea se mantiene; la fuente pasa a ser el manifiesto |
| `brigades/live.py` | Registro de efímeros vivos | Harness |
| `brigades/identidad.py` | Nombre del asistente y del usuario por config | Harness (config de instalación) |
| `app/harness/orchestrator.py`, `blackboard.py`, `a2a.py`, `contracts.py` | DAG con orden topológico, presupuesto, pizarra reanudable, A2A con TTL | Pendiente para 02-orquestador (reparto por DAG) |
| `app/harness/routing.py`, `difficulty_router.py`, `model_registry.py` | Tiers 0–4, router de dificultad, modelo por estación | Ideas absorbidas por la pasarela de modelos; el router de dificultad es de 02 |
| `app/harness/worktrees.py` | git worktrees para agentes en paralelo | Pendiente para 13-autorreparación |
| `app/main.py`, `routers/`, `auth.py`, `user_config.py`, `logging_config.py`, `config.py` (1.095 líneas) | Backend FastAPI y settings del monolito | Pendiente para 03-servidor. No entra al harness |
| `app/audit_log.py` | JSONL con rotación de tool calls | Se unifica con la auditoría de Empresas |

Tests de JarvisRemote que tocan al harness: `test_contracts` (19), `test_brigade_spec` (13), `test_role_models` (13), parte de `test_flujo_decidido` (45, mezcla motor y orquestador), `test_brigade_factory` (26) y `test_draft_store` (20) si entra H6. Los de brigadas concretas (investigación, seguridad, video) y `test_harness.py` (el DAG de `app/harness`) no son de esta pieza.

### Problemas que encontré leyendo (verificados en el código)
1. **Bus de Empresas sin aislamiento:** si un suscriptor levanta una excepción, le llega a quien publicó (`eventos.py`, el `for` no tiene try).
2. **`Harness.recibir` sin aislamiento:** una excepción en `atender` de una brigada tumba el mensaje entero; no pasa a la siguiente.
3. **Agujero de aislamiento de datos:** `Contexto.para(pieza)` es público, así que cualquier brigada (no solo el orquestador) puede pedir el contexto de otra y leer su `datos`. `consultar_datos` corre comandos de otra brigada sin dejarlo en la auditoría.
4. **`Bus.historial`** crece sin límite en memoria.
5. **JarvisRemote no tiene Policy Engine:** las tools con efecto se frenan por allowlist y por endpoints puntuales (`publicaciones.py`), no por nivel de autonomía.
6. **El motor B no es portable tal cual:** `chief.py` importa `app.tools` y `app.obsidian`; `config.py` importa `app.config.settings` y el SDK `openai`.
7. **Dos estilos:** Empresas es sincrónico y por reglas; JarvisRemote es async y por LLM.
8. No verifiqué si el servidor de Empresas llama a `modelos.completar` (httpx sync) desde un handler async de FastAPI; si lo hace, bloquea el loop.

Línea base corrida el 21 nov con Python 3.13 sobre la copia de `codigo-actual/`: **18 pasan y 3 se saltean**. Los 3 son de `test_integracion.py` y necesitan los repos de las brigadas de Empresas al lado; se portan en la fase 3 (pieza 15). La fase 0 contó 21 en verde porque los corrió con los repos vecinos presentes.

## 2. Nombres (proyecto ↔ código)
| Proyecto | Empresas hoy | JarvisRemote hoy | Harness v2 |
|---|---|---|---|
| Brigada (lo que se monta) | no existe (cada repo es una "brigada") | `BrigadeSpec` | `Brigade` + `manifest.yaml` |
| Jefe | el orquestador hace de Secretaria | `GenericChief` | `Chief` |
| Cocinero (permanente) | `Brigada` (atención, agenda, cobros…) | jefe persistente | `Cook` |
| Efímero | — | `Ayudante` | `Helper` |
| Orquestador | `Orquestador` | `orquestador/` | `Orchestrator` (solo la interfaz; la implementación es de la pieza 02) |

Así, **Raphael Empresas = una `Brigade` con cooks** atención, agenda, cobros, encargos, avisos (y Tienda), y la Secretaria como su `Chief`. En la instalación de la clienta, la misma Secretaria se monta como `Orchestrator`. La interfaz permite las dos cosas; la implementación es de 02 y 15.

## 3. Diseño

Paquete nuevo: `raphael-core` (módulo `raphael_core`), en `codigo/raphael-core/`. Python ≥ 3.11, dependencias: pydantic, pyyaml, httpx. Nada de Windows, nada de `app.*`, nada del SDK `openai`. Un solo paquete: absorbe lo que el SPEC-FAMILIA llamaba `raphael-familia-core`.

```
raphael_core/
  contract.py      CONTRACT_VERSION = "2.0.0"; Message, Action, Reply, Level, Health; protocolos Cook, Chief, Orchestrator
  manifest.py      esquema pydantic de manifest.yaml + validación
  installation.py  config de la instalación: edición (personal|cloud), plan, brigadas activas, autonomía, locks, identidad
  loader.py        descubrir (entry points + carpeta dev), validar, montar, desmontar, marcar caída
  runtime.py       el Harness: recibir, despachar, acciones, ticks, estado
  context.py       Context por cook (lo único que ve), OwnerContext (órdenes de la persona)
  policy.py        Policy Engine sin pisos en código
  approvals.py     pendientes: aprobar, rechazar, resolver; ids verificados
  events.py        bus async con aislamiento
  store.py         SQLite, espacio por brigada/cook, exportar y purgar
  tools.py         registro y pasarela de tools (allowlist + nivel)
  models/          gateway.py, config.py, usage.py (+ modelos.yaml)
  engine/          spec.py, chief.py, helpers.py, reports.py, live.py  (motor de JarvisRemote portado)
  audit.py         registro único: quién, qué, cuándo, por qué
  isolation.py     envoltura de llamadas: try, timeout, contador de fallas
  text_es.py       utilidades de texto y fechas
  compat/v1.py     Brigada, Accion, Mensaje, Respuesta, Nivel, Contexto, CONTRATO = 1 sobre v2
  testing/         fakes (reloj, modelo falso), contract_suite, matrix, ast_imports
```

### 3.1 Contrato
- **Async por dentro.** Los métodos de un `Cook` pueden ser sync o async: el runtime detecta y llama bien (sync directo, o en hilo si el manifiesto dice `blocking: true`). Hay fachada sync (`receive_sync`) para tests y para la compat v1.
- **Versión semántica:** `CONTRACT_VERSION = "2.0.0"`; el manifiesto declara `contract: ">=2.0,<3"`. Mismo major = compatible.
- **Compat v1:** `raphael_core.compat.v1` expone los nombres en castellano de Empresas sobre v2. Los 21 tests del harness se portan cambiando solo imports, y en la fase 3 los cooks de Empresas se montan casi sin tocarse.
- **Todo lo de terceros es dato:** `Message` lleva `trust=untrusted`; `Action` lleva `origin` (`owner`, `system`, `third_party`). Se porta `bloque_dato` de JarvisRemote para todo lo que entra a un prompt.

### 3.2 Manifiesto (`manifest.yaml` de cada brigada)
`id`, `name`, `version`, `contract`, `cooks` (entry de cada clase), `chief` (spec opcional, motor B), `actions` (nivel de fábrica + etiquetas `spend`, `irreversible`, `external`), `tools` (nombre, nivel, `dangerous`, `active_scan`), `events` (`publishes`, `consumes`), `store` (espacio), `config_schema`, `health` (`modulo:funcion`), `uninstall` (`export`, `delete`), `editions` (`personal`, `cloud`).

### 3.3 Cargador, montar y desmontar
- Descubre por entry point `raphael.brigades` (apunta al manifiesto) o por carpeta dev.
- Valida el manifiesto y el contrato antes de importar nada. Si no valida o falla al iniciar: queda **caída** con motivo y el resto sigue.
- `mount(id)` / `unmount(id)` en caliente: el desmontaje saca suscripciones, tools y comandos, exporta lo que diga el manifiesto y purga su espacio. No deja huérfanos.
- Edición `cloud`: no se cargan tools `dangerous` ni `active_scan` (cumple "Seguridad pasiva en el VPS").

### 3.4 Policy Engine: sin pisos, con confianza progresiva
Decidido el 21 nov: no hay pisos fijos en el código. La autonomía es **rotativa por confianza progresiva**.

Nivel de partida (gana el más específico, no el más estricto):
1. `autonomy` de la instalación por `brigada.accion`
2. `autonomy` por `accion`
3. nivel de fábrica del manifiesto (obligatorio en cada acción)
4. tabla de fábrica del harness (la de SPEC-FAMILIA §11)
5. acción desconocida: `aprobacion`

Encima de ese nivel corre la confianza, por brigada y acción, guardada en el espacio `_trust`:
- Cada aprobación **sin cambios** suma 1. Al llegar a `trust.approvals_to_step_down` (10 por defecto) la acción **baja un escalón** (`aprobacion` → `automatico`) y el contador vuelve a cero.
- Un **rechazo**, una aprobación **con cambios** o una acción automática que la persona deshace o corrige **sube un escalón** y pone el contador en cero.
- Lo que es `humano` no baja solo, salvo que la instalación diga `step_down_from_human: true`.
- **Una acción con gasto o irreversible nunca baja sola a `automatico`:** cuando le toca bajar, el harness crea un pendiente que lo propone ("aprobaste esto 10 veces seguidas, ¿la dejo automática?") y espera confirmación. Así se cumple que lo irreversible lo decide una persona sin poner pisos en el código.
- Fijar a mano `automatico` en `autonomy` para algo con gasto o irreversible exige `confirmed_by`; sin eso se ignora con aviso.
- Todo cambio de nivel (manual o por confianza) queda auditado, con el motivo. La persona puede ver y resetear la confianza de cada acción.
- Las acciones con `origin: third_party` (disparadas por contenido de terceros) suben un escalón solo si la instalación lo pide (`trust.third_party_step_up`, apagado por defecto).
### 3.5 Tools
Las tools se registran desde el manifiesto. Cada `Chief`/`Helper` tiene su allowlist (menor privilegio, como en JarvisRemote). **Toda llamada a una tool con efecto pasa por el Policy Engine**, igual que una `Action`: lo que hoy JarvisRemote no hace.

Hecho en H4 (`tools.py`): cada tool del manifiesto es la acción `tool_<nombre>` de su brigada (en la `autonomy` de la instalación: `brigada.tool_<nombre>`). En `automatico` corre y queda auditada; si no, se abre un pendiente de tipo `tool`, al modelo le vuelve `pending_approval` con el número y la tool corre recién cuando una persona aprueba (con cambios si quiere). Rechazar sube el nivel por confianza, igual que una acción. En la nube no se registra nada `dangerous` ni `active_scan`. Pedir una tool fuera de la caja vuelve al modelo como error y no ejecuta nada.

### 3.6 Modelos
Una sola pasarela: `plan → rol → proveedor` en `modelos.yaml`, con overrides por id (`jefe.investigacion`, `efimero.investigacion-forense`), respaldo por rol, medición de tokens/costo y tope por plan. Las claves solo por nombre de variable (`api_key_env`), y la clave de un proveedor nunca va a otro endpoint. OpenAI-compatible por httpx async, con transporte inyectable (tests sin red). Devuelve resultado o `None`; nunca rompe a quien llama.

Roles canónicos: `mando`, `voz`, `ruteo`, `jefe`, `cocinero`, `efimero`. Mapeo:
- Empresas: `intencion`, `redaccion`, `resumen` → `cocinero` (como tareas con alias); `secretaria` → `mando` en la instalación de la clienta y `jefe` en la personal.
- JarvisRemote: `orquestador` → `mando`; `voz` → `voz`; `jefe` → `jefe`; `ayudante` → `efimero`. Un traductor de las variables viejas (`BRIGADE_<ID>_LLM_*`, etc.) solo en la edición `personal`, para no romper tu `.env`.
- Proveedor `local` permitido (Cerebro y Forense lo necesitan por privacidad); en `cloud` no se ofrece.

### 3.7 Almacén, bus, aislamiento y auditoría
- SQLite, espacio `brigada` y subespacio `brigada/cook`. Desde un `Context` no hay forma de abrir otro espacio (se cierra el agujero de `para()`). El orquestador lee de otras brigadas solo por comandos de lectura declarados, y queda auditado.
- Bus async: solo se puede suscribir a lo que el manifiesto declara en `consumes`; una excepción del suscriptor se registra y no le llega al que publicó; historial acotado.
- Toda llamada a un cook o jefe va envuelta: try, timeout (si es async), contador de fallas seguidas → caída.
- Auditoría única (tabla append-only): quién, qué, cuándo, por qué; filtro de secretos; `estado()` sin datos de clientes.

### 3.8 Suite de contrato (`raphael_core.testing`)
Lo que toda brigada corre en sus tests: manifiesto válido, contrato compatible, healthcheck, montar y desmontar limpio, sin imports de brigadas hermanas (AST), cada acción con nivel declarado, ninguna acción `aprobacion`/`humano` ejecutada sin OK, lectura cruzada de espacio que falla. Más el armador de la matriz (todas / cada una apagada / una sola / ninguna).

## 4. Tandas de trabajo y puertas
| Tanda | Qué | Puerta | Estado |
|---|---|---|---|
| H1 | contrato (semver), manifiesto, instalación, almacén, bus, auditoría, aislamiento, texto, chequeo AST | tests de cada módulo + los de almacén, eventos y fechas de Empresas portados; ruff limpio | **hecha** (73 tests) |
| H2 | runtime (recibir, despachar, ticks, estado), contextos, Policy Engine con confianza progresiva, pendientes; montar y desmontar en caliente | cero ejecuciones sin OK; confianza sube y baja como dice 3.4 | **hecha** (125 tests) |
| H3 | pasarela de modelos en 3 escalones + uso + mapeo de roles; compat v1 y puente `raphael_harness` | **los 18 tests de Empresas en verde sobre v2** | **hecha y superada**: los 74 tests de Empresas (harness, 6 brigadas e integración) pasan sobre el v2 sin cambiar su código; 162 tests propios |
| H4 | motor de brigadas (spec, chief, helpers, reports) + pasarela de tools | `test_contracts`, `test_brigade_spec`, `test_role_models` y la parte de motor de `test_flujo_decidido` portados | **hecha** (257 tests): `test_contracts` → `test_reports` (42), `test_brigade_spec` + motor de `test_flujo_decidido` → `test_engine` (39), integración con runtime, pasarela y tools → `test_engine_runtime` (14). `test_role_models` no se porta tal cual: lo reemplaza la pasarela de 3 escalones (ya cubierta en `test_models`). Empresas sigue en 74 |
| H5 | cargador de manifiestos, montar/desmontar, suite de contrato, matriz, brigada de ejemplo | **puerta de fase 1:** el ejemplo se monta y se desmonta sin romper nada; matriz en verde | **hecha, puerta pasada**: `loader.py` (entry points `raphael.brigades`, carpetas de desarrollo, config contra `config_schema`, `apply()` según la instalación), `testing/contract.py` (suite de 16 chequeos + matriz), `ejemplos/saludo` y `ejemplos/eco` pasan la suite en personal y nube y la matriz está en verde. El panel monta brigadas de verdad |
| H6 (opcional) | brigadas creadas por borrador con activación firmada | `test_brigade_factory`, `test_draft_store` | **hecha**: portados a `test_drafts.py` (59). Tools validadas contra el registro real; `private` en vez de local/shared; almacén en el Store; firma HMAC con clave protegida por DPAPI en Windows (sin dependencias nuevas); un borrador cuyo propio ruteo no pasa no se activa. 358 tests en total |
| H7 | jefe caído, comandos de lectura, salud periódica, `setup` de tools (los huecos de §3.3/§3.7 que quedaban) | decisiones de Damián del 22 nov, cada una con su test | **hecha** (`test_h7.py`, 18): ver decisión 7. 377 tests; Empresas sigue en 74 |
| H8 | API del orquestador (contrato 2.1): los pendientes H-1 a H-12 de `registro/02-orquestador.md`, menos H-11 | un test por pendiente; los 377 previos y Empresas sin cambios | **hecha** por el chat 2 con OK de Damián (`test_orchestrator_api.py`, 25): ver decisión 8. 402 tests; Empresas sigue en 74 |

## 5. Pendientes para otras piezas
- **Pendiente para 00-mando:** SPEC-FAMILIA §3 y §13 todavía dicen "familia-core aparte" y "el harness no se modifica"; este diseño los unifica en `raphael-core`. Actualizar ESTADO con el diseño cuando se apruebe.
- **Pendiente para 02-orquestador:** `app/harness/orchestrator.py` + `blackboard.py` + `a2a.py` (reparto por DAG), `difficulty_router.py`, `designer.py`, y la Secretaria implementando `Orchestrator` y `Chief`.
- **Pendiente para 03-servidor:** `main.py`, `routers/`, `auth.py`, `user_config.py`; revisar si el servidor de Empresas llama a la IA sync desde handlers async.
- **Pendiente para 03-servidor (app):** heredar el esqueleto de la app nativa de Raphael personal que quedó en `codigo/raphael-core/panel/` (distribución acordada con Damián el 21 nov: brigadas montadas + agregar, estado y tareas en vivo, chat por brigada guardado en disco, cocineros, efímeros, herramientas; orquestador = todo junto, brigada = solo lo suyo). Hoy los datos de cocineros salen de `brigadas/`; efímeros, herramientas y tareas son de muestra hasta H2-H5.
- **Pendiente para 03-servidor:** el `Harness` de compatibilidad es sync por dentro (`Runtime.run`): no llamarlo desde un handler `async` de FastAPI (usar `def` o un hilo). El v2 NO abre una base SQLite de Empresas 0.4 (columnas en castellano): da `LegacyDatabaseError` y no la toca. Migrarla no tiene vuelta atrás: proponerla y que la apruebe Damián en la fase 3.
- **Pendiente para 04-cuentas-y-apis:** la clave de NVIDIA va en la variable `NVIDIA_API_KEY`. Según el foro de NVIDIA (revisado 21 nov 2026) el acceso gratis ronda 40 pedidos por minuto y es para desarrollo y pruebas, no producción: leer los términos oficiales antes de usarlo con la clienta.
- **Pendiente para 15-raphael-empresas:** Empresas ya corre sobre el v2 con `compat-shim/raphael_harness` sin tocar su código (`scripts/regresion_empresas.py` lo prueba). La fase 3 puede portar de a poco al contrato v2.
- **Pendiente para 02-orquestador:** el jefe ya está en el núcleo: `Runtime.ask(brigada, pedido, on_event, context)` (o `OrchestratorContext.ask`) devuelve un `InternalReport` validado que NO es un mensaje para la persona; la voz lo traduce. El parámetro `context` es para el DAG (resultados de otras brigadas, como dato, sin tocar el ruteo interno). El watchdog puede usar `Runtime.live` (`LiveBoard.mark_cut`) y los eventos `heartbeat`.
- **Pendiente para 04-cuentas-y-apis:** medir con la clave real de NVIDIA cuánto cumple la síntesis el contrato con claves en inglés (decisión 4). Sin la clave no se puede medir desde acá; el motor degrada explícito si no cumple.
- **Pendiente para 13-autorreparación:** `worktrees.py`.
- **Pendiente para cada pieza de brigada (05 a 15):** para montarse en el v2, cada brigada necesita su `manifest.yaml` en `codigo\` y pasar `run_contract_suite` en sus tests (cómo: README de `raphael-core`, sección "Hacer una brigada montable"; modelos: `ejemplos\saludo` y `ejemplos\eco`). Hasta entonces el panel las lista como "sin manifiesto".
- **Para 02-orquestador (22 nov, H8):** la API que pidió está hecha (decisión 8). Lo que sigue en esta lista para 02 (DAG, designer, Secretaria) es trabajo de esa pieza.
- **Pendiente para 02-orquestador:** las brigadas creadas por borrador no tienen cocineros, así que no entran al ruteo de mensajes; si el orquestador las quiere usar, es con `Runtime.ask`. `DraftStore.activate` NO se le puede dar como tool a ningún modelo: solo la llama código cuando la persona lo pide.
- **Pendiente para 03-servidor (app):** el panel ya corre un `Runtime` con el cargador, aprueba/rechaza pendientes y maneja borradores; el chat con un jefe corre en un hilo. Al heredarlo, mover el runtime a un proceso de fondo (el servidor) y que la ventana sea cliente.
- **Pendiente para 15-raphael-empresas:** separar del perfil lo que es del negocio (precios, encargos, agenda, cobros) para la config de la brigada.

## 6. Decisiones (21 nov 2026)
1. Autonomía rotativa por **confianza progresiva** (sección 3.4), sin pisos en el código.
2. Un solo paquete, `raphael-core`, que reemplaza a `raphael-harness` y a `raphael-familia-core`.
3. Núcleo async; los cocineros pueden escribir métodos comunes.
4. Nombres de campos en inglés también en los reportes del motor; en H4 se vuelve a medir el cumplimiento del contrato de síntesis.
6. (22 nov 2026) Brigadas por borrador: firma HMAC-SHA256 con clave protegida por DPAPI en vez de Ed25519, para no sumar `cryptography` al núcleo. Mismo modelo de amenaza que en JarvisRemote: protege contra editar el almacén y contra efímeros manipulados; no contra código que ya corre como tu usuario.
7. (22 nov 2026, H7) Jefe: sin tope de tiempo por turno; queda caído tras 5 errores seguidos del jefe (un reporte degradado no cuenta) y vuelve a mano desde el panel o al re-montar. Comandos: el manifiesto declara cuáles son de lectura; el orquestador solo corre esos; uno no declarado lo corre la persona desde el panel, con aviso (el orquestador nunca: no se sabe si escribe). Salud: al montar y cada 5 min; aviso, y con 3 chequeos malos seguidos la brigada deja de recibir hasta que vuelva a dar bien. Tools desde código: las registra la función `setup` del manifiesto; una no declarada se acepta con aviso y pide aprobación en cada uso (en la nube se rechaza).
8. (22 nov 2026, H8, la hizo el chat 2 con el OK de Damián) Contrato **2.1.0** (aditivo: las brigadas `>=2.0,<3` siguen montando). `OrchestratorContext` suma modelos de sus roles (solo `mando`, `voz`, `ruteo`, target `orquestador`), `is_private`, `catalog()`, espacio propio `_orchestrator`, `edition`/`plan`/`identity`/`usage()`, `notify` y `query_detail` con motivo. `OwnerContext` suma `session`, `channel` y `emit` (feed). `Orchestrator` suma `consumes`, `configure`, `tick` y `on_event` (lee y avisa, nunca ejecuta; sus eventos `orquestador.*` no le llegan). `Proposal.pending_id`: el número real lo pone código en `ask()` (lo que el modelo escriba ahí se descarta). Manifiesto: sección `routing` (señales con peso 1 o 2, `direct_only`, `safe_default`). Instalación: `orchestrator: {entry, config}`, lo pone `Loader.apply()`; si falla, orden simple y error en `errors["_orchestrator"]`. La H-11 (jefe a medida) no se hizo: la Secretaria es un rol genérico del orquestador. H-13 (para el watchdog de O2): `catalog()` trae `watch` del jefe; `OrchestratorContext.record` y `mark_cut`.
5. Modelos en tres escalones: `pago` (potente, con tope mensual en dólares), `gratis` (rota entre proveedores) y `local` (en la PC, costo cero, lo único para lo privado). Por ahora NVIDIA en los tres (sin plata para pago ni modelo local). Lo privado solo sale a `localhost`: mientras no haya modelo local, Cerebro y Forense siguen con reglas.
