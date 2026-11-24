# BLUEPRINT — Habilidades y Defensas de las Brigadas

> **Documento vivo.** Lo llenamos brigada por brigada y lo actualizamos a medida
> que construimos. Creado 2026-11-03 con Claude. Traduce a diseño concreto lo que
> Damian quiere lograr con cada brigada. El modelo conceptual (metáfora de cocina)
> está en `LA-BRIGADA.md`; el plano técnico histórico en
> `vision/ORQUESTACION-BLUEPRINT.md`. Este doc es el que mandamos de acá en más.

---

## 0. El norte

De `LA-BRIGADA.md`, palabras de Damian: **la brigada existe para comprarle tiempo
y libertad** — que la cocina funcione sin que él esté parado sobre cada hornalla.
Cada brigada que trabaja sola y bien es un rato de su vida que recupera. Si un
plato nuevo no acerca a eso, capaz no hay que cocinarlo.

## 0.1 Principio rector (definido 2026-11-03)

> **Máxima autonomía por brigada, con el riesgo de daño al sistema eliminado.**

Cada brigada hace sus tareas con la **mayor libertad posible**. La capa de
"defensas" no está para recortar esa libertad, sino para que **ningún fallo,
ataque o acción de una brigada pueda afectar negativamente al resto del sistema**.
Libertad total adentro de su caja; la caja contiene el daño (blast radius acotado).

Esto define los dos ejes de cada brigada:
- **Habilidades** = qué tareas PUEDE hacer (sus skills/tools, sus modos). Acá
  empujamos hacia la autonomía: que haga lo suyo sin pedir permiso para cada paso.
- **Defensas** = la contención que hace segura esa autonomía. No es una sola cosa:
  es un **toolkit de mecanismos** (§1.2) que cada brigada compone según su peligro.

---

## 1. El modelo de "Defensas"

### 1.1 Las tres categorías de riesgo a eliminar

1. **Fallo** — la brigada se cuelga, crashea, o ejecuta una acción incorrecta.
2. **Ataque** — contenido externo (una página web, un archivo, un mensaje) que
   intenta **secuestrar** a la brigada (prompt injection), o un target/acción
   fuera de lo autorizado.
3. **Daño al sistema** — una acción **irreversible** (borrar, formatear, mover
   plata, publicar) o que **degrada el todo** (reventar el contexto, agotar
   recursos, filtrar datos sensibles, tirar abajo el backend).

### 1.2 El toolkit de defensas (mecanismos reusables)

Cada brigada compone de acá lo que su peligro pida. Muchos ya existen en el código
(marcados ✅); el trabajo es **sistematizarlos** y aplicarlos parejo.

| Mecanismo | Qué contiene | Estado |
|---|---|---|
| **Menor privilegio** | cada jefe/brigada ve SOLO sus tools, no las de al lado | ✅ (perfiles, Scout) |
| **Sandbox de FS** | `FS_ALLOWED_ROOT` / raíz por brigada | ✅ (parcial: hoy es HOME entero) |
| **Dry-run → confirm** | lo irreversible pide confirmación explícita con id | ✅ (fixes, cuarentena, forms) |
| **Reversibilidad** | mover no borrar; cada fix en su commit git | ✅ |
| **Gate de scope** | `authorized_targets.yaml` para pentest (solo Damian lo edita) | ✅ |
| **Kill-switch** | flag por capacidad; lo caro/peligroso default OFF | ✅ |
| **Frontera instrucción-vs-dato** | contenido externo = DATO, nunca una orden | ✅ (Scout lo tiene) |
| **Aislamiento de fallo** | watchdog/timeout; una brigada colgada no frena al resto; supervisor fail-open | ✅ (ops_watchdog, parcial) |
| **Privacidad por tier** | los commis (modelos free) nunca tocan datos sensibles | ✅ (regla, falta forzarla) |
| **Auditoría** | log append-only de toda acción de la brigada | ✅ (audit.log) |
| **Presupuesto de recursos** | timeouts + budget de contexto por turno | ✅ |

**Dónde viven las defensas:** sobre todo en el **jefe de brigada** (§2) — es el
chokepoint. Un jefe con solo sus tools, su scope y sus gates ya contiene la mayor
parte del blast radius por diseño, antes de que una skill llegue a ejecutarse.

---

