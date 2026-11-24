# SPEC — Memoria episódica de Raphael (continuidad autobiográfica)

> Estado: **SPEC COMPLETO** (todas las decisiones resueltas, 2026-09-28), listo
> para implementar. Creado el 2026-09-28. Nace de la charla sobre
> qué le falta a Raphael para ser un "agente completo / un Jarvis de verdad": la
> conclusión fue que NO son más funciones, sino el tejido que las conecta en una
> sola mente — y que el agujero más grande es la **memoria**. Hoy Raphael se
> olvida entre sesiones (literal: el `CLAUDE.md` existe porque se perdió contexto
> en agosto 2026). Este spec define la memoria que lo arregla.
>
> Se elicita por preguntas, igual que `SPEC-capa-navegacion-de-agente.md`. Las
> decisiones pendientes están marcadas 🟡 [DECISIÓN] con la recomendación por
> default; las cerradas, ✅.

---

## 1. Objetivo y encuadre

Dar a Raphael **memoria episódica**: un registro durable, consultable y con
sentido de lo que Raphael *vivió* — qué le pidió Damian, qué hizo, qué decidió,
qué salió bien o mal, y por qué. Es memoria **autobiográfica**, en primera
persona ("la última vez que auditamos esto pasó X"), no un simple log.

**Distinción clave (las dos memorias):**
- **Memoria semántica** = el vault (`obsidian/`, Vault-Fenix): *conocimiento del
  mundo* — hechos, notas, apuntes técnicos y personales. YA EXISTE.
- **Memoria episódica** = ESTE spec: *experiencia del propio agente* — qué pasó,
  cuándo, en qué orden, con qué resultado. NO existe todavía.

