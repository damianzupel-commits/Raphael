# ARQUITECTURA DE RAPHAEL — especificación autoritativa

> **Qué es este documento.** La especificación de arquitectura de Raphael (proyecto JarvisRemote), escrita para que otra IA (o una persona)
> pueda **optimizar un punto concreto** sin leer todo el repo. Describe cómo ES el sistema (verificado contra el código al 2026-11-15) y
> cómo DEBE SER (**decisiones finales de Damian**), y marca la distancia entre ambos.
>
> **Cómo leerlo.** Cada componente tiene un ID direccionable (`ORQ-1`, `JEFE-2`…), cada divergencia entre el estado actual y el objetivo un
> `DIV-nn`, y cada punto de optimización un `OPT-nn` (sección 9). Para pedir una optimización alcanza con: *«optimizá `OPT-04`»*.
>
> **Convenciones.** ✅ = así es hoy · 🎯 = diseño **decidido** por Damian (ya no es propuesta), aún no implementado · ⚠️ = divergencia. Las rutas son relativas a la raíz del repo
> (`C:\Users\dam\Documents\JarvisRemote`). Vocabulario de Damian: **cocineros** = agentes PERMANENTES de una brigada; **efímeros** = ayudantes
> que se crean por tarea y mueren. No se usan términos como "router/worker".
>
> **Estado de implementación (2026-11-15):** la refactorización al modelo decidido (`DIV-01`…`DIV-09`, puntos P0–P5 de `docs/PARA-FABLE-5.2.md`) **está implementada en el código** y cubierta por tests sin red;
> **todavía NO pasó por las validaciones reales** con modelos (ver «§0. Estado de implementación»). En el resto del documento, lo marcado 🎯 / ⚠️ `DIV-nn` describe el punto de partida del 2026-11-15; el estado vigente es el de §0.
>
> **Convención de opiniones de Damian.** En los documentos de Damian, las marcas **`R)`** y **`DAMIAN:`** señalan una **OPINIÓN suya**. Toda IA que lea
> esos documentos debe tomarla como tal: no es un dato del sistema ni una sugerencia de otra IA, es una postura del dueño del proyecto y, cuando
> contradice a un documento previo, gana la opinión de Damian.
>
> **Notas de Damian ya incorporadas (diseño FINAL, no propuesta)** — estado: ✅ incorporadas el 2026-11-16:
> 1. **Flujo:** Ayudantes → Jefe → Orquestador → Usuario.
> 2. **Orquestador:** además de clasificar y rutear, es la **VOZ con el usuario**: toma el reporte interno del jefe y se lo comunica a Damian de forma personal y cercana, "en sus formas". **El mensaje final al usuario lo produce el orquestador**, no el jefe.
> 3. **Jefe:** coordina a sus ayudantes efímeros, **sintetiza** sus resultados con su **especialización de dominio** y le **reporta al orquestador** (reporte interno/estructurado; **no le habla al usuario**). **Tiene su PROPIO LLM.**
> 4. **Ayudantes efímeros:** hacen el trabajo y reportan al jefe.
> 5. **Modelo siempre intercambiable:** el modelo de **cada rol** (orquestador, jefe, ayudante) es swappable por configuración; el default es nemotron, pero siempre intercambiable.

---

## 0. Estado de implementación (2026-11-15)

**El flujo decidido (Ayudantes → Jefe → Orquestador → Usuario) está implementado.** Lo que sigue es el estado vigente; las secciones 2–9 conservan la descripción del punto de partida.

| ID | Qué se decidió | Estado | Dónde quedó |
|---|---|---|---|
| **DIV-01** | Cerebro delega, sintetiza y reporta | ✅ implementado | `brigades/cerebro.py`: ayudante efímero `cerebro-recuperador` (asociativo + keyword, devuelve evidencia con extracto textual); el jefe no tiene tools |
| **DIV-02** | El jefe sintetiza y reporta (nunca devuelve el texto crudo del ayudante) | ✅ implementado | `brigades/engine.py` (`_sintetizar`), prompts de jefe en `cerebro.py`, `investigacion.py`, `seguridad.py` |
| **DIV-03** | 1..n delegaciones planificadas, en paralelo si son independientes | ✅ implementado | `engine.py` (`_plan`, `_delegar`), `spec.py` (`Routing.coincidencias`) |
| **DIV-04** | No existe la brigada "directa" | ✅ implementado | `spec.py` (un `BrigadeSpec` sin ayudantes no se construye), `factory.py`, `designer.py`, `ejemplos.py` (`EJEMPLO_UN_AYUDANTE`) |
| **DIV-05** | Eventos del flujo en el feed | ✅ implementado | `plan`, `delegacion`, `resultado_ayudante`, `sintesis`, `reporte`, `comunicacion`, `final` (del orquestador); `ui.html` |
| **DIV-06** | Persona y directrices gobiernan la voz del orquestador | ✅ implementado | `orquestador/voz.py` (`build_voz_system_prompt`); salieron del prompt de Cerebro |
| **DIV-07** | El orquestador es la voz: produce el `final` | ✅ implementado | `orquestador/voz.py`, `orquestador/turno.py`, `server.py` (`/api/chat`) |
| **DIV-08** | Cada rol con LLM propio e intercambiable | ✅ implementado | `brigades/config.py` (`resolve_role_model`, `describe_role_model`), `.env.example` |
| **DIV-09** | Contratos (resultado y reporte) | ✅ implementado | `brigades/contracts.py` |

**Decisiones de implementación** (dentro de lo que el brief dejaba al implementador; si alguna no te cierra, se cambia en un punto):

1. **Planificación: las reglas mandan, el LLM solo elige entre candidatos.** Ninguna regla matchea → el ayudante por defecto (el más pasivo), sin LLM. Una sola → ese ayudante, sin LLM. Dos o más → el LLM del jefe decide cuáles de ESOS hacen falta y redacta cada sub-tarea. El LLM nunca puede sumar un ayudante cuya regla no matcheó (falsos `scout`/`escaneo` = 0) y, si su plan falla o no es válido, gana la primera regla (el comportamiento determinista anterior). Apagable: `BRIGADE_PLAN_LLM=0`.
2. **El LLM del jefe aporta solo la síntesis; el resto del reporte lo completa código.** `resumen`, `hallazgos`, `confianza`, `no_encontrado` y `propuestas_pendientes` vienen del modelo y se validan; `fuentes`, `artefactos`, el detalle por ayudante y los `fallos` salen de los resultados, así no se pueden esconder ni inventar. `requiere_aprobacion` es siempre `true`.
3. **Las fuentes del reporte son las que la síntesis CITA** (tomadas tal cual del resultado del ayudante), no todo lo que una búsqueda tocó: una nota que el recuperador trajo pero no tiene que ver con la pregunta no le llega a Damian como fuente. Sin síntesis (reporte degradado) van todas.
4. **Chequeo de cifras en dos lugares.** En la síntesis: toda cifra del texto del jefe tiene que estar en los resultados de los ayudantes o en el pedido; si no, se reintenta una vez y después se degrada. En la voz: ver el punto 6.
5. **Degradación explícita.** Si el LLM del jefe no responde o no cumple el contrato tras `BRIGADE_SINTESIS_REINTENTOS` (1), el reporte se arma con los resultados crudos, marcado `sintesis_degradada` y con el motivo en `avisos`. Si ningún ayudante completó su tarea, no se le pide al modelo que sintetice la nada: se reporta el fallo.
6. **Fidelidad de la voz (verificador determinista, `voz.verificar`).** El mensaje tiene que traer las cifras de la **conclusión** del reporte (`resumen`), los ids de las propuestas pendientes, los artefactos creados (id o nombre de archivo), todas las fuentes (por título o ref) y todos los fallos; y no puede traer cifras ni URLs que no estén en el reporte o en el pedido. Si no pasa: hasta `ORQUESTADOR_VOZ_REINTENTOS` (2) reintentos diciéndole al modelo qué falta; si solo faltan fuentes se agregan por código; si no, **mensaje de respaldo por plantilla** construido desde el reporte. Las cifras de los `hallazgos` se pueden decir pero no se exigen: exigirlas todas haría imposible un mensaje corto para leer en voz alta.
7. **Textos literales.** Comandos de gestión, gates y el aviso de corte del watchdog salen como `final` con `origen: "comando" | "watchdog"` y `literal: true`: no pasan por el LLM de la voz.
8. **Memoria de conversación del orquestador** (`orquestador/conversacion.py`): últimos 8 turnos + una línea por turno más viejo (hasta 12), en `backend/data/orquestador/conversacion.json`. Solo la lee la voz, como DATO; nunca se le pasa a un jefe ni a un ayudante. Apagable: `ORQUESTADOR_MEMORIA=0`.
9. **Watchdog.** Suma `WATCHDOG_JEFE_SECONDS` (600) a la duración esperada del turno, para que el jefe pueda reportar el fallo de un ayudante que agotó su tiempo; distingue las llamadas por ayudante (dos ayudantes en paralelo haciendo la misma búsqueda no son un loop).
10. **Compatibilidad del feed.** Se sigue emitiendo `tool delegar:<id>` (y `tool_result delegar:<id>` con `ok=false` cuando un ayudante cae) además de los eventos nuevos, porque las validaciones con baseline y el watchdog los leen.
11. **Monolito (:8000).** Su router `/api/brigade/{id}/chat` usa el mismo turno (`orquestador/turno.py`), así que tampoco ahí un jefe le habla directo al usuario.

**Pendiente (no hecho en esta tanda):**

- **Validaciones reales** con modelos (`python -m validation.todas cerebro investigacion`). Los pasos se adaptaron al flujo nuevo **sin cambiar ningún criterio**: lo que evalúan como «respuesta» ahora es el mensaje final del orquestador, y se sumó el chequeo de que ese mensaje sea fiel al reporte. Hay que correrlas en la PC de Damian; **el baseline de Cerebro corresponde al flujo anterior**, así que la primera corrida va a marcar desbalances (tools usadas, palabras) y, si queda verde, corresponde `--rebaseline`.
- **P6 (O-1…O-11):** hecho en una segunda tanda, ver §0.1. Se hizo a pedido de Damian **antes** de las validaciones reales de P0–P5; las mediciones son con datos inventados, no con el vault.
- **Directrices operativas de Cerebro.** Por la decisión `DIV-06` las directrices ahora gobiernan la voz del orquestador y ya no llegan al jefe de Cerebro ni a su recuperador. Las de forma («respondé en una oración», «terminá con…») funcionan igual o mejor; una directriz **operativa** («no leas las notas de la carpeta X») hoy no tiene efecto sobre qué busca el recuperador. Si querés que también lo gobiernen, es agregar las directrices al prompt del recuperador (un cambio de una línea en `brigades/cerebro.py`); no se hizo porque contradice la letra de la decisión.
- **Privacidad (O-11).** Con el flujo nuevo, lo que el recuperador saca de las notas lo ven tres modelos: el del recuperador, el del jefe de Cerebro y el de la voz del orquestador (este último recibe el reporte, no las notas enteras). Hoy los tres son nemotron/NVIDIA; cada uno se puede llevar a un modelo local por `.env` (ejemplos en `.env.example`).


