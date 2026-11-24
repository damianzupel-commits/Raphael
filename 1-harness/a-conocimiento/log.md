# Registro · 01-harness · Harness

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 21 nov 2026 · Resumen de cierre
- Se hizo el inventario de `codigo-actual/` (los dos motores) y la propuesta de diseño en `nucleo/01-harness/DISENO-V2.md`. Sin código.
- Encontrados en el código: el bus y `recibir` de Empresas no aíslan fallos; `Contexto.para()` deja a cualquier brigada leer el espacio de otra; JarvisRemote no pasa las tools con efecto por un Policy Engine.
- Quedó esperando el OK de Damián al diseño y cuatro decisiones (pisos por instalación, un solo paquete `raphael-core`, núcleo async, nombres de campos de los reportes).
- No se corrieron tests (la VM tiene Python 3.10 sin dependencias); la línea base es la de la fase 0.

## 21 nov 2026 (2) · Resumen de cierre
- Damián aprobó el diseño: autonomía rotativa por confianza progresiva (sin pisos en código; lo que gasta o es irreversible nunca baja solo a automático), un solo paquete `raphael-core`, núcleo async y nombres en inglés también en los reportes.
- H1 hecha en `codigo/raphael-core/`: contrato semver, manifiesto, instalación, almacén con exportar y purgar, bus aislado, auditoría que tacha secretos, `Guard`, texto es-AR y chequeo AST. 73 tests en verde, ruff limpio (probado en la nube con Python 3.13; en la PC no se corrió).
- Línea base real del harness de Empresas: 18 pasan y 3 se saltean (integración: necesita los repos de las brigadas, va con la pieza 15). La puerta de los tests de Empresas pasa a H3.
- Sigue H2: runtime, contextos, Policy Engine con confianza progresiva, pendientes.