## 2. Arquitectura de mando: Orquestador → Jefe de Brigada → Skills

> **Decisión (2026-11-03): se construye AHORA. Es la columna vertebral del resto.**

Cuatro capas (traducción de la cocina de `LA-BRIGADA.md`):

- **Orquestador (sous-chef)** — el loop de `agent.py`. Recibe la tarea, decide a
  qué brigada va, y **delega al JEFE** de esa brigada. No habla con cada skill una
  por una. Hub-and-spoke: toda la coordinación pasa por él (los jefes no se hablan
  entre sí). **Persistente.**
- **Jefe de brigada — el "representante de plaza" (PERSISTENTE)** — un supervisor
  por brigada (generaliza el `ops_supervisor`). Siempre está, **recuerda qué viene
  haciendo** (estado en disco). Recibe la sub-tarea, corre con SOLO las tools de su
  brigada (menor privilegio), aplica los gates de su brigada, y devuelve el
  resultado al orquestador. Acá viven las defensas de esa rama.
- **Ayudantes — los trabajadores POR-TAREA (efímeros)** — el jefe spawnea un ayudante
  para una sub-tarea puntual, con una caja de tools aún más chica y un foco único; el
  ayudante resuelve y **muere**. Dan paralelismo + aislamiento de fallo (un ayudante
  que se cuelga no toca al jefe ni al resto = defensa). *(Capa futura; hoy el jefe
  hace el trabajo directo.)*
- **Skills (jefes de partida)** — las tools concretas. Cada una, su caja acotada.

**Por qué:** reduce lo que el orquestador maneja en paralelo, da una jerarquía
clara, y hace del jefe el lugar natural donde se aplican menor-privilegio + gates
(defensa por construcción).

### 2.1 Molde propuesto (Scout YA es el primer jefe de facto)

Lo que armamos para **Scout** es el molde del "jefe de brigada":
- system prompt propio (el rol de la brigada),
- set de tools **reducido y filtrado** (menor privilegio),
- **modelo BYOM propio** (Scout corre en Groq free, independiente del resto),
- sus gates (frontera instrucción-vs-dato, vault propio),
- un engine-loop liviano que reusa el núcleo sin duplicarlo,
- y **su propia vista en la Suite**.

**Generalizar = cada brigada un "jefe" con ese molde + su vista en la Suite.** El
orquestador delega al jefe; la UI de la Suite es la cara de cada jefe.

### 2.2 Decisiones del jefe (definidas 2026-11-03)

- **Persistencia: TODOS los jefes son PERSISTENTES** (el "representante de plaza").
  Viven con estado/memoria de su brigada (recuerdan qué vienen haciendo), persistido
  en disco. Lo efímero/por-tarea son los **ayudantes** (§2), no el jefe.
- **Modelo: tier 3** (Sonnet 5.5) **como objetivo**. Decisión 2026-11-03: por ahora
  los jefes corren con **lo que tengamos disponible (Groq free, `gpt-oss-120b`)**, y se
  cambian a Sonnet cuando Damian tenga la API. Un **solo punto de cambio**:
  `brigades/config.py::load_chief_client_model()` → cambiar a
  `model_registry.client_and_model_for_tier(3)`. (El tier 3 hoy no está cableado: resuelve
  a `anthropic/claude-sonnet-5.5` sobre el endpoint global —Groq— que no tiene ese modelo.)
- **Ruteo: AMBOS.** (a) Por la UI — cada brigada su vista en la Suite, le hablás al
  jefe directo (como Scout). (b) Por el orquestador — le hablás al maestro y él delega
  al jefe correcto (`skills.classify`).

**El molde del jefe (`BrigadeChief`)**, generalizando Scout: `id`, `nombre`,
`system_prompt`, `tool_names` (allowlist = menor privilegio), `tier`/BYOM, vault
propio, gates, estado persistente, engine-loop que reusa el núcleo, y su vista en la
Suite.

**CONSTRUIDO (2026-11-03):**
- `backend/brigades/chief.py` — `BrigadeChief` + `ChiefConfig` (persistente,
  menor-privilegio, reusa el núcleo, `persistent` por brigada).
- `backend/brigades/config.py` — modelo de los jefes (Groq hoy; **un solo punto de
  cambio a Sonnet/tier 3**).