### 0.1 Optimizaciones P6 (2026-11-15): equilibrio entre calidad y eficiencia

Criterio: gastar tiempo y tokens solo donde mejoran la respuesta. Ningún gate, criterio de validación ni verificador se aflojó.

| ID | Qué se hizo | Dónde |
|---|---|---|
| **O-1** ruteo | Banco de 61 pedidos etiquetados; reglas ampliadas; pedido de ≤3 palabras sin señales → default sin modelo; clasificador sin razonar y con sesgo a Cerebro (menor daño) | `orquestador/banco_ruteo.py`, `routing.py` |
| **O-2** consolidación | Evaluación de umbral/brecha contra una verdad etiquetada y barrido de umbrales (solo lee; **falta correrlo contra el vault real**) | `app/obsidian/consolidation.py` (`evaluar_agrupamiento`, `barrer_umbrales`), `validation/calibrar_consolidacion.py` |
| **O-3** recuperación | La búsqueda asociativa puede devolver el extracto textual que responde: el recuperador resuelve en una búsqueda lo que antes era buscar + leer | `app/obsidian/spreading.py` (`extracto_relevante`), `app/tools/obsidian.py`, `brigades/cerebro.py` |
| **O-4** latencia | `tiempos` por fase en `reporte` y `final` (plan, ayudantes, síntesis, jefe, voz, total), visibles en la UI | `engine.py`, `turno.py`, `ui.html` |
| **O-5** prompts | Plan en JSON plano; la voz recibe el reporte compacto (sin campos vacíos ni extractos) y sin el bloque de Markdown de la persona del chat; tests de presupuesto de tamaño | `engine.py`, `voz.py` |
| **O-6** watchdog | `latido` mientras se espera a un modelo o ayudante (da hasta 3× de aire, nunca infinito); loops que solo cambian mayúsculas/espacios/puntuación; `watch` declarable en borradores, dentro de rangos y sin poder apagarlo | `engine.py`, `watchdog.py`, `factory.py` |
| **O-7** costo por rol | Razonamiento por fase (off en ruteo, plan y voz; síntesis `auto`: razona solo en el reintento); topes de tokens; modelo de respaldo por rol con su propia key | `brigades/config.py` (`completar`, `razonamiento`, `fallback_role_model`) |
| **O-8** memoria del jefe | La nota por turno guarda conclusión, no encontrado, creado y pendiente (≤900 caracteres) y llega a la síntesis siguiente como DATO | `engine.py` |
| **O-9** borradores | Hasta 5 versiones anteriores, restaurables; edición del JSON desde la UI. Restaurar nunca activa: la aprobación firmada sigue siendo sobre el hash vigente | `draft_store.py`, `server.py` (`POST /api/brigadas/{id}/restaurar`), `ui.html` |
| **O-10** voz | Lectura por oraciones (empieza a hablar con la primera). **No hecho:** Whisper medium / VAD | `ui.html` |
| **O-11** privacidad | `ROLES_EN_LOCAL` fuerza roles a un modelo de esta PC (exige loopback); auditoría de qué ve cada rol y a qué proveedor sale | `brigades/config.py`, `agentes.py` (`privacidad`), `GET /api/privacidad` |

**Charla directa (agregado el mismo día, a pedido de Damian).** Un mensaje que es SOLO charla social (saludo, agradecimiento, despedida; lista cerrada en `routing.es_charla`) lo contesta el orquestador con una sola llamada a la voz (`voz.charlar`), sin brigada ni reporte: antes un «hola» recorría Cerebro entero (~13 s) para decir que no había nada que buscar. Solo en la pestaña de auto-ruteo; la respuesta no puede traer cifras ni URLs (si las trae, sale una plantilla fija); se apaga con `ORQUESTADOR_CHARLA_DIRECTA=0`. En la UI, el chip «Proceso» oculta los pasos intermedios y deja solo la respuesta.

**Trabajo conjunto de brigadas (principio de Damian: todo modular; cada brigada funciona sola y, además, pueden trabajar juntas bajo el mando del orquestador).** Si un pedido en auto-ruteo trae una señal explícita (peso 2) de más de una brigada (`routing.brigadas_conjuntas`, por código, sin modelo), cada brigada lo trabaja **por separado y en paralelo** —su jefe, sus ayudantes, su watchdog, su candado— sin enterarse de las otras; el orquestador une los reportes por código (`turno.combinar_reportes`: resúmenes rotulados por brigada, listas unidas, confianza la más baja, topes del contrato con aviso) y la voz comunica **una** respuesta con el verificador de siempre, que ahora exige las cifras y fuentes de todas. Si una brigada falla o el watchdog la corta, las demás entregan igual y el fallo queda dicho. Las brigadas no cambiaron ni se hablan entre sí. **El MANDO del orquestador** (`orquestador/mando.py`, rol `mando` con modelo propio: `ORQUESTADOR_MANDO_LLM_*`, pensado para el modelo más capaz) hace dos cosas alrededor de las brigadas: **reparte** el pedido (una sub-tarea por brigada; cada una tiene que conservar la señal explícita de su brigada y no traer cifras ni URLs que el pedido no tenga, y si no cumple se reemplaza por el pedido entero) y **concluye** sobre los reportes (sin cifras ni URLs que no estén en ellos; un reintento; si no se logra, no hay conclusión y queda un aviso). La conclusión encabeza el resumen del reporte conjunto, rotulada, y la voz la comunica. **Es un DAG** (2026-11-16): el reparto puede declarar `despues_de` (qué brigada necesita el resultado de cuál); código valida que las dependencias sean entre brigadas del plan y sin ciclos (si no, todo en paralelo) y `turno.run_conjunto` ejecuta por niveles: cada brigada arranca cuando terminaron las que necesita y recibe sus reportes como DATO. Ese contexto viaja **separado del pedido** (`GenericChief.run(message, contexto=…)`): el plan interno del jefe se decide solo con el pedido, el contexto llega a los ayudantes y a la síntesis, y no se guarda en la memoria del jefe. Si la brigada de la que se depende falla, la siguiente corre igual con ese fallo a la vista. ⚠ Privacidad: en una cadena, lo que una brigada sacó (por ejemplo de las notas) le llega a los modelos de la siguiente; se apaga con `ORQUESTADOR_DAG=0`. Límites: los nodos son brigadas enteras (no ayudantes sueltos) y el plan no se rehace a mitad de camino. Hoy solo Cerebro e Investigación entran al auto-ruteo, así que son las únicas que se combinan. Se apaga con `ORQUESTADOR_TRABAJO_CONJUNTO=0`.

**Mediciones** (`python -m validation.medir`, nemotron en NVIDIA, datos inventados, 2026-11-15; pocas corridas, sirven de orden de magnitud):

| Fase | Antes | Después |
|---|---|---|
| Ruteo (61 pedidos) | — | 80 % por reglas con 100 % de acierto; 4 cortos sin modelo; 8 al clasificador, 100 % de acierto, p50 0,55 s |
| Plan del jefe | — | ~1 s |
| Síntesis del jefe | 12–25 s (razonando) | 3–5 s; 7 de 8 válidas al primer intento, 0 degradadas |
| Voz del orquestador | 20–40 s (razonando) | 1–3 s, fiel al reporte |
| Turno sin contar ayudantes (plan + síntesis + voz) | — | 7–15 s |

El clasificador sin razonar acertaba 37,5 % con el prompt original; con el prompt nuevo, 100 % sobre los 8 casos que le llegan. La calidad de la síntesis sin razonar se sostiene en el verificador (contrato + cifras): si el primer intento no cumple, el reintento razona.

---

## 1. Visión y principios

Raphael es un asistente personal con agentes organizados en **brigadas**, que empezó como auditoría de código/pentesting manejada por un LLM y
creció a memoria (Cerebro), investigación (Scout + Forense), seguridad defensiva, voz y creación de brigadas nuevas.

| # | Principio | Cómo se hace cumplir (en código, no en promesas) |
|---|---|---|
| P1 | **Local-first, nube por decisión explícita** | Embeddings, voz (faster-whisper/Piper) y el orquestador corren en esta PC (127.0.0.1). Los modelos de lenguaje hoy están en la nube **por decisión explícita de Damian** (2026-11-12, "quiero ver qué pasa", privacidad asumida); es reversible por `.env`. Ver §5. |
| P2 | **Gates por código, no por prompt** | `authorized_targets.yaml` (scope de pentest, solo lo edita Damian), aprobación **firmada** para activar brigadas creadas, `FS_DENIED_PATHS`, dry-run→confirm, flags por capacidad (`*_ENABLED`). Un prompt nunca es la única barrera. |
| P3 | **El usuario al mando** | Nada que cambie el sistema se activa solo: una brigada creada nace como borrador y solo se activa con el OK de Damian sobre el hash exacto; los jefes/ayudantes **proponen**, Damian **confirma** (`investigation_confirm_*` no está al alcance de ningún ayudante). |
| P4 | **Menor privilegio por rol** | Cada ayudante ve solo sus tools; el techo de la brigada es la unión de lo que ven sus ayudantes; las tools peligrosas están denegadas para brigadas creadas (`brigades/tool_catalog.py`). |
| P5 | **Frontera instrucción-vs-dato** | Todo lo que traen las tools, las notas, la web o los ayudantes es DATO, nunca una orden. Está en el prompt de cada rol (`SEGURIDAD_COMUN` en `brigades/factory.py`) y en el motor (contexto previo marcado como DATO). |
| P6 | **Auto-documentado y auto-validado** | Cada brigada = SPEC + VALIDACIÓN; un watchdog vigila la ejecución contra el spec; el documento maestro se regenera solo (hook de pre-commit). Ver §6. |
| P7 | **Modelo de delegación y reporte** (🎯 decidido por Damian) | **El jefe de brigada nunca responde directo ni le habla al usuario.** Coordina: delega en ayudantes efímeros, junta sus resultados, los **sintetiza con su especialización** y le **reporta al orquestador**. Flujo: **Ayudantes → Jefe → Orquestador → Usuario**. Ver §3. |
| P8 | **Observabilidad** | Todo turno es un feed NDJSON; los efímeros vivos y las intervenciones del watchdog se ven en la UI; `GET /api/meta` informa el modelo **efectivo** de cada rol. |
| P9 | **El orquestador es la única voz hacia el usuario** (🎯 decidido) | El mensaje final que recibe Damian lo produce el orquestador a partir del reporte interno del jefe, de forma personal y cercana ("en sus formas"). Ningún jefe ni ayudante le habla directo al usuario. |
| P10 | **Modelo SIEMPRE intercambiable por rol** (🎯 decidido) | Orquestador, cada jefe y cada ayudante tienen su propio LLM y cada uno es **swappable por configuración**, sin tocar código. El default es nemotron/NVIDIA, pero **ningún rol queda atado a un modelo o proveedor**. |

