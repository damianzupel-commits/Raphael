# Registro · 02-orquestador · Orquestador

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 22 nov 2026 · Pendientes para harness (API que el orquestador necesita y no existe en `raphael-core` 2.0.0rc2)
Revisado leyendo `contract.py`, `context.py`, `runtime.py`, `approvals.py`, `installation.py`, `manifest.py`, `models/` y `engine/reports.py`. No lo implemento yo.
- **H-1 · Modelos desde el orquestador.** `OrchestratorContext` no tiene `ai`/`has_ai` (solo el `Context` de un cocinero). Falta `ai`, `aai`, `has_ai` y `label` por rol (`mando`, `voz`, `ruteo`) con `target="orquestador"` y `private=`.
- **H-2 · Saber qué es privado.** El orquestador necesita `ctx.is_private(brigada)` (la lista `private` de `modelos.yaml`) para que mando y voz llamen con `private=True` cuando el reporte viene de una brigada privada. Hoy el `InternalReport` no lo dice.
- **H-3 · Catálogo de brigadas.** `brigades()` solo da cocineros de las no caídas. Falta `ctx.catalog()`: por brigada, nombre, descripción, si tiene jefe, cocineros, acciones declaradas (nivel, etiquetas, descripción), comandos de lectura, si es privada, y si está caída con el motivo (salud o jefe). Más las disponibles sin montar, para el autoconocimiento.
- **H-4 · Ids reales en las propuestas de un reporte.** `Proposal.id` lo escribe la síntesis del modelo. Falta que código le pegue el `pending_id` real que devuelve la compuerta de tools (desde la traza) y marque o descarte las propuestas sin número real.
- **H-5 · Espacio propio del orquestador.** `OrchestratorContext` no tiene almacén. Falta `ctx.data` (espacio `_orchestrator`) para propuestas por confirmar, conversación y sesión.
- **H-6 · Hablar con la persona con sesión y feed.** `Runtime.talk_to_owner(text)` no recibe sesión ni canal ni `on_event`, y `OwnerReply` no tiene dónde llevar vía, fidelidad, ruteo o tiempos. Falta `talk_to_owner(text, *, session=None, channel=None, on_event=None)` y `OwnerReply.meta: dict`.
- **H-7 · Ganchos del orquestador.** `Runtime.tick` no llama al orquestador y el orquestador no puede escuchar el bus. Falta `Orchestrator.tick(now, ctx)` y `Orchestrator.on_event(event, data, ctx)` para `pendiente.creado`, `brigada.jefe_caido` y `brigada.reporte` (open loops).
- **H-8 · Entorno en `OrchestratorContext`.** Falta leer `edition`, `plan`, `identity` y el uso (`exceeded`, `summary`), para decir "se acabó el tope" y no gastar más.
- **H-9 · `query()` con motivo.** Hoy devuelve `None` si falla; la voz necesita el motivo (comando no declarado, brigada caída, error) para decirlo.
- **H-10 · Señales de ruteo en el manifiesto** (solo si Damián elige la opción A de la decisión 3): sección opcional `routing` validada: patrones con peso, `direct_only`, `safe_default`.
- **H-11 · Jefe a medida** (solo si elige la opción B de la decisión 1): que `chief` acepte una clase que implemente `run(request, on_event, context) -> InternalReport`, no solo un `BrigadeSpec`.
- **H-12 · Montar el orquestador por config.** Hoy se pasa al constructor de `Runtime`; la instalación (`extra="forbid"`) y el cargador no saben cuál usar. Falta `installation.orchestrator: {entry, config}` o un entry point `raphael.orchestrators`.

## 22 nov 2026 · Resumen de cierre
- Inventario de los dos orquestadores (JarvisRemote y `raphael-orquestador` de Empresas, que está en la carpeta de la 15) y propuesta de diseño en `nucleo/02-orquestador/DISENO.md`. Sin código.
- Encontrado: el ruteo de JR tiene las brigadas fijas en el código; el de Empresas sabe del negocio; los ids de propuestas de los reportes v2 los escribe el modelo; los reportes de brigadas privadas irían a la nube por la voz.
- Anotados H-1 a H-12 como pendientes para harness; sin H-1, H-3, H-5 y H-6 no se puede escribir el orquestador sin tocar el núcleo.
- Queda esperando el OK de Damián y tres decisiones: dónde vive la Secretaria, privacidad de voz/mando/ruteo, y si las señales de ruteo van en el manifiesto.
- No se corrieron tests (no hay código nuevo). Pendientes para 00, 03, 04 y 15 en DISENO.md §6.