- `backend/brigades/registry.py` — Scout registrado como primer jefe.
- `backend/app/routers/brigades.py` — endpoint genérico `/api/brigade/{id}/{meta,chat}`
  (stream del feed), enganchado en `main.py`. = la mitad "UI" del ruteo.

**Pendiente de la capa:** (a) ruteo por orquestador (`skills.classify` → jefe); (b)
que la Suite abra la vista de cualquier jefe registrado; (c) el jefe de **Cerebro**.

---

## 3. Las 10 brigadas (template a llenar)

> Por cada una: **modo(s)**, **habilidades** (actuales + deseadas), **jefe**,
> **defensas** (del toolkit §1.2), **tier de modelo**. Pre-cargado con lo que YA
> existe; lo que falta definir queda como `TODO`.

### 1. Seguridad — `seg` — modos: ⚔️ Ataque / 🛡️ Defensa
- **Habilidades (hoy):** scan de código (security/quality/codebase), auditoría;
  pentest activo (nmap, sqlmap, zap).
- **Defensas:** gate de scope `authorized_targets.yaml`; grabación del pipeline.
- **TODO:** definir habilidades/defensas deseadas, jefe, tier.

### 2. Antimalware — `mal` — Protección activa
- **Habilidades (hoy):** YARA + ClamAV + heurística conductual + FIM + cuarentena.
- **Defensas:** cuarentena reversible (mover, no borrar); borrado definitivo con confirm.
- **TODO:** idem.

### 3. Investigación — `inv` — **una brigada, dos modos** (decidido): 🔭 Scout (research/intel) + 🔬 Forense
- **Habilidades (hoy):** Forense (analyze_link, artifacts); Scout (research_topic, captura).
- **Defensas:** frontera instrucción-vs-dato; vault propio; (Scout) BYOM.
- **TODO:** unificar los dos modos bajo un jefe; arreglar el fetch web de Scout.

### 4. Geolocalización pública / OSINT — `geo` — Mapa · OSINT
- **Habilidades (hoy):** ip_geolocate, crypto_address_trace, shodan; globo 3D.
- **TODO:** definir.

### 5. Memoria · Cerebro — `mem` — **(siguiente a construir)**

**Visión de Damian (2026-11-03):** Cerebro no es "memoria", es el **núcleo cognitivo**
del sistema: sus formas de trabajar + su **autoconciencia** + las notas personales de
Raphael + las notas del usuario + toda la info relevante cargada. Es **las dos cosas**:
el cerebro de Raphael Y el producto "Memoria". Es el **servicio de memoria de TODO el
sistema** (todas las brigadas lo alimentan) y se nutre de **absolutamente todo** (vault,
web/video ingerido, chats con Raphael, capturas de las brigadas). Guarda **notas
propias** cuando reconoce patrones o saca conclusiones. Actúa **solo**, gobernado por
**directrices que Damian le da + la personalidad que construye/adquiere**.

- **Habilidades (hoy):** cerebro-símil fases 1-8 (spreading, hebbian, consolidación,
  predicción, analogía, esquema); embeddings; búsqueda asociativa; curiosidad; feedback.
- **Autonomía:** tareas **permanentes/recurrentes = proactivas** (consolidar, conectar,
  llenar huecos, reconocer patrones→notas); tareas **efímeras = a pedido** del orquestador/usuario.
- **Defensas:** solo lee/organiza (consolidación aditiva y reversible, no borra); corre
  **local** (privacidad: notas personales no salen a la nube); la autonomía la acota el
  store de **directrices** editable por Damian.

**Cómo se construye (plan 2026-11-03):**
1. Cerebro como jefe LOCAL + su vista "¿qué sé de X?" + grafo 3D (lo tangible primero).
   ✅ **CONSTRUIDO:** `brigades/cerebro.py` (jefe local, tools de búsqueda asociativa +
   keyword), `load_local_client_model` (tier 1 Ollama = privacidad), y la vista de Cerebro
   en la Suite (pregunta → respuesta con fuentes + grafo 3D embebido). Requiere: reiniciar
   backend + Ollama local arriba (en CPU, `BRIGADE_LOCAL_MODEL=jarvis-text-lite`).