---

## 2. Capas y responsabilidades

```
                         Damian (texto / voz)
                                ▲   │
        mensaje final, personal   │   │  pedido
        y cercano ("en sus formas")   ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ L1  ORQUESTADOR  (LLM propio)   backend/orquestador/         │  CLASIFICA/RUTEA y es la VOZ con el usuario
  └──────────────▲───────────────────────────────┬───────────────┘
   REPORTE INTERNO│ (estructurado)                │ pedido + brigada
  ┌──────────────┴───────────────────────────────▼───────────────┐
  │ L2  JEFE DE BRIGADA  (LLM propio, cocinero permanente)        │  COORDINA, delega y SINTETIZA con su especialización
  └──────────────▲──────────────────┬────────────▲────────────────┘
   resultado     │                  │ sub-tarea  │ resultado
  ┌──────────────┴───────┐   ┌──────▼────────────┴──┐
  │ L3  AYUDANTE EFÍMERO │   │ L3  AYUDANTE EFÍMERO │   hacen el trabajo real; nacen y mueren; reportan al jefe
  │     (LLM propio)     │   │     (LLM propio)     │
  └──────────────┬───────┘   └──────────┬───────────┘
                 │ llamadas             │
  ┌──────────────▼──────────────────────▼───────────────────────┐
  │ L4  SKILLS / TOOLS   backend/app/tools/ (~131 tools)         │  acciones concretas, cada una acotada
  └───────────────────────────────────────────────────────────────┘
```

**Regla de flujo (decidida):** el trabajo baja (Orquestador → Jefe → Ayudantes) y el resultado **sube capa por capa**: **Ayudantes → Jefe → Orquestador → Usuario**.
Nadie salta una capa: un ayudante nunca le habla al usuario ni al orquestador; el jefe nunca le habla al usuario; solo el orquestador le habla a Damian.

**Cada rol tiene su propio LLM y cada uno es intercambiable (P10).** Resolución del modelo por rol: ver §5.

### 2.1 L1 — Orquestador (`ORQ-*`)

| ID | Pieza | Archivo |
|---|---|---|
| ORQ-1 | Servidor (FastAPI, solo `127.0.0.1`, token efímero por arranque, anti DNS-rebinding) y todos los endpoints | `backend/orquestador/server.py` |
| ORQ-2 | **Ruteo a brigada** (clasificador) | `backend/orquestador/routing.py` |
| ORQ-3 | Comandos de gestión de brigadas (`/crear-brigada`, `/activar-brigada`…) interpretados por código | `backend/orquestador/brigadas.py` |
| ORQ-4 | **Watchdog** (vigila turnos, corta y avisa) | `backend/orquestador/watchdog.py` |
| ORQ-5 | Cocineros por brigada (desde el spec) | `backend/orquestador/agentes.py` |
| ORQ-6 | UI (HTML único con pestañas) | `backend/orquestador/ui.html` |
| ORQ-7 | Arranque "como app" y detección de proceso viejo | `backend/orquestador/launcher.py`, `backend/run_orquestador.py` |
| ORQ-8 | Registro liviano de tools (no carga pentest/malware/desktop/phone) | `backend/orquestador/slim_tools.py` |
| ORQ-9 | 🎯 **Comunicador / voz del orquestador** (a construir): convierte el reporte interno del jefe en el mensaje personal para Damian | (nuevo) `backend/orquestador/voz.py` (nombre sugerido) |

**Responsabilidades (decididas):**
1. **Clasificar y rutear** el pedido a una brigada (override > reglas con peso > clasificador LLM > default) y abrir el turno.
2. **Ser la VOZ con el usuario.** Recibe el **reporte interno** del jefe y le comunica a Damian el resultado **de forma personal y cercana, "en sus formas"**
   (español rioplatense con voseo, directo, sin relleno; ver `RAPHAEL_PERSONA` en `backend/app/agent.py` y las directrices de Damian en `backend/brigades/directrices.py`).
   **El mensaje final al usuario lo produce el orquestador.** Su LLM propio hace este paso.
3. **Fidelidad al reporte:** el orquestador **no inventa ni altera** hechos, cifras, fuentes, hashes ni fallos del reporte; lo que el reporte marca como *propuesta que requiere
   aprobación* se presenta como tal (nunca como hecho consumado). Los textos de **gates** (hashes de activación, confirmaciones, errores del watchdog) se muestran **literales**.
4. Aplicar el watchdog, vigilar el turno y mantener la conversación con el usuario (memoria de la conversación a través de brigadas).

**Entrada:** `POST /api/chat {message, brigade?}`. **Salida:** stream NDJSON: `route`, `start`, `tool`, `tool_result`, `reporte` (🎯, el reporte interno del jefe), `final` (🎯, el mensaje del orquestador), `error`, `watchdog`.
**Ruteo (✅):** (1) override `/cerebro …`, `/investigacion …`, `/<id-creada> …` o `brigade` del request; (2) reglas con peso (`_RULES`); (3) clasificador LLM (`llm_classify`, timeout 45 s); (4) default **Cerebro**.
Las brigadas **creadas nunca entran al auto-ruteo**. **Concurrencia (✅):** un turno a la vez por brigada (`asyncio.Lock`).

### 2.2 L2 — Jefe de brigada (`JEFE-*`)

| ID | Pieza | Archivo |
|---|---|---|
| JEFE-1 | `BrigadeChief`: mini-loop LLM→tool→LLM (máx. 12 iteraciones), memoria en disco (últimos 16 mensajes en `backend/data/brigades/<id>.json`), tope de 6000 caracteres por resultado de tool | `backend/brigades/chief.py` |
| JEFE-2 | `GenericChief`: ejecuta un `BrigadeSpec`; con ayudantes delega (✅ hoy 1 por pedido), sin ayudantes responde él (⚠️ `DIV-01`) | `backend/brigades/engine.py` |
| JEFE-3 | `BrigadeSpec` y dataclasses (identidad, prompt, modelo, tools, ayudantes, ruteo, skills, `helper_timeout`, `watch`, `tool_modules`, `validation`) | `backend/brigades/spec.py` |
| JEFE-4 | Registro de brigadas (declarativas + legacy + creadas activas, re-verificadas en cada uso) | `backend/brigades/registry.py` |
| JEFE-5 | Config de modelo por rol y etiqueta del modelo efectivo | `backend/brigades/config.py` |

**Responsabilidades (decididas):**
1. **Coordinar** a sus ayudantes efímeros: recibe el pedido del orquestador, elige y **encarga** sub-tareas (1..n, en paralelo si son independientes).
2. **Sintetizar** los resultados de sus ayudantes **con su ESPECIALIZACIÓN de dominio** (el jefe de Cerebro razona como memoria; el de Investigación como investigador/forense; el de Seguridad como auditor).
3. **Reportar al orquestador** con un **reporte interno estructurado** (§3.2). **No le habla al usuario** y no redacta el mensaje final.
4. Tiene su **PROPIO LLM** (intercambiable por config) para planificar y sintetizar; **no tiene tools de dominio** (solo delega y lee su memoria); recuerda qué viene haciendo la brigada.
5. Contener fallos: un ayudante colgado/caído/cortado por el watchdog no tumba al jefe; el reporte lo informa.

**Entrada:** `(message, on_event)` del orquestador. **Salida:** el **reporte interno** + eventos del feed (hoy: `(texto_final, historial)` ⚠️ `DIV-02`).

### 2.3 L3 — Ayudantes efímeros (`AYU-*`)

| ID | Ayudante | Brigada | Archivo |
|---|---|---|---|
| AYU-1 | `investigacion-scout` (research web trazable) | Investigación | `backend/brigades/investigacion.py` + `backend/scout/` |
| AYU-2 | `investigacion-forense` (evidencia digital de un caso; solo PROPONE) | Investigación | `backend/brigades/investigacion.py` |
| AYU-3 | `seguridad-escaneo` (nmap, ZAP, sqlmap solo detección; gate de scope) | Seguridad | `backend/brigades/seguridad.py` |
| AYU-4 | `seguridad-reporte` (informe pasivo, no escanea) | Seguridad | `backend/brigades/seguridad.py` |
| AYU-n | los ayudantes de cada brigada **creada** | creadas | `backend/brigades/factory.py` |

**Responsabilidad (decidida):** hacer el trabajo real con la **caja de tools más chica posible**, con su propio LLM (intercambiable), config y timeout; nacer con el pedido y morir con la
respuesta; **reportar al jefe** (nunca al usuario ni al orquestador). **Entrada:** sub-tarea + contexto previo marcado como DATO. **Salida:** resultado (hoy texto libre; 🎯 resultado estructurado, §3.2).
**Ciclo de vida (✅):** `GenericChief._spawn(modo)` crea un `BrigadeChief` con `AyudanteSpec.config()` y `AyudanteSpec.client_model()`; corre bajo `asyncio.wait_for(timeout)` (default 900 s,
`BRIGADE_AYUDANTE_TIMEOUT_SECONDS`); un fallo/timeout se contiene; se registra en el registro vivo (`brigades/live.py`).

### 2.4 L4 — Skills / Tools (`SKL-*`)

| ID | Pieza | Archivo |
|---|---|---|
| SKL-1 | Registro de tools (`@register_tool`), esquemas OpenAI, `call_tool` | `backend/app/tools/__init__.py` (+ un módulo por dominio en `backend/app/tools/`) |
| SKL-2 | Catálogo liviano de tools y política de privilegios para brigadas creadas (denegadas / sensibles / normales), leído con `ast` | `backend/brigades/tool_catalog.py` |
| SKL-3 | Dominios reutilizados: vault Obsidian (`backend/app/obsidian/`), investigación forense (`backend/app/investigation/`), pentest y red (`backend/app/pentest/`, `backend/app/network/`), búsqueda (`backend/app/search_providers/`) | — |