## 21 nov 2026 (3) · Resumen de cierre
- Panel nativo del harness (tkinter) en `codigo/raphael-core/panel/`: estado, pruebas en vivo (bus, aislamiento, auditoría), validador de manifiestos y tests. Acceso directo en el escritorio: `Raphael Harness v2.bat` (la primera vez arma `.venv` e instala dependencias).
- Arreglado en `audit.py`: un dato con clave `n`, `when`, etc. pisaba los campos del registro; ahora se guarda como `data_<clave>`. 77 tests en verde, ruff limpio.
- Probado en la nube (Python 3.12 y 3.13, pantalla virtual). En la PC de Damián todavía no se abrió.
- (20:50) El panel pasó a la estética del panel del orquestador (azul noche, cian, esfera, píldoras, pestañas tarjeta); suma Pillow. El lanzador reinstala solo si cambian las dependencias (`.listo-v2`).
- (20:55) Pestañas del panel como las del orquestador: Harness (núcleo, con Estado/Pruebas/Manifiesto/Tests adentro), brigadas montadas, Brigadas (catálogo) y Auditoría, separador y las 12 brigadas sin montar apagadas, con scroll horizontal. Las brigadas se leen de `brigadas\` (README, cocineros y manifest.yaml si hay; nada se importa). 78 tests.
- (21:05) La fila de pestañas muestra solo las brigadas montadas y al final "Agregar brigadas" (abre el catálogo); sin brigadas queda solo ese botón. El núcleo se abre tocando la esfera o el título; Auditoría pasó al selector del núcleo.
- Ojo: una copia a la PC tomó una versión vieja guardada en caché aunque dijo "escrito" (por eso Damián seguía viendo el panel viejo). Desde ahora, después de copiar se compara el md5 en la PC. Verificado: los 28 archivos de raphael-core coinciden.
- (21:20) La app quedó con la distribución que dibujó Damián: arriba brigadas montadas (+ agregar) y estado y tareas en vivo; izquierda el chat (uno por brigada y del orquestador, guardado en `.datos\panel.sqlite`, sin modelo avisa y no inventa); derecha cocineros, efímeros y herramientas. La esfera abre el orquestador (todo junto); una brigada muestra solo lo suyo. Botón "Muestra" con datos de ejemplo marcados y "⚙ Núcleo" para las herramientas del harness. 81 tests. Anotado como pendiente para 03 (la app la hereda esa pieza).

## 21 nov 2026 (4) · Resumen de cierre · H2
- H2 hecha en `raphael-core`: `policy.py` (sin pisos, gana lo más específico; confianza progresiva: baja tras N aprobaciones sin cambios, sube con rechazo, cambios o corrección; lo que gasta o es irreversible nunca baja solo a automático, se propone y la persona confirma), `approvals.py`, `context.py`, `runtime.py` (recibir, despachar, acciones, aprobar/rechazar/resolver/corregir, montar y desmontar con exportar y purgar, ticks, estado).
- Arreglos sobre lo portado de Empresas: un cocinero que falla ya no tumba el mensaje (pasa al siguiente); ningún cocinero puede leer el espacio de otra brigada (no existe `para()`); los comandos del orquestador quedan auditados; publicar exige que el evento esté declarado.
- Arreglado en `isolation.py`: las fallas seguidas se cuentan por método (antes un `interest` sano salvaba a un `handle` que siempre fallaba).
- Decidido sin respuesta de Damián: lo disparado por terceros sube un escalón solo si se activa `trust.third_party_step_up` (apagado por defecto).
- 125 tests en verde (Python 3.12 y 3.13), ruff limpio; los 35 archivos verificados por md5 en la PC. Sigue H3: modelos por rol, uso y compat v1 (puerta: tests de Empresas en verde sobre v2).

## 21 nov 2026 (5) · Resumen de cierre · H3
- Modelos en tres escalones (decidido con Damián): `pago`, `gratis` (rota entre proveedores, pausa ante 429, control de pedidos por minuto y cupo diario) y `local` (lo único para lo privado: se mira que la dirección sea localhost). Cada rol tiene su orden de escalones; overrides por brigada o ayudante; tope mensual en dólares del escalón pago (0 = solo gratis). `modelos.yaml` con NVIDIA en los tres. Registro de uso por escalón y proveedor.
- Compatibilidad v1 (`raphael_core.compat.v1`) y puente `compat-shim/raphael_harness`: **los 74 tests de Raphael Empresas (harness viejo, las 6 brigadas y la integración) pasan sobre el v2 sin cambiar su código**, verificado que corre el v2 y no el harness viejo. `scripts/regresion_empresas.py` y el botón "Empresas sobre el v2" del panel corren esa puerta.
- El v2 no abre una base de Empresas 0.4 (columnas en castellano): avisa y no la toca; la migración queda propuesta para la fase 3.
- 162 tests propios en verde (Python 3.12 y 3.13), ruff limpio, 66 archivos verificados por md5 en la PC. Pendientes anotados para 03, 04 y 15 en DISENO-V2.md. Sigue H4: motor de jefes y efímeros.

## 21 nov 2026 (6) · Resumen de cierre · H4
- Motor de brigadas portado de JarvisRemote a `raphael_core.engine`: spec declarativo, jefe que planifica (reglas primero; su modelo solo elige entre candidatos), delega en paralelo con timeouts, sintetiza con el contrato (un reintento) y si no degrada explícito; efímeros con su modelo y su caja de tools; contratos v2 con campos en inglés; tablero en vivo por runtime; memoria del jefe en el espacio de la brigada.
- `tools.py`: las tools pasan por la política (`tool_<nombre>`): lo no automático queda pendiente y corre al aprobar; nada peligroso en la nube. Arreglaba un problema del inventario (en JarvisRemote no pasaban por la política).
- Cambios respecto de JR: un efímero que llega al máximo de pasos falla (antes devolvía texto de relleno como ok); los errores de tools de un efímero que igual terminó llegan al reporte como avisos (antes se perdían); `is_down` ya no da caída a una brigada que solo tiene jefe.
- 257 tests en verde (3.12 y 3.13), ruff limpio, Empresas sigue en 74 sobre el v2. Pendiente: medir el cumplimiento de la síntesis con NVIDIA real (necesita la clave, anotado para 04). Sigue H5: cargador de manifiestos y suite de contrato (puerta de fase 1).

## 22 nov 2026 (7) · Resumen de cierre · H5 y H6 (todas las tandas hechas)
- H5: `loader.py` (encuentra brigadas por `manifest.yaml` en paquetes instalados o carpetas, valida su config, monta y desmonta según la instalación; una rota no frena a las demás), suite de contrato de 16 chequeos y matriz de montaje (`testing/contract.py`), brigadas de ejemplo `saludo` y `eco`. **Puerta de la fase 1 pasada**: el ejemplo pasa la suite en personal y nube y la matriz está en verde.
- H6: brigadas por borrador portadas (`drafts/`): validación contra el registro real de tools, revisión con hash, activación solo con aprobación firmada (HMAC + DPAPI en Windows, sin dependencias nuevas), se revalida en cada uso y se desmonta sola si deja de verificar.
- El panel ahora corre el núcleo de verdad: "Agregar brigadas" monta y desmonta, chat con brigadas reales, aprobar/rechazar pendientes, apagar tools, vista Borradores; lo montado queda guardado en `.datos\`.
- 358 tests en verde (3.12 y 3.13), ruff limpio, Empresas sigue en 74 sobre el v2. Versión `2.0.0rc1`.
- No verificado: la protección DPAPI de la clave (solo corre en Windows; acá probé el camino sin DPAPI) y la síntesis con NVIDIA real (falta la clave). Pendientes anotados para 02, 03, 04 y las piezas de brigadas en DISENO-V2.md.

## 22 nov 2026 (8) · Resumen de cierre · H7
- Hechos los 4 huecos que quedaban del diseño, con las decisiones de Damián tomadas pregunta por pregunta: jefe caído tras 5 errores seguidos (sin tope de turno; vuelve a mano o al re-montar), el orquestador solo corre comandos declarados de lectura, healthcheck al montar y cada 5 min (3 malos seguidos y la brigada deja de recibir, vuelve sola), y `setup` del manifiesto para registrar tools sin `entry` (no declaradas: aviso y aprobación en cada uso; en la nube se rechazan).
- Interpretado por mí (anotado en la decisión 7): un comando no declarado lo corre la persona con aviso, pero el orquestador nunca.
- El panel corre el tick cada minuto, muestra jefe caído y salud mala en la lista de cocineros y revive el jefe con doble clic. La suite de contrato suma "setup registra sus tools" y "comandos y tools declarados".
- 377 tests en verde (3.12 y 3.13), ruff limpio, Empresas 74 sobre el v2. Versión 2.0.0rc2. Sigue sin verificar: DPAPI en Windows y la síntesis con NVIDIA real.

## 22 nov 2026 (9) · Nota del chat 2 (Orquestador) · H8
- Con el OK de Damián, el chat 2 hizo en `raphael-core` la API que pedía el orquestador (H-1 a H-12 de `registro/02-orquestador.md`, menos H-11). Contrato 2.1.0 (aditivo), versión 2.0.0rc3. Detalle en DISENO-V2.md, decisión 8, y en el README de `raphael-core`.
- Archivos tocados: `contract.py`, `context.py`, `runtime.py`, `loader.py`, `manifest.py`, `installation.py`, `engine/reports.py`, `__init__.py`, README, `panel/harness_panel.py` (texto del contrato) y 3 tests que fijaban "2.0.0". Test nuevo: `tests/test_orchestrator_api.py` (25).
- 402 tests en verde (Python 3.12 y 3.13), ruff limpio (también en `panel`, `scripts`, `compat-shim` y `ejemplos`), Empresas 74 sobre el v2. Los 14 archivos verificados por md5 en la PC. En la PC no se corrió pytest (la VM tiene Python 3.10).

## 22 nov 2026 (10) · Nota del chat 2 (Orquestador) · H-13
- Para el watchdog del orquestador: `Runtime.catalog()` trae `watch` del jefe (`helper_timeout` y su `WatchSpec`), y `OrchestratorContext` suma `record(what, **data)` (auditoría a nombre del orquestador) y `mark_cut(brigada, motivo)` (tablero de efímeros). Test en `test_orchestrator_api.py`. 403 tests, Empresas 74. 3 archivos verificados por md5 en la PC.

## 22 nov 2026 (11) · Nota del chat 2 (Orquestador) · H-14
- `Runtime.catalog()` trae `commands` (todos los declarados, con `read`, `description` y qué cocineros los atienden: los que lo nombran en su `Cook.commands` o, si ninguno, todos). Lo usa la Secretaria para pedir `owner_tasks` y proponer comandos. Test en `test_orchestrator_api.py`. 404 tests, Empresas 74. 2 archivos verificados por md5 en la PC.

## 22 nov 2026 (12) · Nota del chat 2 (Orquestador) · H-15
- `OwnerContext.drafts`: el `DraftStore` del cargador, solo cuando habla la persona (no existe en `OrchestratorContext`, o sea ni en ruteo, ni en tick, ni en eventos). Lo usan los comandos de borradores del orquestador. Test en `test_orchestrator_api.py`. 405 tests, Empresas 74. 2 archivos verificados por md5 en la PC.
