# Diseño del Orquestador · propuesta

Chat 2 · 22 nov 2026 · Estado: **aprobado el 22 nov 2026** (decisiones en §5). API del harness hecha (H8, contrato 2.1). **Las cinco tandas hechas** (O1 a O5, 266 tests): ver `codigo\raphael-orchestrator\README.md` y `registro\02-orquestador.md`.

## 1. Inventario de `codigo-actual/`

Ojo: `codigo-actual\` de esta pieza solo tiene JarvisRemote. El orquestador de Empresas (`raphael-orquestador` 0.3.0) está en `brigadas\15-empresas\codigo-actual\raphael-empresas\raphael-orquestador\`: lo leí ahí, no lo copié ni lo toqué.

### JarvisRemote `backend/orquestador/` (2.729 líneas) y vecinos
| Archivo | Qué hace | Destino |
|---|---|---|
| `routing.py` | Ruteo: override `/brigada`, charla, "pregunta sobre Raphael", reglas por palabras con peso, trabajo conjunto si hay señal fuerte de 2 brigadas, clasificador LLM solo si hay empate, default Cerebro (solo lectura). Brigadas y reglas **fijas en el código** (`cerebro`, `investigacion`, `video`) | **Se reescribe**: misma cascada, pero las brigadas y sus señales salen del catálogo del harness (manifiesto), no del código |
| `mando.py` | `repartir` (sub-tarea por brigada + `despues_de`), `_dependencias` (valida sin ciclos por código; si algo es raro, todo en paralelo), `Reparto.niveles`, `concluir` con control de cifras/URLs y un reintento | **Se porta** casi igual, con nombres en inglés y el reporte v2 |
| `turno.py` | Turno de una brigada (jefe → reporte → voz) y `run_conjunto` (DAG por niveles con futures, contexto como dato, una brigada que falla no tumba a las otras), `combinar_reportes` por código | **Se porta**; el jefe pasa a ser `ctx.ask()` del harness |
| `voz.py` | La voz: prompt de persona, verificador determinista (cifras, ids de propuestas, fuentes, artefactos, fallos; nada inventado), reintentos, completar fuentes por código, plantilla de respaldo, charla corta | **Se porta** casi igual sobre `InternalReport` v2 |
| `watchdog.py` | Vigila el feed del jefe: loop, sin progreso, timeout, errores seguidos; corta y avisa con texto literal | **Se porta** sobre los eventos de `ask(on_event)` y `LiveBoard` del harness |
| `conversacion.py` | Memoria acotada de la charla (8 turnos + resumen determinista), solo la lee la voz; hoy en un JSON en disco | **Se porta** al espacio propio del orquestador en el almacén |
| `agentes.py` | Cocineros/efímeros por brigada y `reporte_del_sistema` (autoconocimiento) | **Se reescribe** sobre `Runtime.status()` y el catálogo |
| `brigadas.py` | Comandos de chat `/crear-brigada`, `/revisar-brigada`, `/activar-brigada <hash>`… (los interpreta código, nunca un modelo) | **Se porta** sobre `raphael_core.drafts`; tanda aparte |
| `banco_ruteo.py` | Banco de pedidos etiquetados para medir el ruteo | **Se porta como datos de test**, re-etiquetado a ids v2 |
| `server.py`, `ui.html`, `launcher.py` | FastAPI, NDJSON, UI web, ventana y puertos de Windows | **Descarte acá** → pendiente para 03 (la lógica del chat pasa a `turn.py`) |
| `slim_tools.py` | Truco para importar el registro de tools del monolito sin cargarlo entero | **Descarte**: no existe más el monolito |
| `voice/engine.py`, `voice/worker.py` | STT (faster-whisper) y TTS (Piper) locales en subproceso | **Se porta, pero no es el rol `voz`**: es un canal de entrada/salida de la edición personal → pendiente para 03 |
| `app/agent.py` (1.868) | Loop del agente monolítico: ejecuta tools de dominio, gates de Obsidian y autorreparación | **Descarte**: el orquestador no ejecuta herramientas de dominio. Las reglas de sus gates son de 09 y 13 |
| `app/skills.py` | Recorta prompt/tools del agente monolítico por palabras clave | **Descarte**: lo reemplaza la caja de tools por efímero del harness |
| `app/proactive.py` | Bucle que amplía casos y llena huecos del vault llamando al agente | **Se reescribe** como "open loops": revisa pendientes y avisa, sin ejecutar nada que pida aprobación. Ampliar casos o el vault es de 07 y 09 |
| `app/mission_control.py` | Estado en memoria + broadcast; 9 brigadas fijas en el código | **Descarte**: lo reemplazan `Runtime.status()` y `live`; el panel es de 03 |

Del lado del harness viejo de JarvisRemote (en `01-harness\codigo-actual`, que el DISENO-V2 dejó para esta pieza): `app/harness/orchestrator.py` (DAG con retry/skip/abort y presupuesto) → **tomo** su validación estricta (nombres duplicados, dependencia inexistente, ciclo) y el presupuesto por turno; `blackboard.py` (reanudar) y `a2a.py` (mensajes entre agentes) → **descarte** en v1 (las brigadas no se hablan; reanudar un DAG queda para después); `difficulty_router.py` → **descarte**, lo absorbe el plan de modelos; `brigades/designer.py` → **se porta** con los comandos de borradores.

### Empresas `raphael-orquestador` 0.3.0 (780 líneas, 28 tests)
| Archivo | Qué hace | Destino |
|---|---|---|
| `orquestador.py` | Ruteo de mensajes de clientes: reclamo → `atencion` primero; conversación abierta; interés 0-1; IA si nadie lo toma; `atencion` siempre al final | **Se reescribe genérico**: abierta → interés → IA de desempate → cocinero de red configurable. Lo de "reclamo va a atención" es conocimiento del negocio: pasa al `interest` del cocinero de Atención (pendiente para 15) |
| `agente.py` | Charla con la dueña: órdenes por reglas ("aprobá la 2"), IA con JSON `decir/hacer`, **armado de acciones con ids reales**, propuesta guardada, ejecuta solo con "sí", cualquier otra frase cancela, memoria corta | **Se porta**: es la base de la confirmación de acciones (§3.5). Se generaliza: los tipos de acción salen del catálogo, no de una lista fija |
| `secretaria.py` | Junta tareas del día (pendientes, encargos, agenda, cobros), puntaje por urgencia, lista, recomendación, siguiente, ficha con contexto y opciones | **Se parte**: la mecánica (lista, recomendar, siguiente, ficha, puntaje por antigüedad) queda en el orquestador; lo del negocio (qué es un encargo, una seña, los textos de las opciones, `BONUS_TIPO`) se va a la brigada Empresas como comando de lectura (§3.6) |

### Problemas que encontré leyendo (verificados en el código)
1. **JR no es montable:** las brigadas, sus reglas, la brigada por defecto y la lista de "directas" están escritas en `routing.py`. Sumar una brigada obliga a editar el orquestador.
2. **El orquestador de Empresas sabe del negocio:** nombra `atencion`, `encargos`, `agenda` y `cobros`, y llama a `ctx.consultar_datos` de cada una.
3. **Ids de propuestas inventables:** en el reporte v2, `Proposal.id` lo escribe la síntesis del modelo; no está atado al número real del pendiente que crea la compuerta de tools (`pending_id`). La voz verifica que el id esté en el mensaje, pero nadie verifica que exista.
4. **Privacidad:** en JR, los reportes de Cerebro (privado) van a la voz y al mando, que hoy usan NVIDIA en la nube. Con la regla v2 ("lo privado solo sale a localhost") eso ya no vale.
5. **Toggles por variables de entorno** (`ORQUESTADOR_*`, más de 15) y archivos en `backend/data/`: pasan a `orchestrator.yaml` y al almacén.
6. **Tests que faltan en la copia:** no encontré en `Raphael Ultimate` tests de `mando.repartir`, `_dependencias` ni `run_conjunto`. `test_optimizaciones.py` (usa el banco de ruteo) y `test_mission_control.py` quedaron sin asignar en `sin-clasificar`. Las pruebas de voz y turno están dentro de `test_flujo_decidido.py`, en `01-harness\codigo-actual` (solo lectura para mí).

### Tests
- Se portan: `test_watchdog` (24), la parte de voz y turno de `test_flujo_decidido` (14 tests), `test_orquestador` (22) y `test_orquestador_brigadas` (17) reescritos sin FastAPI (lo HTTP va a 03), `test_agentes_vivo` (13) sobre `status()`, y los 28 de Empresas (`test_agente`, `test_orquestador`, `test_secretaria`) adaptados.
- Se descartan con su código: `test_agent*` (77). `test_voice` (17) va con `voice/` a 03.
- Nuevos: DAG (validación, niveles, presupuesto), confirmación con ids reales, los dos modos de despliegue, chequeo AST.

## 2. API del harness que falta

Ya existe y alcanza: `route()` sync o async, `ask(brigade, request, on_event, context)`, pendientes con número verificado (`Approvals.open`), `OwnerContext` (aprobar, rechazar, resolver, `act` por el Policy Engine con origen `owner`, `order`, `write`), comandos de lectura declarados, `LiveBoard`, borradores, roles `mando`/`voz`/`ruteo` y planes en la pasarela de modelos.

Lo que faltaba quedó anotado en `registro\02-orquestador.md` (H-1 a H-12) y **está hecho** en `raphael-core` (H8, contrato 2.1.0, `tests/test_orchestrator_api.py`), menos la H-11, que no hace falta con la decisión 1. Resumen de la API en el README de `raphael-core`, sección "API para el orquestador".

## 3. Diseño propuesto

Paquete nuevo `raphael-orchestrator` (módulo `raphael_orchestrator`) en `codigo\raphael-orchestrator\`. Depende solo de `raphael-core`. No importa ninguna brigada (chequeo AST en los tests): todo lo que sabe de ellas sale del catálogo del harness.

```
raphael_orchestrator/
  config.py      orchestrator.yaml: modo (master | secretary), brigada por defecto segura, toggles, topes
  orchestrator.py  la clase Orchestrator (route, talk_to_owner, tick, on_event)
  routing.py     rol ruteo: cascada de reglas + clasificador solo en empate
  plan.py        el DAG: Plan, validación por código, niveles, presupuesto
  command.py     rol mando: repartir y concluir, con control de inventos
  turn.py        turno simple y conjunto (DAG), combinar reportes, feed de eventos
  voice.py       rol voz: comunicar, verificar, plantilla, charla
  confirm.py     propuestas de escritura con ids reales; ejecuta solo tras un "sí"
  secretary.py   rol Secretaria genérico (tareas, recomendar, ficha, órdenes)
  memory.py      conversación acotada en el espacio del orquestador
  watchdog.py    vigila corridas de jefes y corta
  self_report.py autoconocimiento desde el catálogo
  drafts_cmd.py  comandos de brigadas por borrador (tanda aparte)