## 22 nov 2026 (2) · Resumen de cierre · H8 en el harness
- Damián aprobó el diseño y delegó las decisiones: Secretaria como rol genérico (`owner_tasks` por brigada), mando y voz solo locales con reportes privados (plantilla si no hay modelo), clasificador de ruteo en la nube como el 11 nov, señales de ruteo en el manifiesto, confirmación sin vencimiento (la cancela el próximo mensaje). Anotado en DISENO.md §5.
- Con su OK hice H-1 a H-12 en `raphael-core` (menos H-11): contrato 2.1.0 aditivo, versión 2.0.0rc3, `tests/test_orchestrator_api.py` (25). Detalle en DISENO-V2.md (decisión 8) y nota en `registro/01-harness.md`.
- 402 tests en verde (3.12 y 3.13), ruff limpio, Empresas 74 sobre el v2; 14 archivos verificados por md5 en la PC. En la PC no se corrió pytest (la VM tiene Python 3.10).
- Sigue la tanda O1 del orquestador (config, voz, memoria, autoconocimiento) en `codigo\raphael-orchestrator\`.
- Quedó `obra\tmp-02\` con los paquetes de copia (rc.tgz, emp.tgz, rc-cambios.tgz, rc-md5.txt): se pueden borrar a mano.

## 22 nov 2026 (3) · Resumen de cierre · O1
- Paquete nuevo `codigo/raphael-orchestrator/` (0.1.0): `config.py` (modos master y secretary, voz, memoria; reemplaza las `ORQUESTADOR_*`), `voice.py` (verificador, reintentos, fuentes por código, plantilla, charla), `memory.py` (charla por sesión en el espacio `_orchestrator`), `self_report.py` (autoconocimiento desde `ctx.catalog()`), `ports.py` (roles con `private=`).
- Cambios respecto de JR: los pendientes se nombran por su número real (`#N`) y la verificación lo exige; una propuesta sin número se dice como tal; persona, directrices y nombres salen de la config y la identidad.
- **Puerta de O1 en verde:** 38 tests (los 14 de voz de `test_flujo_decidido` portados más los nuevos de memoria, autoconocimiento, config, puente y reglas: sin imports fuera del núcleo y la stdlib, sin brigadas ni personas en los textos del código), Python 3.12 y 3.13, ruff limpio. 11 archivos verificados por md5 en la PC; en la PC no se corrió pytest (la VM tiene Python 3.10).
- No portado: la autoconciencia (líneas rojas de `app.self_model` de JR, que no está en la copia): la voz acepta `self_model` cuando alguien lo cargue. Sigue O2.

## 22 nov 2026 (4) · Resumen de cierre · O2
- `routing.py` (pedidos con las señales del manifiesto de cada brigada, charla, autoconocimiento, conjunto, clasificador validado, destino seguro; clientes con conversación abierta → interés → modelo → red), `watchdog.py` (sobre los eventos del motor v2, límites del catálogo, registro en `_orchestrator`) y `turn.py` (turno simple por `ctx.ask` vigilado → voz; privada → solo local; un solo `final`).
- **Puerta de O2 en verde:** 151 tests (watchdog portado de JR, el banco de ruteo de JR entero con señales de manifiesto, ruteo de clientes de Empresas, turno de punta a punta sobre el harness), 10 de 10 corridas, Python 3.12 y 3.13, ruff limpio. Encontrado y arreglado por un test: el turno guardaba la charla en la sesión `default` en vez de `ctx.session`.
- En el núcleo (H-13, con el mismo OK): `catalog()` trae `watch` del jefe, y `OrchestratorContext` suma `record` y `mark_cut`. Núcleo en 403 tests, Empresas 74 sobre el v2. 21 archivos verificados por md5 en la PC.
- Límite heredado de JR, sin cambiar: el verificador de la voz controla cifras, fuentes, pendientes, creados y fallos, pero un mensaje sin nada de eso (por ejemplo un saludo) pasa si el reporte tampoco trae nada de eso. Queda anotado para revisar en O5.
- Antes de O3 un pedido conjunto va a la brigada de más puntaje, con aviso. Sigue O3 (mando + DAG).

## 22 nov 2026 (5) · Resumen de cierre · O3
- `plan.py` (DAG: dependencias validadas por código, niveles, presupuesto de brigadas y etapas), `command.py` (rol mando: repartir con control de inventos y de la señal de su brigada; concluir con un reintento) y `joint.py` (DAG por niveles con `ctx.ask` vigilado por nodo, contexto previo como dato, falla parcial, corte del watchdog y presupuesto de tiempo sin tumbar el turno; `combine_reports` por código con los números reales de los pendientes). Trabajo conjunto prendido en `master`, apagado por defecto en `secretary`.
- **Puerta de O3 en verde:** 184 tests (25 nuevos de DAG y mando; 9 de conjunto de punta a punta sobre el harness: paralelo, dependencia, falla parcial, proveedor caído, watchdog en un nodo, presupuesto, brigada privada sin nada a la nube, sin modelo del mando), 11 de 11 corridas en 3.12 y 3.13, ruff limpio. 23 archivos verificados por md5 en la PC. El núcleo no cambió en esta tanda.
- Visto en un test: cuando un proveedor falla, la pasarela lo pausa para todos; en un turno conjunto eso degrada también a las otras brigadas que usan el mismo proveedor (es comportamiento del harness, no del orquestador; con más proveedores por escalón no pasa).
- Sigue O4 (confirmación con ids reales, Secretaria, modo secretary).