**Responsabilidad:** una acción acotada con su propio gate (dry-run→confirm, scope, flags). Las tools sensibles se marcan ⚠ en la revisión de una brigada creada.

---

## 3. El MODELO DE INTERACCIÓN (decidido)

### 3.1 Reglas de diseño (decisión final de Damian)

> **Flujo: Ayudantes → Jefe → Orquestador → Usuario.** El jefe de brigada **coordina y reporta**; el **orquestador es la voz** con el usuario.

1. **El jefe nunca responde directo ni le habla al usuario.** Recibe el pedido, lo delega en uno o más ayudantes efímeros, junta sus resultados, los **sintetiza con su especialización de dominio** y
   **le reporta al orquestador** con un reporte interno/estructurado.
2. **El orquestador es la VOZ con el usuario.** Además de clasificar y rutear, toma el reporte interno del jefe y le comunica a Damian el resultado **de forma personal y cercana, "en sus formas"**.
   El mensaje final lo produce el orquestador.
3. **Cada rol tiene su propio LLM** (orquestador, jefe, ayudante) y **cada uno es siempre intercambiable por configuración** (default nemotron/NVIDIA).
4. El jefe **no tiene tools de dominio**; toda acción sobre el mundo la hacen los ayudantes con su caja mínima. Una brigada **siempre** tiene ≥1 ayudante (no existe la brigada "directa").
5. La síntesis y la comunicación son **fieles**: citan las fuentes que trajeron los ayudantes, atribuyen cada hallazgo, separan lo encontrado de lo inferido, admiten lo no encontrado y **reportan los fallos**
   (timeout, error, corte del watchdog) en vez de esconderlos. El orquestador **no altera** el contenido del reporte; solo lo comunica.
6. Los ayudantes pueden correr **en paralelo** cuando las sub-tareas son independientes.
7. Lo que el reporte marca como **propuesta que requiere aprobación** (fusiones, fixes, activaciones) llega al usuario **como propuesta**; aprobar es siempre de Damian (gates intactos).

### 3.2 Flujo decidido, paso a paso 🎯

```
 1. Damian ─ pedido ───────────────────────────────────────────────────────────────▶ ORQUESTADOR (/api/chat)
 2. ORQUESTADOR  clasifica y rutea a una brigada (override > reglas > clasificador LLM > default); abre el turno; el watchdog empieza a vigilar
 3. JEFE         PLANIFICA con su LLM y DELEGA: 1..n sub-tareas a ayudantes efímeros (contexto previo como DATO)         [hoy: 1 ayudante por regex]
 4. AYUDANTES    TRABAJAN con sus tools (menor privilegio) y REPORTAN AL JEFE un resultado estructurado:
                  {ayudante, ok, texto, fuentes[], artefactos[], errores[]}                                              [hoy: texto libre]
 5. AYUDANTES    MUEREN (registro vivo → "terminaron hace poco")
 6. JEFE         SINTETIZA con su ESPECIALIZACIÓN (paso de LLM sin tools; los resultados entran como DATO) y emite el REPORTE INTERNO:
                  {brigada, resumen, hallazgos[], fuentes[], confianza, no_encontrado[], propuestas_pendientes[], ayudantes[], fallos[]}
 7. JEFE         recuerda (memoria persistente: pedido, quién lo resolvió, conclusión) y ENTREGA EL REPORTE al orquestador (evento `reporte`)
 8. ORQUESTADOR  COMUNICA: su LLM convierte el reporte en el mensaje personal y cercano para Damian, "en sus formas", sin alterar hechos, cifras, fuentes ni fallos
 9. ORQUESTADOR  emite `final` = su mensaje ─▶ UI / voz ("Leer respuestas") / historial de la conversación
```

**Invariantes del flujo:**
(a) los pasos 6 y 8 ocurren siempre, también si todos los ayudantes fallan (el jefe reporta el fallo; el orquestador lo comunica);
(b) ningún texto de un ayudante ni del jefe llega al usuario sin pasar por el orquestador; un `final` solo lo emite el orquestador;
(c) el reporte interno es la **fuente de verdad**: queda en el feed (inspectable en la UI) y el mensaje del orquestador se deriva de él;
(d) los gates de cada tool siguen intactos; el orquestador y el jefe **no pueden aprobar** nada por el usuario;
(e) los mensajes de **comandos y gates** (`/crear-brigada`, `/activar-brigada <id> <hash>`, errores del watchdog) los produce **código** y se muestran **literales**: el LLM del orquestador no los parafrasea.

### 3.3 Estado actual vs objetivo, por brigada

| Brigada | Estado actual ✅ (código) | Objetivo decidido 🎯 | Divergencia |
|---|---|---|---|
| **Cerebro** (`backend/brigades/cerebro.py`) | **Sin ayudantes: el jefe responde él mismo** al usuario con su mini-loop y las tools `obsidian_buscar_asociativo` + `obsidian_search_notes`; la persona y las directrices viven en su prompt. | El jefe **delega** la recuperación en ayudante(s) efímero(s) (propuesta: *recuperador* asociativo+keyword que devuelve evidencia con nota fuente y extracto textual), **sintetiza** con su especialización de memoria y **reporta al orquestador**; pierde sus tools de búsqueda. La persona/directrices pasan a la voz del orquestador. | **DIV-01**, **DIV-06** |
| **Investigación** (`brigades/investigacion.py`) | Delega en **un** ayudante (Forense por defecto; Scout solo ante señal web) por regex y **devuelve el texto crudo del ayudante como respuesta final**; el jefe **no tiene LLM propio**. | El jefe (con LLM propio) puede delegar en Scout **y** Forense, sintetiza como investigador/forense y **reporta al orquestador**, que comunica. | **DIV-02**, **DIV-03**, **DIV-07**, **DIV-08** |
| **Seguridad** (`brigades/seguridad.py`) | Igual que Investigación (reporte por defecto, escaneo ante señal explícita; texto crudo); no está en el auto-ruteo ni tiene pestaña activa. | El jefe sintetiza como auditor (qué se escaneó, qué no, riesgos, próximos pasos) y reporta; el gate de scope no cambia. | **DIV-02**, **DIV-07**, **DIV-08** |
| **Brigadas creadas** (`brigades/factory.py`) | Esquema con dos formas: **directa** (jefe responde con tools) o **delega**; el jefe delegante no tiene LLM propio. | Solo la forma "delega": ≥1 ayudante; jefe con LLM propio y especialización declarada; reporte al orquestador. | **DIV-04**, **DIV-08** |
| **Orquestador** (`orquestador/server.py`, `routing.py`) | Su LLM solo **clasifica** (y diseña borradores); el `final` del turno lo produce el jefe/ayudante. | Su LLM además **comunica**: produce el `final` desde el reporte interno, con persona y memoria de conversación. | **DIV-07**, **DIV-09** |

### 3.4 Registro de divergencias

| ID | Divergencia (actual → objetivo) | Dónde está | Qué hay que cambiar (sin implementar aún) |
|---|---|---|---|
| **DIV-01** | Cerebro responde directo → debe delegar, sintetizar y reportar | `brigades/cerebro.py` (`tools=CEREBRO_TOOL_NAMES`, sin `ayudantes`); `GenericChief.run` rama `not spec.delegating` | Darle ayudante(s) y quitarle las tools de dominio al jefe |
| **DIV-02** | Los jefes con ayudantes devuelven el texto **crudo** del ayudante y es la respuesta final → deben sintetizar con su especialización y **reportar al orquestador** | `brigades/engine.py` `GenericChief.run`; prompts `INVESTIGACION_PROMPT`, `SEGURIDAD_PROMPT` ("devolvés su resultado") | Paso de síntesis del jefe (LLM propio, sin tools) + reporte interno; cambiar los prompts |
| **DIV-03** | Un ayudante por pedido, ruteo regex sin planificación ni paralelismo → 1..n delegaciones planificadas por el jefe | `brigades/spec.py` `Routing.clasificar`; `engine.py` | Planificación del jefe (LLM + reglas como red de seguridad) y ejecución paralela |
| **DIV-04** | El esquema de borradores admite brigadas "directas" → exigir ≥1 ayudante | `brigades/factory.py` `validate_draft`, `compile_spec`; `ejemplos.py` `EJEMPLO_DIRECTA`; `designer.py` | Exigir ≥1 ayudante; ajustar diseñador, ejemplos, validación genérica y tests |
| **DIV-05** | El feed no distingue plan / delegación / resultado de ayudante / reporte / comunicación | `orquestador/ui.html` `onEvent`; eventos de `engine.py` | Eventos `plan`, `delegacion`, `resultado_ayudante`, `reporte`, `final` (del orquestador) |
| **DIV-06** | La persona y las directrices de Damian viven en el prompt de **Cerebro** (pensadas para responder) → deben gobernar la **voz del orquestador** | `brigades/cerebro.py` (`build_cerebro_system_prompt`), `brigades/directrices.py` | Reubicar persona/directrices en el prompt del orquestador-comunicador; el jefe de Cerebro recibe solo su especialización |
| **DIV-07** | **El orquestador no es la voz**: su LLM solo clasifica; el `final` lo emite el jefe/ayudante → el orquestador produce el mensaje final | `orquestador/server.py` `/api/chat`, `routing.py` | Paso de comunicación del orquestador (ORQ-9) y evento `final` suyo |
| **DIV-08** | El jefe que delega **no tiene LLM propio** y no hay config unificada de modelo por rol → cada rol con LLM propio e intercambiable | `brigades/spec.py` (`client`), `engine.py` (`model`), `brigades/config.py` | Resolución de modelo por rol (§5): orquestador, jefe, ayudante; swappable por config |
| **DIV-09** | No existe el **contrato del reporte interno** (jefe→orquestador) ni del resultado del ayudante | — | Definir y validar los esquemas (reporte y resultado), con límites de tamaño y versión |

---

## 4. Cocineros, efímeros, registro vivo y watchdog

### 4.1 Cocineros (permanentes) vs efímeros, por brigada

| Brigada | Cocineros (permanentes) | Efímeros que puede crear | Modelo efectivo hoy |
|---|---|---|---|
| Cerebro | el jefe (memoria persistente) — ✅ hoy también hace el trabajo y habla al usuario ⚠️ `DIV-01` | 🎯 recuperador (+ opcionales) | jefe: nemotron/NVIDIA |
| Investigación | el jefe (✅ rutea, **sin LLM propio** hoy ⚠️ `DIV-08`) | `scout` (Groq gpt-oss-120b), `forense` (nemotron/NVIDIA) | ver §5 |
| Seguridad | el jefe (✅ rutea, **sin LLM propio** hoy ⚠️ `DIV-08`) | `escaneo`, `reporte` (nemotron/NVIDIA) | ver §5 |
| Creadas | el jefe | los ayudantes del borrador | `shared` por default (nemotron/NVIDIA) |