```

### 3.1 Roles
- **`ruteo`** (barato, decisiones chicas). Pedido de la persona, en orden: comando de código (`/brigadas`, `/crear-brigada`…) → brigada elegida a mano (pestaña o `/id`) → charla social (lista cerrada) → pregunta sobre Raphael → señales con peso del manifiesto de cada brigada; si dos o más tienen señal fuerte, trabajo conjunto → clasificador del rol `ruteo` solo si hay empate o ninguna señal y más de 3 palabras → brigada por defecto segura (config; en personal, la de solo lectura). Las brigadas marcadas "solo directas" nunca entran al auto-ruteo. Mensaje de un cliente: conversación abierta → interés → IA de desempate entre las descripciones → cocinero de red (config). Sin modelo, todo sigue por reglas.
- **`mando`** (el más capaz por plan). Reparte el pedido en sub-tareas y concluye sobre los reportes. Código controla todo lo que propone: sub-tarea corta, sin cifras ni URLs que el pedido no tenga, conserva la señal de su brigada; si no cumple, esa brigada recibe el pedido entero. Conclusión sin datos que no estén en los reportes; un reintento; si no, no hay conclusión y se dice.
- **`voz`** (alto). Única voz hacia la persona. Verificador determinista y plantilla de respaldo como en JR: siempre hay un mensaje y siempre es fiel al reporte. Las propuestas se comunican como propuestas, con su número real. Los textos de comandos, del watchdog y de confirmaciones son de código y salen literales.

### 3.2 Reparto por DAG validado por código
- El mando devuelve `{"<brigada>": "<sub-tarea>", "after": {"b": ["a"]}}`. Código valida: solo brigadas montadas, con jefe y no caídas; sin autodependencias, sin dependencias a brigadas fuera del plan, sin ciclos (orden topológico), sin nombres repetidos. Cualquier falla → todo en paralelo (siempre válido) y un aviso en el feed.
- Se corre por niveles: lo que no depende de nada arranca junto; una brigada arranca cuando terminaron las suyas y recibe sus reportes **como dato** (`ask(..., context=)`), separado del pedido. Una brigada que falla o que el watchdog corta entra como degradada y las que dependen de ella siguen con eso.
- Presupuesto por turno (config): máximo de brigadas, de niveles y de segundos. Si se pasa, se corta y se dice.
- Las dependencias solo valen si todas las sub-tareas pasaron el control (como en JR).

### 3.3 Modelos por plan
El orquestador nunca nombra un proveedor: pide `mando`, `voz` o `ruteo` y la pasarela del harness resuelve plan → rol → escalones (`modelos.yaml`). El proveedor queda configurable por rol y sin decidir. `orchestrator.yaml` solo prende o apaga usos (reparto con IA, conclusión, charla, clasificador) y fija timeouts y reintentos. Si se agotó el tope del plan, el orquestador lo dice y sigue con reglas y plantillas, sin gastar más.

### 3.4 Datos de terceros
Todo lo que entra a un prompt va en un bloque de dato (`data_block`): pedido, reportes, conversación, mensajes de clientes. Ninguna frase de un reporte, una página o un mensaje puede disparar un comando o una aprobación: los comandos solo se leen si el mensaje de la persona **empieza** con ellos.

### 3.5 Confirmación de acciones con ids reales
1. Las lecturas (resumen, recomendar, detalle, estado) corren de inmediato.
2. Una escritura (aprobar, rechazar, responder, escribir a un contacto, una acción o comando declarado de una brigada) se **arma por código** contra la realidad: el número de pendiente tiene que estar abierto, la acción tiene que estar declarada en el manifiesto de esa brigada, el contacto tiene que existir. Lo que el modelo inventó se rechaza y se dice por qué.
3. Se guarda como propuesta en el espacio del orquestador (por sesión) y se muestra: "Voy a … ¿Confirmo?". No vence por tiempo: dura hasta el próximo mensaje de la persona (decisión 4).
4. Solo un "sí" explícito (lista cerrada, el mensaje entero) la ejecuta; cualquier otra frase la cancela. Antes de ejecutar se vuelve a validar (el pendiente pudo cerrarse mientras tanto).
5. Se ejecuta solo por `OwnerContext`; una acción de brigada pasa además por el Policy Engine con origen `owner` (si su nivel pide aprobación, queda pendiente igual). Todo queda auditado con el nombre de quien confirmó.
6. Las propuestas que vienen en un reporte se muestran con el número real del pendiente (`Proposal.pending_id`, lo pone el harness); una sin número real no se ofrece para aprobar.

### 3.6 Secretaria (rol genérico)
Lista lo pendiente, recomienda por dónde empezar, da la ficha de una tarea (contexto de la conversación + opciones) y hace lo que se le pide con la confirmación de §3.5. Fuentes de tareas: los pendientes del harness y un comando de lectura declarado `owner_tasks` que ofrece cada brigada que quiera aparecer (devuelve ítems con título, motivo, puntaje, pendiente, contacto y opciones). El orquestador suma la antigüedad y ordena; **no sabe qué es un encargo ni una seña**: eso lo dice la brigada. Con IA entiende frases libres y responde el JSON `decir/hacer` de Empresas; sin IA, reglas.

### 3.7 Los dos modos de despliegue (mismo código, cambia `orchestrator.yaml`)
- **`master`** (Raphael personal, edición personal): punto de entrada único de Damián. Ruteo, trabajo conjunto por DAG, voz única, watchdog, borradores, open loops. La Secretaria corre como rol interno solo sobre las brigadas que publican `owner_tasks` (Empresas): en la app se ve como jefa de la pestaña Empresas y lo que hace vuelve al maestro como reporte, que comunica la voz. Los mensajes de clientes que entren a Empresas usan el mismo ruteo de cocineros.
- **`secretary`** (instalación de la clienta, edición cloud, sin maestro arriba): `route()` para los clientes y `talk_to_owner()` directo a la Secretaria. El trabajo conjunto queda apagado por defecto y se prende si la clienta contrata dos o más brigadas con jefe. Nada `dangerous` (lo filtra el harness). La persona se nombra con `identity.user`.

En ninguno de los dos hay un `if empresas`: lo que cambia es la config y lo que esté montado.

### 3.8 Fallas
Sin modelo o sin red: reglas y plantillas, y se avisa. Brigada desmontada o caída: se explica (con el motivo del harness) y se sigue con las demás. Orquestador roto: el harness ya tiene respaldo para `route()` y `talk_to_owner()`.

## 4. Tandas propuestas (después del OK y de los pendientes del harness)
| Tanda | Qué | Puerta |
|---|---|---|
| O1 | config, voz (verificador + plantilla), memoria, autoconocimiento | tests de voz de `test_flujo_decidido` portados · **hecha** |
| O2 | ruteo (pedidos y clientes), turno simple, watchdog | `test_watchdog` + banco de ruteo + ruteo de Empresas · **hecha** |
| O3 | mando + DAG + trabajo conjunto | tests nuevos de DAG (ciclos, dependencias raras, presupuesto, falla parcial) · **hecha** |
| O4 | confirmación con ids reales + Secretaria + modo `secretary` | los 28 de Empresas adaptados; ninguna escritura sin "sí" · **hecha** |
| O5 | modo `master` completo, open loops, comandos de borradores | matriz: master y secretary, con y sin modelo; chequeo AST · **hecha** |

## 5. Decisiones (22 nov 2026, Damián: "lo más óptimo en cada caso")
1. **Secretaria:** opción A. Rol genérico en el orquestador + comando de lectura `owner_tasks` en cada brigada que quiera aparecer. Sin jefe a medida (la H-11 no se hace).
2. **Privacidad:** opción A. Si el pedido va a una brigada privada o un reporte viene de una, mando y voz llaman con `private=True` (solo local); sin modelo local, plantilla y aviso. El clasificador de ruteo sigue como decidió Damián el 11 nov: en empate puede mandar el texto a la nube; se apaga con una línea de `orchestrator.yaml`.
3. **Señales de ruteo:** opción A, en el manifiesto (`routing`, contrato 2.1, hecho en H8).
4. **Confirmación:** la propuesta no vence por tiempo; la cancela cualquier mensaje que no sea un "sí" (como en Empresas hoy).
5. **API del harness:** la hizo esta pieza en `raphael-core` con el OK de Damián (H8), con los tests del núcleo y de Empresas en verde.

## 6. Pendientes para otras piezas
- **Harness:** H-1 a H-12 hechos en H8 (menos H-11). Nada pendiente para arrancar.
- **Pendiente para 07-investigacion y 09-memoria:** sección `routing` en su `manifest.yaml`. Las señales equivalentes a las reglas fijas de JR (las que daban el banco de ruteo) están en `codigo\raphael-orchestrator\tests\kit.py` (`CEREBRO_ROUTING` con `safe_default: true`, `INVESTIGACION_ROUTING`). Video (14) va con `direct_only: true`.
- **Pendiente para 15-empresas (O4):** comando de lectura `owner_tasks` en cada cocinero que tenga tareas para la dueña (encargos, agenda, cobros, atención), con el formato del README de `raphael-orchestrator` ("Para las brigadas"); declarar como comandos (no de lectura) las órdenes que hoy eran reglas, como el cambio de estado de un encargo. Modelo de cómo hacerlo: las brigadas de prueba de `tests/test_secretary.py`.
- **Pendiente para 15-empresas:** el `interest` de Atención sube con reclamos o pedido de hablar con una persona (hoy lo hace el orquestador); comando de lectura `owner_tasks` con lo que hoy arma `secretaria.py` (encargos, agenda, cobros, textos de opciones, `BONUS_TIPO`).
- **Pendiente para 03-servidor-app-instalador:** `server.py`, `ui.html`, `launcher.py` y el canal de voz local (`voice/`, `test_voice`); el endpoint de chat solo llama al orquestador y streamea su feed.
- **Pendiente para 02 (esta pieza, más adelante):** portar el diseñador de brigadas por descripción (JR `brigades/designer.py`, está en `01-harness\codigo-actual`); hoy `/crear-brigada` pide el JSON del borrador.
- **Pendiente para 03-servidor-app-instalador:** montar una brigada recién activada por borrador desde la app (cambia la instalación); mostrar los avisos del orquestador (`Runtime.notices()`, evento `orquestador.aviso`); el endpoint de la dueña llama a `Runtime.talk_to_owner(text, session=, channel=, on_event=)` y streamea el feed.
- **Pendiente para 00-mando:** copiar `raphael-orquestador` de Empresas a `codigo-actual\` de esta pieza (hoy está solo en la 15); asignar `test_optimizaciones.py` y `test_mission_control.py` a esta pieza; buscar en el original los tests de `mando`/`run_conjunto`, si existen; actualizar ESTADO (orquestador hecho: O1 a O5; núcleo con contrato 2.1, H8 y H-13 a H-15); actualizar SPEC-FAMILIA §3 y §13.
- **Pendiente para 04-cuentas-y-apis:** `modelos.yaml` no tiene `plans:` cargados (básico, pro, privado, premium); hasta que estén, todos los planes usan el orden por rol.