2. Servicio de memoria del sistema (las brigadas alimentan a Cerebro; él integra).
   ✅ **CONSTRUIDO:** `brigades/memory_service.py::remember()` — puente **write-only**:
   las brigadas escriben su captura en la memoria unificada (la que lee Cerebro), pero
   NO leen el vault personal (defensa de privacidad: Scout corre en la nube). Scout ya
   enganchado (cada captura de `research_topic` alimenta a Cerebro, tageada `brigada-scout`).
   Pendiente fino: reindexar embeddings de lo nuevo (lo hará la tarea proactiva del paso 3).
3. Tareas recurrentes proactivas + notas propias (reusando consolidación/curiosidad/proactive bajo el jefe + scheduler).
   ✅ **CONSTRUIDO:** `brigades/cerebro_proactive.py` (`cerebro_pass`/`cerebro_loop`):
   reindexa la memoria + corre la consolidación "sueño" (que escribe las **notas de
   conclusión** de Cerebro), reusando `vault.reindex_all` + `consolidation.run_once`.
   Aditivo/reversible. `brigades/cerebro_activity.py` = registro "lo que hizo solo" +
   endpoint `/api/brigade/cerebro/activity` + panel en la vista de Cerebro de la Suite.
   Default OFF (`CEREBRO_PROACTIVE_ENABLED`): corre local (pesado en CPU) y escribe solo.
4. Directrices + personalidad (la capa de gobierno de la autonomía; hook a self_model + persona + el loop de feedback/fuerza que ya existe).
   ✅ **CONSTRUIDO:** `brigades/directrices.py` (carta editable, `data/cerebro_directrices.md`)
   + endpoints `GET/POST /api/brigade/cerebro/directrices` + editor en la Suite. El prompt
   de Cerebro pasó a ser un **builder vivo** (`build_cerebro_system_prompt`): persona
   (identidad unificada) + rol + **autoconciencia** (líneas rojas + límites honestos del
   `self_model`) + las directrices editables — se rearma cada turno, así editás las
   directrices y aplican sin reiniciar. **Cerebro: los 4 pasos completos.**

**Honesto:** memoria, proactivo, directrices, notas propias y vista = construibles ya.
"Autoconciencia / personalidad que adquiere" se construye en su **versión funcional**
(self-model que lee/actualiza + loop de aprendizaje que cambia qué prioriza), no como
conciencia real — eso es la parte abierta (🔬, etapas B/C/D del cerebro no biológico).

### 6. Ingesta — `ing` — Conocimiento
- **Habilidades (hoy):** youtube (video/playlist) + web → notas embebidas; watcher automático.
- **TODO:** definir.

### 7. Trading — `trd` — Mercados
- **Habilidades (hoy):** watchlist, señales IFVG, backtest, panel de riesgo. **Solo análisis, nunca opera.**
- **Defensas:** NO ejecuta órdenes ni mueve dinero (línea roja dura).
- **TODO:** definir.

### 8. Operaciones — `ops` — PC · Celular (las "manos")
- **Habilidades (hoy):** shell (pc/phone), desktop, celular, browser.
- **Defensas:** blocklist de comandos destructivos; flags por capacidad; ops_watchdog; ops_supervisor.
- **TODO:** idem.

### 9. Autorreparación — `rep` — Auto-mejora
- **Habilidades (hoy):** propone/aplica fixes a su propio código.
- **Defensas:** dry-run sin gate; aplicar requiere `proposal_id` confirmado por Damian; guardrail de self-target.
- **TODO:** idem.

### 10. Contenido — `con` — Imagen · Video — **APAGADA**
- **Estado:** desactivada por riesgo de apagón físico de la PC (GPU). No reactivar sin resolver el hardware.
- **TODO:** nada hasta resolver el hardware.

---

## 4. Orden de construcción (decidido 2026-11-03)

1. **Orquestador → Jefe de Brigada** (la columna). ← AHORA
2. **Memoria · Cerebro** (el jefe de Cerebro).
3. (resto, a definir con Damian)

---

## 5. Decisiones registradas

- 2026-11-03: Principio rector = máxima autonomía + riesgo de daño eliminado.
- 2026-11-03: Se construye la capa jefe-de-brigada ahora.
- 2026-11-03: Investigación = una brigada con dos modos (Scout + Forense).
- 2026-11-03: Orden: orquestador, luego Cerebro.
- 2026-11-03: Este es un blueprint vivo.

## 6. Preguntas abiertas
- (ver §2.2: persistencia del jefe, modelo por jefe, ruteo)