El panel **Cocineros** de la UI sale del spec (`ORQ-5`, `GET /api/cocineros`): lista los agentes permanentes con rol, memoria, tools y **modelo efectivo + proveedor**.
Un ayudante cuyo `config().persistent` sea verdadero contaría como cocinero; hoy ninguno lo es. Con el modelo decidido, **todo jefe tiene LLM propio** (planifica y sintetiza) y la UI
debe mostrar su modelo efectivo en lugar de "sin LLM propio". El orquestador (L1) tampoco es un cocinero de una brigada: es la capa que habla con el usuario.

### 4.2 Registro vivo de efímeros (`brigades/live.py`)

`GenericChief.run` registra al spawnear un ayudante (`live.start`), actualiza lo que hace con cada evento de su feed (`live.touch`: tool en curso o "pensando") y lo
quita al terminar (`live.finish`: `ok` / `timeout` / `error` / `cancelado`); el watchdog anota ahí por qué cortó (`live.mark_cut`). `GET /api/efimeros` devuelve
el tablero (activos + últimos 12 terminados); la UI lo consulta cada 2 s (pestaña ⚡ y chip de la cabecera). Alcance: el proceso del orquestador. Es solo observación.

### 4.3 Watchdog (`backend/orquestador/watchdog.py`)

Supervisa cada turno de `/api/chat` contra lo que el spec declara (`BrigadeSpec.watch` = `WatchSpec`; default por `.env`):
**loop** (misma llamada o respuesta repetida, ≥4 en las últimas 10, incluye ciclos A-B-A-B), **falta de progreso** (300 s sin eventos), **timeout** (timeout de ayudante + 30 s de margen) y **errores seguidos** (5).
Corta cancelando la tarea del jefe (y con ella a su ayudante), emite un evento `watchdog` + un `final` que cierra el feed, lo registra en `backend/data/watchdog/intervenciones.jsonl` y
`GET /api/watchdog`. Es **defensivo**: no ejecuta tools ni toca gates. Apagable con `WATCHDOG_ENABLED=0`. Con el modelo 🎯 hay que vigilar también la fase de síntesis y las delegaciones paralelas (`OPT-09`).

---

## 5. Ruteo de modelos (qué modelo corre cada rol)

### 5.0 Cómo se resuelve hoy

Resolución real en `backend/brigades/config.py` y `backend/app/harness/model_registry.py`; la UI muestra el modelo **efectivo + proveedor** (`GET /api/meta`).

| Rol | Cómo se elige | Valor hoy (`backend/.env`) |
|---|---|---|
| **Orquestador** (clasificador de ruteo + diseñador de brigadas) | `load_orquestador_client_model()` → `ORQUESTADOR_LLM_BASE_URL/MODEL/API_KEY` (la key **solo** de ese `.env`; no cae al `LLM_API_KEY` global) | `nvidia/nemotron-3.5-super-vl-120b-a12b` por **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) |
| **Jefe de brigada** (planifica y sintetiza) | hoy: el jefe que delega **no llama a ningún LLM** ⚠️ `DIV-08`; 🎯 LLM propio por jefe, intercambiable (`BRIGADE_LLM_*` por default, override por brigada) | 🎯 nemotron/NVIDIA por default |
| **Orquestador como voz** (comunicador, 🎯) | mismo `ORQUESTADOR_LLM_*` que el clasificador (o un rol aparte si se prefiere otro modelo para la voz) | 🎯 nemotron/NVIDIA por default |
| **Jefe y ayudantes con `modelo: shared`** (Cerebro, Forense, Seguridad, brigadas nuevas por default) | `load_chief_client_model()` → `BRIGADE_LLM_*` (si no, el chat global) | nemotron/NVIDIA |
| **Roles `modelo: local`** (tier 1) | `load_local_client_model()` → `client_and_model_for_tier(1)` → `TIER1_*` | hoy **también** nemotron/NVIDIA (antes `jarvis-text-v2` en Ollama) |
| **Scout** (ayudante de Investigación) | `scout/config.py` → `SCOUT_LLM_*` (BYOM; set chico de 8 tools) | `openai/gpt-oss-120b` por **Groq** |
| **Chat del monolito** (:8000, Raphael completo) | `LMSTUDIO_BASE_URL/MODEL`, `LLM_API_KEY` | nemotron/NVIDIA (el proceso del monolito puede estar desactualizado: se reinicia aparte) |
| **Embeddings** (memoria semántica del vault) | `EMBEDDING_BASE_URL/MODEL` | `text-embedding-nomic-embed-text-v1.5` en **LM Studio :1234** (local; nemotron no es modelo de embeddings) |
| **Voz** (STT/TTS) | `voice/engine.py` → worker | faster-whisper `small` (CPU, int8) y Piper `es_AR-daniela-high`, todo local |
| Tiers del monolito | `DEFAULT_TIER_MODELS` en `backend/app/harness/routing.py` | 0 determinista · 1 local (`jarvis-text-v2`, hoy redirigido por `TIER1_*`) · 2 free rotativo · 3 Sonnet 5.5 · 4 Opus 5.5 |

### 5.1 Principio: el modelo de CADA rol es siempre intercambiable (decidido)

Orquestador, cada jefe y cada ayudante tienen **su propio LLM** y cada uno se puede cambiar **por configuración, sin tocar código** (nemotron/NVIDIA es el default, no una dependencia).
Esto incluye pasar un rol a un modelo **local** (privacidad), a otro proveedor o a otro tamaño (por ejemplo un clasificador barato, jefes de mayor calidad).

Resolución del modelo de un rol (de más específico a más general):
1. **Override del rol:** `AyudanteSpec.client_model` / el modelo declarado del jefe en su `BrigadeSpec` / variables por rol (`ORQUESTADOR_LLM_*` ✅ existe; por brigada y por ayudante 🎯 `BRIGADE_<ID>_LLM_*`, `AYUDANTE_<ID>_LLM_*`).
2. **Default del tipo de rol:** orquestador → `ORQUESTADOR_LLM_*`; jefes y ayudantes `shared` → `BRIGADE_LLM_*` (✅); `local` → `TIER1_*` (✅).
3. **Default global:** `LMSTUDIO_*` / `LLM_API_KEY` (chat global) y, por último, nemotron en NVIDIA.

Requisitos: (a) ningún rol hardcodea un modelo ni un endpoint; (b) la UI muestra el modelo **efectivo + proveedor** de cada rol (`GET /api/meta`, panel Cocineros, cabecera del orquestador); (c) cambiar el modelo de un rol
no cambia su contrato (mismos esquemas de resultado y de reporte); (d) la key de cada proveedor solo sale del `.env` y no cae a la de otro proveedor; (e) hay tests con modelos falsos que prueban el intercambio por rol.

### 5.2 Notas

Notas: (1) **privacidad**: con todo en nemotron/NVIDIA, lo que lee Cerebro y los mensajes salen a NVIDIA; los embeddings y la voz siguen locales; está documentado y es reversible
(`.env.example`). (2) Cambiar el modelo de los jefes a Sonnet (tier 3) es **un solo punto**: el cuerpo de `load_chief_client_model`. (3) `Seguridad`/`Investigación` usan `shared` para
sus ayudantes; el jefe que delega **no llama a ningún LLM** hoy (🎯 decidido: todo jefe tiene LLM propio e intercambiable, `DIV-08`, `OPT-19`).

---

## 6. Creación de brigadas, validación y documento vivo

### 6.1 Brigada declarativa (spec) — `CRE-*`

Una brigada **no es una clase**: es un `BrigadeSpec` (dato) que ejecuta `GenericChief`. Campos: `id`, `name`, `purpose`, `prompt` (str o builder vivo), `client` (`local`/`shared`),
`tools` (techo), `vault_path`, `persistent`, `ayudantes` + `routing` (reglas regex en orden, gana la primera, `default`), `skills`, `helper_timeout`, `watch`, `tool_modules`, `validation`.
Archivo: `backend/brigades/spec.py`. Declaradas hoy: `cerebro`, `investigacion`, `seguridad` (`backend/brigades/registry.py::_SPECS`); `scout` es legacy.

### 6.2 Crear una brigada desde el orquestador (Etapa 2) — `CRE-1…`

| ID | Pieza | Archivo |
|---|---|---|
| CRE-1 | Fábrica: borrador JSON → `BrigadeSpec` (esquema cerrado, validación estricta, revisión con hash, bloque de seguridad fijo en todos los prompts) | `backend/brigades/factory.py` (+ `ejemplos.py`) |
| CRE-2 | **Gate borrador → activa**: aprobación **firmada** (Ed25519, clave protegida con DPAPI) sobre el hash exacto, re-validada en cada uso (falla cerrado); el almacén está en `FS_DENIED_PATHS` | `backend/brigades/draft_store.py` → `backend/data/brigades_creadas/` |
| CRE-3 | Política de tools (denegadas / sensibles / normales) | `backend/brigades/tool_catalog.py` |
| CRE-4 | Diseñador: descripción en lenguaje natural → borrador (modelo del orquestador, hasta 3 intentos con los errores de validación devueltos al modelo; sin camino a la activación) | `backend/brigades/designer.py` |
| CRE-5 | Comandos y API (`/crear-brigada`, `/activar-brigada <id> <hash>`, `/desactivar-brigada`, `/descartar-brigada`, `/brigadas`; `/api/brigadas*`) y pestaña **Brigadas** | `backend/orquestador/brigadas.py`, `server.py`, `ui.html` |

Línea roja: un borrador **no es operativo** (no rutea, no corre, no tiene pestaña, el router responde 404) hasta que Damian lo activa. Una brigada creada **se usa por `/<id>` o su pestaña, nunca por auto-ruteo**.
Default de modelo de una brigada nueva: `shared` (`BRIGADA_MODELO_DEFAULT`). 🎯 `DIV-04`: el esquema debe exigir ≥1 ayudante.

### 6.3 Framework de validación — `VAL-*`