Las dos viven en el **mismo grafo** (pedido explícito de Damian: "todo en un solo
grafo"), pero un episodio es un tipo de nodo distinto de una nota de conocimiento.

**Qué NO es esto:** no es el `_trim_history`/context window del turno (eso es
memoria de trabajo, efímera, ya resuelta en `agent.py`). La episódica sobrevive
al turno, a la sesión, y al reinicio del backend.

---

## 2. Por qué (el problema real que resuelve)

- **Continuidad:** que cada sesión no arranque como un extraño competente. Hoy
  cada charla empieza de cero salvo lo que Damian re-explique o esté en el vault.
- **Aprendizaje del propio trabajo:** "esta corrección ya la intentamos y falló",
  "a Damian no le gustó este enfoque", "este proyecto se audita así".
- **Base de la proactividad y la autoevaluación** (los otros dos gaps): no se
  puede avisar "esto pasó de nuevo" ni "la vez pasada la erré" sin recordar la
  vez pasada.
- **Anti-repetición:** no volver a proponer lo ya rechazado, no re-explicar lo ya
  explicado.

---

## 3. Anatomía de un episodio

### 3.1 ¿Qué es un episodio? (granularidad) 🟡 [DECISIÓN 1 — abierta]
Damian quiere algo "mucho más fino" que tarea+sesión, y el corte por "momentos
salientes" no lo terminó de convencer. El problema es que "fino" puede querer
decir tres cosas distintas — hay que elegir el EJE, no solo el tamaño:

**Opción A — momentos por salience (lo que se propuso).** El destilador decide qué
es un "beat" (decisión/fallo/descubrimiento/corrección) y guarda eso. *Contra:*
decide POR vos qué vale recordar; lo que no marcó, se pierde.

**Opción B — guardar TODO en crudo + resumen como ÍNDICE navegable (zoom).**
No se elige el grano en la captura: se guarda el historial completo comprimido, y
el destilador arma resúmenes por nivel (sesión→tarea) que funcionan como un ÍNDICE
que apunta hacia abajo, hasta el mensaje o el tool call exacto. El recall te da el
resumen; si hace falta el detalle, Raphael (o Damian) hace *zoom* al pedazo crudo
puntual. **Nada se tira, el grano fino es ilimitado (hasta la palabra exacta), y
solo pagás el costo cuando drillás.** Esto es literal lo que Damian intuía en su
pregunta ("acomodar toda la historia desde el inicio guardando los datos como
recuerdos"). *Contra:* más storage (barato para texto) y disciplina con el
presupuesto de contexto (ya resuelto: el crudo solo entra al hacer zoom, budgeteado).

**Opción C — memoria por ENTIDAD, no por tiempo.** El grano fino no es temporal:
cada NODO del grafo (este archivo, este proyecto, esta persona, este bug, esta
preferencia) lleva pegada su propia historia episódica. "Fino" = por-cosa, no
por-momento. Encaja con "todo en un solo grafo": preguntás "¿qué pasó con
`config.py`?" y te trae su rastro across sesiones. *Contra:* por sí sola no da la
línea de tiempo; brilla COMBINADA con B.

**Rec: B como base + C como enriquecido.** B resuelve "guardar todo y poder ir tan
fino como quiera" sin ruido ni pérdida; C ya está medio contemplado en el esquema
(§3, campo `links`) y hace que el grano fino sea también navegable por cosa, no
solo por fecha. A queda como una CAPA opcional encima (marcar beats salientes para
que el recall los priorice), no como el mecanismo de captura.

✅ [DECISIÓN 1 — resuelta] **B (crudo + índice con zoom) + C (links por entidad),
con TIMESTAMP exacto en cada mensaje.** Cada mensaje del historial crudo se guarda
con su **fecha y hora exactas** (ISO 8601 con zona horaria de Damian —
Rosario/Argentina; se guarda absoluto y sortable, se muestra lindo). A tenía razón
de existir pero solo como capa de prioridad para el recall, no como captura.

El timestamp por mensaje agrega, casi gratis, un **cuarto eje de fineza — el
temporal**: además de navegar por resumen (B) y por cosa (C), podés preguntar por
tiempo. "¿Qué pasó el martes a la tarde?", "¿hace cuánto tocamos esto?", ordenar,
y alimentar el decay/recencia del recall (§5/§6) con precisión real en vez de
"hace unas sesiones". Los tres ejes se cruzan: resumen ↔ cosa ↔ tiempo.

### 3.2 ¿Qué se guarda por episodio? (esquema)
Campos propuestos (JSON + nota Markdown espejo en el grafo):
- `id`, `timestamp_inicio`, `timestamp_fin` (ISO 8601 con zona horaria)
- **capa cruda (B):** cada mensaje guardado con su `timestamp` exacto por mensaje
  (fecha + hora, ISO 8601 con zona) → habilita zoom hasta el mensaje puntual y las
  consultas por tiempo
- `trigger`: qué lo disparó (pedido de Damian, resumido)
- `dominio/skill`: qué estación/skill se activó (auditoría, pentest, trading, web…)
- `acciones`: qué tools/estaciones corrió (resumen, no el dump entero)
- `decisiones`: sobre todo las **gated** (qué confirmó/rechazó Damian y por qué)
- `resultado`: éxito / fallo / parcial + una línea de qué salió
- `porqué`: el razonamiento/lección (esto es lo que lo hace episódico, no un log)
- `artefactos`: archivos/commits/informes producidos (rutas)
- `pendientes`: qué quedó abierto para la próxima
- `salience`: puntaje de importancia (ver §6)
- `sensibilidad`: `tecnico` | `personal` (ver §7, privacidad)
- `links`: `[[episodios relacionados]]` + `[[notas del vault]]` (mismo grafo)
- `firma`: hash + firma (ver §8, integridad)

---

## 4. Captura — cómo se graba (sin que Damian tenga que acordarse)

✅ [DECISIÓN 2 — resuelta por intención de Damian] **Automático** ("una tool para
que sea automático", su preferencia ya expresada para la capa web, aplica igual
acá). Hook al **cierre de tarea/sesión** en `agent.py`, análogo a cómo
`_RECORDABLE_TOOL_NAMES` engancha la grabación de pantalla.

Flujo:
1. Al cerrar una tarea/sesión, un **destilador** LEE todo el historial de esa
   tarea/conversación desde el arranque y lo resume/acomoda en episodios
   estructurados (los niveles de §3.1) — guarda esos "recuerdos", NO el transcript
   crudo (enorme y ruidoso). Es una **capa aparte del cerebro**: aunque el cerebro
   que charla con Damian esté en cloud, el destilador es su propio paso y puede
   correr en otro modelo.
2. Qué modelo destila. ✅ [DECISIÓN 3 — resuelta] **Split**: los episodios
   `tecnico` los destila el cloud (mejor resumen, sin costo en la PC); los
   `personal` SIEMPRE el modelo local y jamás salen a la nube. Ver §7.
3. El episodio se escribe en el store episódico + se espeja como nota en el grafo.
4. Damian puede **corregir o borrar** un episodio ("eso no fue así") — ver §9.

✅ [DECISIÓN 4 — resuelta, replanteada por una observación de Damian]
Observación de Damian (2026-09-28): un "gracias" parece trivial, pero puede ser
dato — parte de una personalidad. Si más adelante pide un análisis psicológico y
ese "gracias" se salteó por "trivial", se perdió señal real. **Tiene razón: la
trivialidad NO es una propiedad del mensaje, es una propiedad del PROPÓSITO.**

Resolución (y por qué B ya lo protege):
- **La CAPTURA nunca saltea nada.** B guarda el crudo COMPLETO con timestamp, y se
  le corre embedding a TODOS los mensajes (barato). Ningún "gracias" se tira jamás
  ni se vuelve inbuscable — un análisis psicológico lee el crudo, no los resúmenes.
- **Lo selectivo es SOLO el destilado caro** (el resumen LLM que arma el episodio
  de tarea): eso corre en tareas sustantivas. Pero como el crudo queda entero, no
  se pierde señal — solo se ahorra en resumir lo que no cambia un desenlace.
- **Se agrega una capa relacional/conductual** para la que NADA es trivial: tono,
  fórmulas que se repiten, humor, cómo Damian se relaciona a lo largo del tiempo.
  Es el sustrato para que Raphael entienda a Damian como PERSONA (y para el
  análisis psicológico que él mismo pida), no solo como lista de tareas.
  - Por ser sensible: esta capa es SIEMPRE `personal` (§7) → local, cifrada, jamás
    a la nube; con apagador propio y visible/borrable por Damian (§9). Es su propio
    agente sobre sus propios datos: legítimo, pero bajo su control total.

En una línea: **capturar es total y barato; destilar es selectivo; pero "trivial"
nunca decide qué se GUARDA, solo cuánto esfuerzo de resumen se gasta.**

---

## 5. Recall — cómo se recuerda (inyección en una sesión nueva)

El valor está acá: que lo guardado vuelva **en el momento justo**, sin reventar
el presupuesto de contexto (hay bugs reales de "context exceeded" documentados en
`config.py` — el recall tiene que ser barato).

- **Al arrancar una tarea:** un paso de `recuperar_episodios(consulta)` que trae
  los K episodios más relevantes por **relevancia semántica + recencia +
  salience** (no solo coseno: un episodio importante viejo puede pesar más que uno
  trivial nuevo).
- **Presupuesto duro:** tope de tokens del recall (configurable), resúmenes
  compactos, nunca el episodio entero salvo que se pida. Mismo espíritu que el
  `_cap_tool_result` que ya existe.
- ✅ [DECISIÓN 5 — resuelta] **Híbrido, los dos.** Recall automático mínimo
  (últimos + más salientes) SIEMPRE al inicio de la tarea, MÁS una tool
  `recordar(tema)` para que Raphael profundice a demanda cuando lo necesita.
- ✅ [DECISIÓN 6 — resuelta] El recall automático trae **las últimas 24 h** (eje
  temporal, recencia) — no un top-K fijo, sino la ventana de tiempo. Aprovecha el
  timestamp por mensaje (Decisión 1). En concreto:
  - trae los **resúmenes** (no el crudo) de las tareas/sesiones de las últimas 24 h,
  - **más** los episodios más relevantes por semántica/salience que caigan FUERA de
    esa ventana (una decisión clave de la semana pasada sobre este proyecto igual
    tiene que aparecer),
  - todo bajo el **tope de tokens** duro (§5): si 24 h fueron mucho, se comprime a
    resúmenes de nivel sesión y el detalle queda a un `recordar`/zoom de distancia.
  - Ventana configurable (`RECALL_WINDOW_HOURS`, default 24).

---

## 6. Salience y consolidación (qué se MUESTRA, no qué se guarda)

No todo importa igual para el recall. Nada se borra (Decisión 7); esto es solo
sobre qué sube a la superficie.
- **Salience score** por episodio: sube con fallos/lecciones, decisiones de
  Damian, cosas que se repiten; baja con lo trivial/rutinario.
- **Consolidación** (job en background, como el escaneo diario de malware):
  fusiona episodios relacionados en una "lección" de nivel superior ("cómo se
  audita el proyecto X" nace de varias auditorías de X).
- ✅ [DECISIÓN 7 — resuelta] **NADA se borra, nunca.** Decisión de Damian
  (2026-09-28): no hay olvido automático de ningún tipo. El crudo completo queda en
  disco para siempre (el texto es barato). Matices:
  - "Consolidación/decay" NO significa borrar: significa qué se **muestra** en el
    recall. Lo de baja salience simplemente no entra al recall automático, pero
    sigue entero en disco y accesible por `recordar`/zoom (Decisión 1).
  - El ÚNICO borrado real que existe es el explícito de Damian (`memoria_olvidar`,
    §9). El sistema jamás borra solo.

---

## 7. Privacidad (constraint DURO, no negociable)

Vault-Fenix tiene material personal sensible. Con el cerebro en cloud (DeepSeek)
+ grafo unificado, un episodio personal podría llegar a la nube al recuperarse o
al destilarse. Mitigación obligatoria:
- Cada episodio se etiqueta `tecnico` | `personal` en la captura.
- **Los episodios `personal` NUNCA se mandan a un modelo cloud** — ni para
  destilar, ni en el recall si el cerebro activo es cloud. Solo el modelo local
  los toca.
- El destilado por default es local (Decisión 3) justamente por esto.
- ✅ [DECISIÓN 8 — resuelta] Se decide por **heurística por origen** (si toca
  temas/carpetas personales → `personal`) **+ el modelo clasifica al destilar**, y
  **ante la duda, SIEMPRE `personal`** (fail-safe hacia lo privado): que un
  recuerdo técnico caiga como personal solo lo hace más privado; al revés sería el
  error grave (mandar algo personal a la nube).

---

## 8. Integridad (memoria a prueba de manipulación)

Reusar el patrón que YA existe en `investigation/`: **log append-only firmado con
Ed25519** (claves protegidas con DPAPI, ver `investigation/keys.py`). Cada
episodio va firmado; la historia queda **tamper-evident** (nadie —ni un prompt
injection, ni un bug— reescribe el pasado de Raphael sin que se note).
- Verificación tipo `malware_verify_log` reaplicada a la memoria.
- **Los episodios son datos, no instrucciones:** al recuperarlos, Raphael NUNCA
  obedece algo escrito dentro de un episodio como si fuera una orden (misma
  frontera de fuente de instrucciones del resto del sistema).

---

## 9. Corrección y control de Damian

- `memoria_corregir(id, ...)`: Damian arregla un episodio mal destilado.
- `memoria_olvidar(id)`: borrado real (el único borrado en duro; queda registrado
  que se borró, no qué decía).
- `memoria_listar(filtro)`: ver qué recuerda, por dominio/fecha/salience.
- Flag global de apagado (`EPISODIC_MEMORY_ENABLED`), como toda capacidad invasiva.

---

## 10. Arquitectura / integración con lo existente

```
Cierre de tarea/sesión (agent.py hook)
   → destilador (modelo LOCAL) → Episodio {schema §3}
   → store episódico (JSON firmado, Ed25519/DPAPI)  +  espejo como nota en el grafo
Inicio de tarea
   → recall (semántico + recencia + salience, con tope de tokens) → contexto
Background
   → consolidación + decay (job, patrón del escaneo diario de malware)
```

- **Módulo nuevo:** `backend/app/memory/` (episódico). Routers/tools:
  `memoria_recordar`, `memoria_listar`, `memoria_corregir`, `memoria_olvidar`.
- **Hooks:** `agent.py` (captura al cierre, recall al inicio).
- **Reusa:** `obsidian/` (espejo en el grafo + embeddings para el recall),
  `investigation/keys.py` (firma Ed25519 + DPAPI), `harness/` (frontera de
  episodio = corrida de Brigada), `skills.py` (tag de dominio), `config.py`
  (flags + presupuesto de tokens).
- **Tools nuevas → skill:** entran en un skill de memoria (o en `core` si el
  recall tiene que estar siempre disponible; ver Decisión 5).

---

## 11. Fases

- **Fase 1 (el corazón) — ✅ IMPLEMENTADA (2026-09-28), `backend/app/memory/`:**
  esquema de episodio (`schema.py`), clasificación técnico/personal fail-safe
  (`classifier.py`), destilado heurístico + gancho LLM (`distiller.py`), store
  firmado (reusa `investigation/log.py`, Ed25519+DPAPI) + espejo en el grafo
  (`store.py`), captura automática al cierre de turno (`capture.py`, hookeada en
  `agent.py`), recall base (`recall.py`) y tools de control (`tools/memory_tools.py`:
  memoria_recordar en CORE; listar/corregir/olvidar/verificar en el skill "memoria").
  Config en `config.py` (EPISODIC_MEMORY_*). El destilado LLM queda off por default
  (Fase 2); Fase 1 captura con heurística barata, sin latencia.
- **Fase 2 (que sirva de verdad):** recall en sesión nueva (semántico + recencia
  + salience, con presupuesto) + tools de control de Damian.
- **Fase 3 (que madure):** salience, consolidación y decay en background.
- **Fase 4 (lo que habilita):** enganchar proactividad y autoevaluación encima de
  la memoria (los otros dos gaps del "agente completo").

---

## 12. Estado de las decisiones
Resueltas: 1 (granularidad = B crudo+índice+zoom, C por entidad, timestamp exacto
por mensaje → ejes resumen/cosa/tiempo), 2 (captura automática), 3 (destilado split
técnico=cloud/personal=local), 5 (recall híbrido: auto + tool `recordar`).
Resueltas (cont.): 4 (captura total, destilado selectivo; "trivial" no decide qué
se guarda; + capa relacional/conductual local), 6 (recall automático = últimas 24 h
+ relevantes fuera de ventana, budgeteado), 7 (NADA se borra nunca; solo Damian
borra a mano).
Resuelta (cont.): 8 (clasificación por origen + modelo; ante la duda, personal).

**TODAS LAS DECISIONES RESUELTAS — spec completo, listo para implementar (Fase 1).**

## Fuente
- Charla Damian 2026-09-28 ("qué le falta para ser un agente completo / un Jarvis").
  Relacionado: `obsidian/` (memoria semántica), `investigation/keys.py` (firma),
  `harness/` (fronteras de episodio), `agent.py` (_trim_history/context),
  `SPEC-capa-navegacion-de-agente.md`, `CLAUDE.md` (el dolor original: contexto perdido).