## 22 nov 2026 (6) · Resumen de cierre · O4
- `confirm.py` (escrituras armadas contra la realidad: pendiente abierto, nivel, contacto conocido, comando declarado; "¿Confirmo?"; solo un "sí" explícito, el mensaje entero, ejecuta; se revalida antes; por sesión), `secretary.py` (rol Secretaria genérico: pendientes del harness + `owner_tasks` de cada brigada; lista, recomendar, siguiente, ficha; órdenes por reglas, también por número real "aprobá el #7", y con IA validada) y `orchestrator.py` (`RaphaelOrchestrator`, entry point `raphael`; modos secretary y master básico).
- **Puerta de O4 en verde:** 222 tests (los 22 de secretaria y agente de Empresas portados, con brigadas de prueba que hacen lo que le toca a la 15; más: ninguna escritura sin "sí" con 7 frases trampa, sesiones que no se cruzan, pendiente cerrado mientras esperaba el sí, tareas rotas de una brigada, inventos de la IA en 5 formas). 8 de 8 corridas en 3.12 y 3.13, ruff limpio. Se rompió a propósito la confirmación y los tests fallan. 29 archivos verificados por md5 en la PC.
- En el núcleo (H-14): el catálogo trae todos los comandos declarados (no solo los de lectura) y qué cocinero los atiende. 404 tests, Empresas 74.
- Cambio respecto de Empresas: "marcá el encargo 4 como listo" ya no es una regla del orquestador; va como comando declarado de la brigada (lo propone la IA o la brigada en sus opciones) y pide confirmación igual. Sin emojis en las respuestas de código (se leen en voz alta).
- Sigue O5 (modo master completo, avisos proactivos, comandos de borradores).

## 22 nov 2026 (7) · Resumen de cierre · O5 (las cinco tandas hechas)
- `drafts_cmd.py` (comandos de borradores sobre `raphael_core.drafts`: crear con el JSON, revisar, activar solo con el hash exacto, desactivar, descartar; los interpreta código, solo si el mensaje empieza con el comando y solo desde el `OwnerContext`), `proactive.py` (avisos por los ganchos del harness: pendiente que resuelve una persona, jefe caído, salud mala, propuesta de confianza, recordatorio de pendientes viejos; solo lee y avisa) y el modo `master` completo con feed y `meta`.
- Cerrado el límite que anoté en O2: el verificador de la voz ahora rechaza un mensaje que no dice nada del reporte (ninguna palabra con contenido de la conclusión, los hallazgos o lo no encontrado).
- **Puerta de O5 en verde:** 266 tests (matriz de 28 casos: master y secretary, con y sin modelo; montado de verdad por la instalación; config inválida falla al montar), 8 de 8 corridas en 3.12 y 3.13, ruff limpio. En el núcleo (H-15): `OwnerContext.drafts`. 405 tests, Empresas 74. 32 archivos verificados por md5 en la PC; en la PC no se corrió pytest (la VM tiene Python 3.10).
- No portado (anotado): el diseñador de brigadas por descripción (JR `brigades/designer.py`, no estaba en la copia de esta pieza): hoy `/crear-brigada` pide el JSON. Activar un borrador no lo monta: eso queda para la app (03).
- Pendientes de otras piezas en DISENO.md §6 (03, 07, 09, 15, 00, 04).

## 25 nov 2026 · Resumen de cierre · lienzo en blanco
- Arreglado `c-salud/pruebas/conftest.py`: tras la mudanza al árbol a/b/c buscaba `raphael-core` una carpeta de más y los 266 tests no corrían sin instalarlo. Ahora corren desde el repo limpio.
- Nuevo: `speech.py` + `speech_worker.py` (voz hablada local enchufable, con simulada y apagada), `health.py` (chequeo de salud), aviso proactivo cuando falta el modelo de un rol o el modelo LOCAL que exigen las brigadas privadas (lo sensible no se manda a la nube), `speech` y `warn_no_ai` en la config.
- Plantillas: `orquestador.env.plantilla`, `orquestador.config.ejemplo.yaml`, `modelos.personal.ejemplo.yaml` (decisión de Damián: sensible local, resto NVIDIA, cualquier rol cambiable). Un test las valida.
- **Puerta en verde:** 282 tests del orquestador (16 nuevos), core 409, Empresas 124, ruff limpio. Sin red ni claves.
- Decisión de diseño: el orquestador no es brigada, no lleva manifest ni cocineros; se monta por la instalación.
- Pendientes para otras piezas: harness (`modelos.yaml` real de la edición personal: usar el ejemplo y alinear `private` con los ids de los manifests de 05, 07, 09 y 12; el harness no sondea si Ollama está prendido: lo nota cuando falla el pedido y pausa al proveedor); 03 (endpoints HTTP de voz `/api/voz*`, que usan `speech_from`); coordinador (ESTADO, LIENZO-DAMIAN).
- No probado: voz real (sin faster-whisper, Piper ni modelos en la nube de pruebas), Ollama/LM Studio ni NVIDIA reales, Windows.