Cada brigada declara su **escena de validación** (`ValidationSpec`: escena fija con hash, pasos, criterio, prerrequisitos). El framework corre cualquier brigada desde su spec, en un **entorno aislado**
(vault, estado, stores y `audit.log` reales no se tocan; si cambian, la validación falla), compara contra un **baseline** (primera corrida verde) y detecta regresiones.
Un paso sin prerrequisito queda **SIN VALIDAR** (código de salida 2), nunca rojo ni verde falso. Archivos: `backend/validation/framework.py`, `harness.py`, `todas.py`, `registro.py`, `generic.py`
(pasos declarativos para brigadas creadas), un módulo por brigada (`cerebro.py`, `investigacion.py`, `seguridad.py`), escenas en `backend/brigades/*_scene.py`, baselines en `backend/validation/baselines/`.
Comando: `python -m validation.todas [cerebro investigacion …]`. Registro doble: JSON por corrida (`backend/validation/results/`, gitignoreado) + un Word por ronda (`Documents\Validacion-Brigadas\`).
Estado (2026-11-12): Cerebro PASA 4/4 con baseline; Investigación INCOMPLETA (Scout sin validar: falta `BRAVE_SEARCH_API_KEY`); Seguridad con validación lista y sin corrida real.
🎯 La validación debe cubrir el modelo de delegación: el paso de síntesis (fiel, con fuentes, honesto ante fallos) es un criterio nuevo (`OPT-02`, `OPT-12`).

### 6.4 Documento vivo — `DOC-*`

El documento maestro `CONTEXTO-MAESTRO-RAPHAEL.md` tiene tres bloques `AUTO` (decisiones, mapa de archivos, estado de componentes) que regenera `tools/actualizar_contexto.py`
(`git log` + `git ls-files` + última validación real + lista blanca de `.env` sin claves) desde un **hook de pre-commit** (`.githooks/pre-commit`: stagea el cambio en el mismo commit, no entra en bucle, nunca bloquea un commit).
Fuentes curadas: `docs/contexto/`. El Word de lectura se regenera con `--word`. **Este** documento (`docs/ARQUITECTURA-RAPHAEL.md`) es la especificación de arquitectura y se mantiene a mano.

### 6.5 Otras capacidades (contexto)

| Pieza | Qué es | Archivo |
|---|---|---|
| Voz local (`VOZ-*`) | dictado (faster-whisper) y lectura de respuestas (Piper es-AR), subproceso offline en CPU | `backend/voice/engine.py`, `worker.py`; `docs/VOZ-LOCAL.md` |
| Cerebro proactivo | consolidación ("sueño"), curiosidad, notas propias; **apagado por default** | `backend/brigades/cerebro_proactive.py`, `backend/app/obsidian/consolidation.py` |
| Servicio de memoria | puente **write-only** hacia Cerebro: las brigadas escriben su captura; solo Cerebro lee la memoria completa | `backend/brigades/memory_service.py` |
| Cerebro no biológico (8 fases) | spreading activation, hebbiano, consolidación, olvido, sucesora, sorpresa, analogía, esquema+composición | `backend/app/obsidian/*.py` |
| Monolito (Raphael completo, :8000) | loop del agente con ~50 tools, control de PC/celular, pentest, malware, trading, etc. | `backend/app/`, `backend/run.py` |

---

## 7. MAPA DE CÓDIGO (dónde vive cada pieza)

| Quiero tocar… | Archivo(s) |
|---|---|
| El ruteo a brigada (reglas, clasificador LLM, default) | `backend/orquestador/routing.py` |
| El endpoint del chat, el feed NDJSON, los locks por brigada | `backend/orquestador/server.py` (`/api/chat`) |
| Cómo un jefe delega / el mini-loop / la memoria del jefe | `backend/brigades/engine.py` (`GenericChief.run`), `backend/brigades/chief.py` (`BrigadeChief.run`, `_persist_memory`) |
| La estructura de una brigada (spec) | `backend/brigades/spec.py` |
| Los prompts de los jefes | `backend/brigades/cerebro.py` (`CEREBRO_PROMPT`, `build_cerebro_system_prompt`), `investigacion.py` (`INVESTIGACION_PROMPT`), `seguridad.py` (`SEGURIDAD_PROMPT`) |
| Los prompts de los ayudantes | Forense: `backend/app/skills.py` (`_INVESTIGATION_PROMPT_SLIM`) + `brigades/investigacion.py` (`_FORENSE_PROMPT_EXTRA`); Scout: `backend/scout/identity.py`; Seguridad: `brigades/seguridad.py` (`ESCANEO_PROMPT`, `REPORTE_PROMPT`); creadas: `brigades/factory.py` (`SEGURIDAD_COMUN`) |
| Las reglas de ruteo de un jefe a sus ayudantes | `brigades/investigacion.py` (`_FORENSE_MARKERS`, `_SCOUT_MARKERS`, `ROUTING`), `brigades/seguridad.py` (`_ESCANEO_MARKERS`, `ROUTING`) |
| Cerebro: recuperación y consolidación | `backend/app/obsidian/spreading.py`, `consolidation.py` (`select_pairs`, `find_clusters`), `embeddings.py`, `vault.py`; config en `backend/app/config.py` (`consolidation_*`) |
| Modelos y proveedores | `backend/brigades/config.py`, `backend/app/harness/model_registry.py`, `backend/app/harness/routing.py`, `backend/.env` / `.env.example` |
| La **voz del orquestador** (comunicador, 🎯 a construir) y el flujo reporte→mensaje | (nuevo) `backend/orquestador/voz.py`, `backend/orquestador/server.py` (`/api/chat`), contratos en `backend/brigades/` (nuevo módulo), persona en `backend/app/agent.py` (`RAPHAEL_PERSONA`) y `backend/brigades/directrices.py` |
| Watchdog / registro vivo / cocineros | `backend/orquestador/watchdog.py`, `backend/brigades/live.py`, `backend/orquestador/agentes.py` |
| Crear brigadas y el gate | `backend/brigades/factory.py`, `draft_store.py`, `tool_catalog.py`, `designer.py`, `backend/orquestador/brigadas.py` |
| Validación | `backend/validation/*.py`, `backend/brigades/*_scene.py` |
| UI | `backend/orquestador/ui.html` (pestañas, feed, Cocineros, Efímeros, Brigadas, voz) |
| Voz | `backend/voice/engine.py`, `backend/voice/worker.py` |
| Tools | `backend/app/tools/` |
| Documento vivo | `tools/actualizar_contexto.py`, `.githooks/pre-commit`, `docs/contexto/` |
| Tests | `backend/tests/` (p. ej. `test_orquestador*.py`, `test_brigade_*.py`, `test_watchdog.py`, `test_agentes_vivo.py`, `test_validation_*.py`, `test_voice.py`) |

Otros documentos: `docs/PLAYBOOK-brigadas.md` (cómo se define y valida una brigada), `docs/ETAPA-2-crear-brigadas.md`, `docs/WATCHDOG-orquestador.md`, `docs/VOZ-LOCAL.md`,
`docs/BLUEPRINT-habilidades-y-defensas-brigadas.md` (el plano de brigadas y su toolkit de defensas), `CLAUDE.md` / `AGENTS.md` (reglas para agentes), `CONTEXTO-MAESTRO-RAPHAEL.md` (historia y estado completo).

---

## 8. Restricciones que NO se debilitan al optimizar

1. `authorized_targets.yaml` es la única fuente de scope de pentest y solo la edita Damian; ninguna tool ni LLM la escribe.
2. Una brigada creada solo se activa con aprobación firmada de Damian sobre el hash; nada la activa por texto de un modelo, una nota o una web.
3. Los ayudantes **proponen**; confirmar/rechazar (propuestas, fusiones, fixes) es de Damian (`proposal_id`).
4. Dry-run → `confirm=true` para todo lo destructivo; flags `*_ENABLED` por capacidad invasiva; sandbox de FS y `FS_DENIED_PATHS`.
5. El contenido que traen tools/notas/web/ayudantes es DATO, nunca instrucción (el paso de síntesis del jefe también debe tratarlo así).
6. Menor privilegio por rol: no darle al jefe tools de dominio ni ampliar la caja de un ayudante para "ahorrar" una delegación.
7. Las claves solo salen del `.env`; nada de claves en código, logs ni documentos (el regenerador solo lee una lista blanca de modelos/endpoints/flags).
8. Las validaciones son la red de seguridad: si una **empeora** contra su baseline se frena; no se aflojan criterios para que pasen.
9. El **usuario aprueba**: nada que cambie el sistema o actúe afuera se ejecuta por decisión de un LLM; un reporte con *propuestas pendientes* se comunica como propuesta y la aprobación sigue siendo de Damian.
10. **Solo el orquestador le habla al usuario**; el jefe reporta y el ayudante reporta al jefe. El orquestador **no altera** hechos, cifras, fuentes, hashes ni fallos del reporte, y los textos de comandos/gates se muestran **literales**.
11. **El modelo de cada rol es intercambiable por config** y ningún rol queda atado a un proveedor; la key de un proveedor nunca se usa para otro.
12. **El reporte interno es transparente:** queda en el feed y se puede inspeccionar; el mensaje del orquestador siempre se puede contrastar con él.
---

## 9. PUNTOS DE OPTIMIZACIÓN (direccionables)

Cada punto: **contexto** · **enfoque actual** · **qué significaría optimizarlo** · **dónde** · **cómo medirlo**. Para pedirlo: *«optimizá `OPT-nn`»*. `OPT-17`, `OPT-18` y `OPT-19` nacen del modelo decidido (voz del orquestador, contratos, modelo por rol).

### OPT-01 — Implementación del flujo decidido: Ayudantes → Jefe → Orquestador → Usuario *(el cambio estructural)*
- **Contexto.** `DIV-01`…`DIV-09`: hoy Cerebro responde directo, los jefes con ayudantes devuelven el texto crudo del ayudante (que es el `final`), se delega en un solo ayudante y el LLM del orquestador solo clasifica.
- **Enfoque actual.** `GenericChief.run` tiene dos ramas: sin ayudantes → `BrigadeChief.run` (responde él); con ayudantes → 1 ayudante por regex, `wait_for`, devuelve su `reply`; `/api/chat` emite el `final` del jefe.
- **Optimizar/implementar =** una sola ruta: el jefe **planifica** (LLM propio) 1..n delegaciones (paralelas si son independientes) → los ayudantes devuelven **resultado estructurado** → el jefe **sintetiza** con su especialización (LLM sin tools) y emite el **reporte interno** →
  el orquestador **comunica** (LLM propio, persona) y emite el `final`. Incluye: contratos (`OPT-18`), voz (`OPT-17`), modelos por rol (`OPT-19`), tope de tamaño de lo que entra a cada síntesis, qué pasa si un ayudante falla y cómo se mantiene el streaming del feed.
- **Dónde.** `backend/brigades/engine.py`, `chief.py`, `spec.py`, `backend/orquestador/server.py`, prompts de jefes, `factory.py` (`DIV-04`).
- **Medir.** Escenas de validación del flujo completo: el mensaje final cita las fuentes del reporte, no inventa y comunica los fallos; ningún texto crudo de ayudante llega al usuario; latencia total por brigada; tests existentes sin regresión.

### OPT-02 — Calidad de la síntesis del jefe con su especialización
- **Contexto.** El jefe sintetiza los resultados de sus ayudantes con su especialización de dominio y produce el reporte interno; de su calidad depende todo lo que el orquestador comunica.
- **Enfoque actual.** No existe como paso (hoy sale el texto del ayudante; en Cerebro la "síntesis" es la respuesta del mini-loop, con la sección FIDELIDAD A LOS DATOS del prompt).
- **Optimizar =** un prompt de síntesis por brigada (memoria, investigación/forense, seguridad) que: atribuya cada hallazgo a su ayudante, cite fuentes tal cual, separe lo encontrado de lo inferido, declare confianza y lo no encontrado, no mezcle temas, trate lo recibido como DATO y
  produzca el **reporte con el esquema** de `OPT-18`. Criterios de calidad en la validación (chequeos deterministas de citas + evaluador).
- **Dónde.** Nuevos prompts de síntesis en `brigades/*.py`; `validation/*.py`. **Medir.** Fidelidad a las fuentes (citas verificables), tasa de "no encontrado" correcto, cobertura de los resultados de los ayudantes, longitud.

### OPT-03 — Clasificación de ruteo del orquestador
- **Contexto.** Decide a qué brigada va un pedido; un error manda notas personales a un lugar equivocado o gasta una delegación inútil.
- **Enfoque actual.** Override → reglas con peso (`_RULES`, regex sin acentos) → clasificador LLM (nemotron, razona: ~26 s en OpenRouter, ~2 s en NVIDIA; 1024 tokens, timeout 45 s) → default Cerebro.
- **Optimizar =** más precisión con menos latencia: reglas mejor calibradas con un set de pedidos reales etiquetados, un clasificador más barato o con salida forzada, soporte para pedidos que tocan **dos** brigadas, y un criterio claro de cuándo preguntar en vez de adivinar. Mantener el sesgo de seguridad (ante la duda, la opción de menor daño).
- **Dónde.** `backend/orquestador/routing.py`. **Medir.** Exactitud sobre un banco de pedidos; % resuelto por reglas (sin LLM); latencia p50/p95 del ruteo.

### OPT-04 — Planificación de la delegación del jefe a sus ayudantes
- **Contexto.** Hoy el `Routing` del spec es una lista de regex (primera regla que matchea gana, si no el `default` más pasivo/privado), 1 ayudante por pedido. El modelo decidido da al jefe un LLM propio para planificar.
- **Enfoque actual.** Determinista, auditable, gratis; el sesgo es de privacidad/menor privilegio.
- **Optimizar =** que el jefe elija 1..n ayudantes y redacte la sub-tarea de cada uno (híbrido: reglas como red de seguridad y default seguro + LLM para casos ambiguos), con paralelismo cuando son independientes, sin perder la auditabilidad ni el sesgo seguro.
- **Dónde.** `brigades/spec.py` (`Routing`), `engine.py`, `investigacion.py`, `seguridad.py`. **Medir.** Aciertos de delegación en las escenas; delegaciones innecesarias; falsos "scout"/"escaneo" (los caros/peligrosos).

### OPT-05 — Umbral de consolidación de Cerebro
- **Contexto.** El "sueño" agrupa notas parecidas y escribe una conclusión; un grupo mal armado mezcla temas.
- **Enfoque actual.** `select_pairs`: coseno ≥ 0.85 **y** a lo sumo 0.08 por debajo de la mejor similitud de cualquiera de las dos notas (`CONSOLIDATION_SIMILARITY_THRESHOLD`, `_GAP`); calibrado con `nomic-embed-text-v1.5` y una escena de 3 notas (0.91 entre las correctas, 0.74–0.77 el distractor).
- **Optimizar =** calibrar con un vault real y varias escenas (no una), robustecer ante otros modelos de embeddings, considerar clustering jerárquico o umbral adaptativo por densidad, y medir falsos positivos/negativos.
- **Dónde.** `backend/app/obsidian/consolidation.py`, `backend/app/config.py`. **Medir.** Precisión/recall de grupos sobre notas etiquetadas; la validación de Cerebro (paso 4) sigue verde.

### OPT-06 — Recuperación de Cerebro (el futuro "recuperador")
- **Contexto.** Cuando Cerebro delegue (`DIV-01`), la calidad de lo que trae el recuperador define la calidad de la respuesta.
- **Enfoque actual.** `obsidian_buscar_asociativo` (spreading activation sobre el grafo + embeddings) y `obsidian_search_notes` (keyword, respaldo si no hay embeddings).
- **Optimizar =** devolver evidencia **estructurada** (id de nota, título, extracto textual, score, por qué se activó), con límites de tamaño, y afinar spreading/hebbiano para que el distractor no suba. Decidir si se dividen en dos efímeros (asociativo / keyword) o uno.
- **Dónde.** `backend/app/obsidian/spreading.py`, `vault.py`, `embeddings.py`, tools de obsidian. **Medir.** Recall@k sobre preguntas con respuesta conocida; ausencia del distractor.

### OPT-07 — Ciclo de vida y latencia de los efímeros
- **Contexto.** Cada pedido spawnea un ayudante nuevo; hay latencia de arranque y de modelo, y el trabajo es secuencial.
- **Enfoque actual.** `_spawn` crea un `BrigadeChief` + cliente por pedido (sin pool), timeout 900 s, un turno a la vez por brigada (`asyncio.Lock`), el registro vivo observa pero no optimiza.
- **Optimizar =** medir dónde se va el tiempo (config, cliente, modelo, tools), reusar clientes/conexiones, ejecutar delegaciones en paralelo, streaming de resultados parciales a la síntesis, timeouts adaptativos por ayudante, y decidir qué lock hace falta (¿un turno por brigada o por ayudante?).
- **Dónde.** `brigades/engine.py`, `chief.py`, `live.py`, `orquestador/server.py`. **Medir.** Latencia p50/p95 pedido→final por brigada; tiempo de arranque del efímero; throughput con 2–3 pedidos simultáneos.

### OPT-08 — Prompts por rol
- **Contexto.** Hay prompts del orquestador (clasificador y, con el modelo decidido, **comunicador con persona**), de cada jefe (planificación + síntesis de dominio), de cada ayudante y un bloque de seguridad común.
- **Enfoque actual.** Escritos a mano, con secciones no negociables (SEGURIDAD, FIDELIDAD A LOS DATOS, CONFIRMÁ LO QUE HICISTE); el prompt de Cerebro se rearma por turno con persona + autoconciencia + directrices vivas (⚠️ `DIV-06`); ya hubo una ablación del system prompt del monolito (-80 %) con los gates intactos.
- **Optimizar =** una matriz rol × objetivo: **orquestador** (persona, formas de Damian, fidelidad al reporte), **jefe** (especialización + síntesis + reporte), **ayudante** (operativa mínima); prompts más cortos y verificables; ablaciones medidas contra las validaciones. No tocar las secciones de seguridad.
- **Dónde.** ver el mapa de código (§7). **Medir.** Las validaciones por brigada; tokens por turno; variabilidad entre corridas.

### OPT-09 — Calibración y alcance del watchdog
- **Contexto.** Corta runs colgados; con delegación paralela y síntesis tiene más superficie.
- **Enfoque actual.** Umbrales por defecto razonables pero **sin calibrar con corridas reales de un modelo colgado**; solo ve eventos del feed (un modelo lento en una sola respuesta no emite nada); un loop con argumentos que cambian apenas no es "idéntico".
- **Optimizar =** latidos del motor durante llamadas largas, detectar loops semánticos, límites por rol desde el spec (incluido el campo `watch` en borradores), vigilar la fase de síntesis y varias delegaciones, y calibrar con datos reales (falsos cortes vs cuelgues no detectados).
- **Dónde.** `backend/orquestador/watchdog.py`, `brigades/spec.py` (`WatchSpec`), `engine.py`. **Medir.** Falsos positivos/negativos en un set de corridas reales y simuladas.

### OPT-10 — Latencia, costo y robustez del modelo por rol (default nemotron/NVIDIA)
- **Contexto.** Con tres tipos de rol con LLM propio (orquestador, jefe, ayudante) las llamadas por pedido aumentan: clasificar, planificar, trabajar, sintetizar y comunicar. Todos los modelos son intercambiables por config.
- **Enfoque actual.** Un modelo para casi todo (`BRIGADE_LLM_*`, `TIER1_*`, `ORQUESTADOR_LLM_*`), timeouts LLM generosos (1800 s en el monolito), reintentos del cliente (`max_retries=2`), cortes transitorios de red observados, riesgo de 429 en tiers free; Scout en Groq.
- **Optimizar =** elegir el modelo **por rol** aprovechando el intercambio (clasificador barato, ayudantes de recuperación rápidos, jefes de mayor calidad, orquestador con buena redacción), presupuestos de tokens y de razonamiento por rol, fallback entre proveedores, política ante 429/caídas, y paralelizar para esconder latencia. Todo reversible por `.env`.
- **Dónde.** `backend/brigades/config.py`, `backend/app/harness/model_registry.py`, `.env.example`. **Medir.** Latencia y tokens por rol; tasa de errores; costo por pedido.

### OPT-11 — Memoria del jefe, del orquestador y contexto entre turnos
- **Contexto.** El jefe "recuerda qué viene haciendo" la brigada; con el modelo decidido el **orquestador conversa con Damian a través de todas las brigadas**, así que necesita su propia memoria de conversación; los ayudantes reciben un resumen como DATO.
- **Enfoque actual.** Historial limpio por jefe: system + últimos 16 mensajes en `backend/data/brigades/<id>.json`; el ayudante recibe los últimos 4 mensajes (300 caracteres c/u) como DATO; no hay memoria de conversación del orquestador.
- **Optimizar =** memoria útil para sintetizar (qué se pidió, qué se concluyó, qué quedó pendiente, referencias a notas/casos), resúmenes en vez de truncado, límites de tamaño, **memoria de conversación del orquestador** (continuidad entre brigadas y entre turnos, sin mezclar datos de brigadas) y qué entra al contexto de cada rol (menor privilegio también en información).
- **Dónde.** `brigades/chief.py` (`_persist_memory`, `_load_memory`), `engine.py` (`_context_digest`), `orquestador/server.py`. **Medir.** Calidad en conversaciones de varios turnos; tokens de contexto.

### OPT-12 — Cobertura y variabilidad de la validación
- **Contexto.** La validación es la red de seguridad de cualquier refactor (incluido `OPT-01`).
- **Enfoque actual.** Escenas fijas por brigada, aislamiento, baseline de la **primera** corrida verde (una sola corrida por brigada), pasos genéricos para las creadas; los modelos varían entre corridas; Scout sin validar.
- **Optimizar =** repetir corridas y medir variabilidad, escenas más amplias, validar el **flujo completo** (orquestador → jefe → ayudantes → reporte → mensaje del orquestador), un evaluador de calidad de síntesis y de fidelidad del mensaje al reporte (determinista donde se pueda), pruebas de **intercambio de modelo por rol** y un tablero de tendencias.
- **Dónde.** `backend/validation/`, `backend/brigades/*_scene.py`. **Medir.** Tasa de verde sobre N corridas; detección de regresiones inyectadas.

### OPT-13 — Diseñador de brigadas y esquema de borradores
- **Contexto.** El orquestador crea brigadas desde lenguaje natural; el modelo decidido exige jefe con LLM propio y ≥1 ayudante.
- **Enfoque actual.** Un prompt con el esquema cerrado y un ejemplo, 3 intentos con feedback de errores; probado con nemotron (1 intento, borrador válido); acepta brigadas directas (`DIV-04`); sin edición de borradores en la UI.
- **Optimizar =** exigir la forma "delega" (≥1 ayudante) y el modelo por rol en el borrador, mejores plantillas de ayudantes y de síntesis de dominio, calidad de las reglas de ruteo/planificación que propone, edición/versionado de borradores, restricciones por argumento de tool (hoy solo por prompt). El gate firmado no cambia.
- **Dónde.** `brigades/designer.py`, `factory.py`, `ejemplos.py`. **Medir.** % de borradores válidos al primer intento; revisión humana mínima; validación genérica en verde.

### OPT-14 — Voz (dictado y lectura)
- **Contexto.** Hablarle a Raphael y que responda hablando, todo local. Con el modelo decidido, lo que se **lee en voz alta es el mensaje del orquestador** (la voz con el usuario).
- **Enfoque actual.** Whisper `small` en CPU (se equivoca en detalles), Piper es-AR, lectura por respuesta completa, sin manos libres; el dictado con micrófono real aún no se probó en la ventana app.
- **Optimizar =** precisión (`medium`/GPU si está libre), lectura en streaming por oraciones, VAD/palabra de activación, y que el mensaje del orquestador esté escrito para ser escuchado (corto, sin markdown).
- **Dónde.** `backend/voice/`, `ui.html`, `orquestador/voz.py` (🎯). **Medir.** WER del dictado; latencia hasta el primer sonido.

### OPT-15 — Observabilidad del flujo (feed y UI)
- **Contexto.** `DIV-05`: el feed no muestra el plan, las delegaciones, el reporte interno ni la fase de comunicación.
- **Enfoque actual.** Eventos `route`, `tool` (incluye `delegar:*`), `tool_result`, `final`, `watchdog`; tablero de efímeros en vivo; panel Cocineros.
- **Optimizar =** eventos `plan`, `delegacion`, `resultado_ayudante`, `reporte` (el reporte interno del jefe, inspectable) y `final` (el mensaje del orquestador); mostrar qué ayudante aportó qué y el modelo efectivo de cada rol; trazas por turno para depurar; todo escapado.
- **Dónde.** `engine.py`, `orquestador/server.py`, `ui.html`, `brigades/live.py`. **Medir.** Tiempo para entender por qué una respuesta salió como salió.

### OPT-16 — Política de datos por rol bajo "todo en la nube"
- **Contexto.** Damian asumió la privacidad para una prueba; con el flujo decidido el **orquestador ve el reporte de todas las brigadas** (incluido lo que Cerebro saca de notas personales), así que la exposición al proveedor de su LLM aumenta. Como el modelo de cada rol es intercambiable, el orquestador puede pasar a un modelo local.
- **Enfoque actual.** `modelo: shared` para casi todo; avisos en la revisión de brigadas creadas (rol que lee el vault en la nube); `memory_service` write-only; el clasificador manda hasta 1500 caracteres de mensajes ambiguos a NVIDIA.
- **Optimizar =** una política explícita por rol (qué datos puede ver cada modelo/proveedor), minimización de lo que se envía (extractos en vez de notas enteras, redacción de datos sensibles en el reporte), y un interruptor único y verificable para llevar cualquier rol (o todos) a un modelo local.
- **Dónde.** `brigades/config.py`, `factory.py` (advertencias), `routing.py`, `memory_service.py`, ORQ-9. **Medir.** Auditoría de qué sale a cada proveedor; cero datos marcados privados en la nube.

### OPT-17 — Voz del orquestador (comunicador personal y cercano) *(nuevo, decidido)*
- **Contexto.** El orquestador es la única voz hacia Damian: convierte el reporte interno del jefe en un mensaje personal y cercano, "en sus formas". Es lo que Damian lee y escucha.
- **Enfoque actual.** No existe: el `final` lo emite el jefe/ayudante (`DIV-07`); la persona y las directrices están en el prompt de Cerebro (`DIV-06`).
- **Optimizar/implementar =** el paso de comunicación (ORQ-9) con LLM propio e intercambiable: persona de Damian (voseo rioplatense, directo, cercano, sin relleno), **fidelidad estricta al reporte** (no altera hechos, cifras, fuentes, hashes ni fallos; presenta las propuestas como propuestas), longitud adecuada, escrito para ser leído en voz alta,
  continuidad con la conversación, y texto **literal** para comandos y gates. Evaluar con chequeos deterministas (todas las cifras y fuentes del reporte presentes, ninguna inventada) y la preferencia de Damian.
- **Dónde.** (nuevo) `backend/orquestador/voz.py`, `orquestador/server.py` (`/api/chat`), `backend/app/agent.py` (`RAPHAEL_PERSONA`), `brigades/directrices.py`. **Medir.** Fidelidad al reporte (verificable), naturalidad (juicio de Damian), latencia añadida por la comunicación.

### OPT-18 — Contratos: resultado del ayudante y reporte interno del jefe *(nuevo, decidido)*
- **Contexto.** El flujo decidido necesita dos contratos estables: **ayudante → jefe** (resultado) y **jefe → orquestador** (reporte interno estructurado). Son lo que permite cambiar el modelo de cualquier rol sin romper nada (`OPT-19`).
- **Enfoque actual.** No existen: hoy el ayudante devuelve texto libre y el jefe devuelve el texto del ayudante (`DIV-09`).
- **Optimizar/implementar =** esquemas versionados y validados. Resultado del ayudante: `{ayudante, ok, texto, fuentes[], artefactos[], errores[]}`. Reporte del jefe: `{brigada, resumen, hallazgos[], fuentes[], confianza, no_encontrado[], propuestas_pendientes[], ayudantes[], fallos[]}`
  (campos mínimos; la forma exacta la fija el implementador respetando estas propiedades). Límites de tamaño, validación estricta (un reporte inválido se reintenta o se degrada con un aviso), contenido siempre tratado como DATO, y visibilidad en el feed.
- **Dónde.** `backend/brigades/` (nuevo módulo de contratos), `engine.py`, `chief.py`, `orquestador/server.py`. **Medir.** Tasa de reportes válidos al primer intento; ningún campo perdido entre capas; tests de contrato con modelos falsos.

### OPT-19 — Modelo intercambiable por rol (orquestador, jefe, ayudante) *(nuevo, decidido)*
- **Contexto.** Principio P10: el modelo de **cada** rol es swappable por config; el default es nemotron/NVIDIA pero nunca una dependencia.
- **Enfoque actual.** Existen `ORQUESTADOR_LLM_*`, `BRIGADE_LLM_*`, `TIER1_*`, `SCOUT_LLM_*` y `AyudanteSpec.client_model`; el jefe que delega no tiene LLM propio (`DIV-08`) y no hay override por brigada ni por ayudante.
- **Optimizar/implementar =** una resolución única y documentada por rol (override del rol → default del tipo → default global, ver §5.1), override por brigada y por ayudante, el LLM del jefe, y que **cambiar el modelo no cambie el contrato** (`OPT-18`). La UI muestra el modelo efectivo de cada rol; la key de cada proveedor solo del `.env`.
- **Dónde.** `backend/brigades/config.py`, `spec.py`, `engine.py`, `orquestador/agentes.py`, `server.py` (`/api/meta`), `.env.example`. **Medir.** Tests que intercambian el modelo de un rol por uno falso y comprueban que el flujo y los contratos siguen iguales; cero modelos hardcodeados (grep).

---

## 10. Glosario

- **Orquestador (L1):** capa con LLM propio que **rutea** el pedido a una brigada y es la **voz con el usuario**: comunica el reporte del jefe de forma personal y cercana. Produce el mensaje final.
- **Brigada:** unidad de trabajo declarada por un `BrigadeSpec` (jefe + ayudantes + reglas + validación).
- **Jefe de brigada / cocinero (L2):** agente permanente con LLM propio; **coordina** a sus ayudantes, **sintetiza** con su especialización de dominio y **reporta al orquestador**; recuerda. No le habla al usuario.
- **Ayudante efímero (L3):** agente que se crea por tarea, con una caja de tools mínima y su propio LLM, trabaja, **reporta al jefe** y muere.
- **Reporte interno:** el informe estructurado jefe → orquestador (fuente de verdad del mensaje al usuario). **Resultado del ayudante:** el informe estructurado ayudante → jefe.
- **Skill / tool (L4):** acción concreta y acotada con su propio gate.
- **Modelo intercambiable:** el LLM de cada rol se cambia por configuración; el default es nemotron/NVIDIA.
- **Spec:** el dato que declara una brigada. **Validación:** su escena y criterio de éxito. **Baseline:** primera corrida verde, contra la que se detectan regresiones.
- **Gate:** barrera implementada en código (scope, aprobación firmada, dry-run→confirm, flags, FS).
- **Watchdog:** vigilante defensivo que corta runs colgados y avisa. **Registro vivo:** tablero de efímeros corriendo ahora.
- **Borrador:** brigada creada que aún **no** es operativa hasta la activación firmada de Damian.
- **`R)` / `DAMIAN:`:** marcas que señalan una **opinión de Damian** en sus documentos; toda IA debe tomarla como tal.
