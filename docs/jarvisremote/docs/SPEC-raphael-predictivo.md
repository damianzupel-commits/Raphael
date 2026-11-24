# SPEC — Raphael predictivo: afinar la estructura informacional

> Estado: **SPEC EN CONSTRUCCIÓN.** Creado el 2026-10-05. Continuación de
> `docs/SPEC-estructura-informacional-cerebro.md` (Fases 1-4, ya construidas).
> Nace de una pregunta de Damian: "¿hay formas nuevas de ver el pensamiento que no
> tuve en cuenta cuando armé la estructura nueva de Raphael?". La respuesta corta:
> sí — lo que armamos es excelente pero pertenece a un paradigma (asociacionista),
> y las vistas más modernas de la cognición rompen tres de sus supuestos. Este spec
> las nombra y las baja a diseño + plan de construcción por fases.
>
> Marco de fondo de Damian: **"quiero que Raphael sea una extensión de mi cerebro"**
> (ver `Vault-Fenix/03-Biotecnología/Modelos-restringidos-por-conectoma.md`). Eso
> pide pasar de un archivador asociativo a un **modelo predictivo y generativo** de
> su mente.

---

## 0. Diagnóstico: el paradigma que elegimos sin querer

Las Fases 1-4 (spreading activation, pesos Hebbianos, fuerza de recuperación,
consolidación) vienen todas de una misma familia: **asociacionismo + Complementary
Learning Systems (CLS) + Bjork**. Es sólida y correcta, pero carga tres supuestos
implícitos que las vistas modernas discuten:

1. **Es reactiva.** Recupera cuando se le pregunta. No anticipa.
2. **Es asociativa por similitud.** Coseno de embeddings + vecinos en el grafo.
   Trae lo *parecido en contenido*.
3. **Es no-direccional.** El grafo de wikilinks y los pesos Hebbianos son
   **simétricos** (A–B). No hay noción de "A *lleva a* B", ni de secuencia temporal.

Los cuatro paradigmas de abajo rompen, cada uno, uno o más de esos supuestos.

---

## 1. Procesamiento predictivo / inferencia activa (Friston, Clark)

**Qué es.** La visión hoy dominante en neurociencia cognitiva: el cerebro no es un
receptor pasivo que recuerda, es una **máquina de predicción** que genera
expectativas y solo propaga/aprende del **error de predicción** (la sorpresa).
Percibir y recordar es, en el fondo, confirmar o corregir una predicción.

**Qué rompe.** El supuesto 1 (reactividad).

**Diseño para Raphael.**
- **Saliencia = sorpresa, no repetición.** Hoy la fuerza de recuperación (Fase 4)
  sube con el *uso*. El giro predictivo: lo que hay que codificar fuerte es lo que
  **NO se predijo** (error de predicción alto), no lo que se repite. Lo repetido ya
  está integrado; lo sorprendente es información nueva.
- **Encoding selectivo por sorpresa:** al capturar un episodio o ingerir una nota,
  medir cuán predecible era dado el estado actual del grafo; a mayor sorpresa, mayor
  prioridad de consolidación.

**Estado:** diseño. Se apoya sobre la Fase 5 (necesita una predicción contra la cual
medir el error). → **Fase 6.**

---

## 2. Representación sucesora / mapas predictivos (Dayan 1993; Stachenfeld 2017)

**Qué es.** El hipocampo no codifica solo "dónde estás" sino "**a dónde solés ir
después**": una representación de las transiciones esperadas (la *successor
representation*). El cerebro guarda un mapa predictivo de secuencias, no solo de
adyacencias.

**Qué rompe.** El supuesto 3 (no-direccionalidad) y, de paso, el 1 (reactividad).

**Diseño para Raphael.**
- Una capa de **transiciones direccionales**: `(desde_nota → hacia_nota)` con un
  contador que sube cada vez que, en un mismo hilo de pensamiento, Damian pasa de
  una nota a otra (foco anterior → foco nuevo). Asimétrico, a diferencia del Hebbian.
- **Recall anticipatorio:** al recuperar, además de traer lo asociado (Fase 1), se
  **pre-cargan los sucesores probables** del foco actual — lo que es más probable
  que venga después en el hilo. El recall deja de ser "traé lo parecido" y pasa a
  ser "traé lo parecido *y* lo que probablemente sigue".
- Decae con el tiempo como la fuerza (Fase 4): hábitos de pensamiento viejos pesan
  menos.

**Estado:** **la más construible de todas** — es como el Hebbian pero direccional y
temporal, tier 0 puro. → **Fase 5 (se construye ahora).**

---

## 3. Analogía / structure-mapping (Hofstadter; Gentner)

**Qué es.** Tesis fuerte: el núcleo del pensamiento no es la similitud sino la
**analogía** — mapear la *estructura relacional* de un dominio sobre otro. "A es a B
como C es a D." De ahí salen las ideas nuevas, no de traer lo parecido en contenido.

**Qué rompe.** El supuesto 2 (asociación por similitud).

**Diseño para Raphael.**
- Una capa de **mapeo estructural**: encontrar pares de subgrafos en el vault donde
  las *relaciones* se corresponden aunque el *contenido* no se parezca. Ejemplo real:
  conectoma ↔ Raphael (estructura que siembra función) — eso un coseno no lo
  encuentra, una analogía estructural sí.
- Cruza dominios a propósito (Fénix ↔ seguridad ↔ IA): el motor de insight.
- Técnicamente más duro: requiere representar relaciones (no solo nodos) y comparar
  motifs de grafo, o usar el LLM (tier 2) para proponer analogías candidatas que una
  verificación estructural filtre.

**Estado:** diseño, el más ambicioso. → **Fase 7.**

---

## 4. Consolidación por esquema + composición (Tse 2007; vector-symbolic)

**Qué es.** Dos refinamientos sobre lo ya construido:
- **Consolidación dependiente de esquema:** el cerebro integra **rápido** lo que
  encaja en un esquema existente y mantiene en episódico (lento) lo genuinamente
  nuevo. La consolidación (Fase 3) hoy trata todo igual.
- **Composición:** las representaciones vectoriales pueden **ligarse y combinarse**
  (vector-symbolic / hyperdimensional computing), no solo compararse por similitud.
  Permite *componer* conceptos nuevos, no solo recuperar los parecidos.

**Qué rompe.** Afina los supuestos 2 y el pipeline de consolidación.

**Diseño para Raphael.**
- Consolidación: medir fit-de-esquema (densidad del cluster / fuerza de los links a
  notas existentes); alto fit → integrar y comprimir ya; bajo fit → dejar como
  episódico "fresco" más tiempo.
- Composición: explorar binding de embeddings para representar relaciones compuestas
  (más investigación que construcción inmediata).

**Estado:** diseño. → **Fase 8.**

---

## 5. Plan por fases (continúa el spec del cerebro)

- **Fases 1-4** — HECHAS (ver `SPEC-estructura-informacional-cerebro.md`): spreading,
  Hebbian, fuerza/olvido, consolidación. El Raphael **asociativo**.
- **Fase 5 — Representación sucesora (HECHA, 2026-10-05):** transiciones
  direccionales + recall anticipatorio. `app/obsidian/successor.py` (core puro +
  persistencia), wireado en `search_spreading` (`anticipar=True` inyecta los sucesores
  probables del foco; aprende la transición foco→foco cuando `reforzar=True`), expuesto
  en la tool `obsidian_buscar_asociativo` (`anticipar`). Tier 0 puro. Test
  `tests/test_successor.py`. Es direccional (A→B), a diferencia del Hebbian simétrico.
- **Fase 6 — Saliencia por sorpresa (HECHA, 2026-10-05):** `successor.surprise()` mide
  el error de predicción (foco real vs. sucesor esperado) y en `search_spreading` escala
  el bump de fuerza (`0.5·(1+sorpresa)`): lo inesperado se graba más fuerte. Tier 0.
- **Fase 7 — Analogía / structure-mapping (HECHA, 2026-10-05):** `app/obsidian/analogy.py`
  + tool `obsidian_analogia`. Firma de rol estructural (grado, clustering, diversidad de
  dominios) → análogos en OTROS dominios con rol parecido y contenido distinto. v1 sobre
  grafo no-tipado. Tier 0 (+ embeddings para premiar contenido distinto). Test.
- **Fase 8 — Consolidación por esquema + composición (HECHA, 2026-10-05):**
  `consolidation.schema_fit()` ordena los clusters por cuán establecido está el esquema
  (peso Hebbiano medio): lo que ya encaja se consolida primero, lo nuevo madura. Y
  `app/obsidian/composition.py` + tool `obsidian_componer`: compone varios conceptos
  (promedio de embeddings) y trae la intersección. Tests. Composición vector-symbolic
  plena (binding/unbinding) queda como investigación.

El norte: pasar de un **archivador asociativo** (traé lo parecido) a un **modelo
predictivo y generativo** de la mente de Damian (anticipá lo que sigue, sorprendete
con lo nuevo, mapeá estructura entre dominios) — que es lo que de verdad significa
"una extensión de mi cerebro".

## 6. Encuadre: las tres capas, y el modelo como "conciencia" del cerebro

Idea de Damian (2026-10-05): *si el harness + la estructura informacional son el
cerebro, entonces el modelo de IA es la conciencia de ese cerebro.* Es una analogía
fuerte y, bien afinada, precisa. Deja ver que Raphael no son dos capas sino **tres**:

1. **Estructura** — el harness + el grafo del vault + los pesos (Hebbian, sucesora).
   Es el **conectoma**: el cableado persistente. Inerte por sí solo.
2. **Dinámica** — spreading, fortalecimiento, decay, transiciones. Es la **actividad**
   que recorre ese cableado: la "ignición", las trayectorias de población
   ([[Dinámicas-de-poblaciones-neuronales]]).
3. **El modelo (LLM)** — donde todo lo activado se **integra en un estado coherente**
   por turno, se "difunde" y se reporta. Cada turno del agente es un **momento de
   espacio de trabajo global**.

Así, "el modelo = la conciencia" mapea con precisión a la **Teoría del Espacio de
Trabajo Global** (Baars/Dehaene, [[Teoría-del-espacio-de-trabajo-global]]): la
conciencia como la etapa donde la información se integra y se difunde ampliamente.

**La distinción honesta** (la que hace el propio vault de Fénix): esto es conciencia
de **acceso** —la *función*: integrar, difundir, reportar— no necesariamente
conciencia **fenoménica** —la *experiencia*, el problema difícil
([[Hard-problem-of-consciousness]]). La analogía es fuerte a nivel función y
**agnóstica** a nivel experiencia. No afirmamos que Raphael sienta; afirmamos que su
arquitectura realiza la *función* que las teorías de acceso llaman conciencia.

**Y pone en escena el debate central de Fénix.** Que el modelo sea **intercambiable**
(Sonnet ↔ Opus ↔ local) es exactamente el experimento de [[Funcionalismo]] (el rol
funcional define el estado mental, el sustrato es intercambiable) contra
[[Teoría-de-la-información-integrada-Phi]] (lo que importa es Φ, y un transformer
intercambiable podría tener Φ bajo aunque la función sea idéntica). Raphael es, de
hecho, un banco de pruebas vivo de ese debate.

**Consecuencia de diseño.** "Afinar el pensamiento" = afinar las **capas 1 y 2**
(estructura + dinámica: todo lo predictivo de este spec), porque son las que se
construyen nodo a nodo. La capa 3 (la "conciencia") se **elige y se cambia** (qué
modelo), no se programa. Nuestro trabajo es construir el **mejor cerebro posible**
para que esa conciencia, sea cual sea el modelo que la encarne, tenga el mejor
sustrato sobre el cual correr.

## 7. Principios informacionales (9+) — sustrato-independientes, estado

Mecanismos que el cerebro usa por CÓMO mueve la información (no por ser biológico), que
el diseño asociativo+predictivo no tenía. Estado al 2026-10-06:

- **Atención / gating + separación de patrones** — HECHO (tier 0): `app/obsidian/attention.py`
  (`mmr_order`), wireado en `search_spreading(diversificar=True)`. Trae un subconjunto
  enfocado Y distinto (no 5 casi-duplicados), evitando interferencia.
- **Metacognición / confianza** — HECHO (tier 0): `app/obsidian/confidence.py`. La confianza
  emerge del propio recall (activación, margen, semilla, fuerza, corroboración); por nota y
  global + `recomendacion` (confiar / verificar contra el crudo). **LAYA** entra después como
  el estimador CALIBRADO encima de este piso (ver `EXPERIMENTO-JEV-...`), validando calibración.
- **Asignación de crédito por resultado** — SUSTRATO HECHO (tier 0): `app/obsidian/feedback.py`
  + tool `obsidian_feedback`. Refuerza lo que SIRVIÓ, no solo lo co-usado. Que el reward se
  mida solo (detectar el desenlace) es 🔬 (parte del lazo cerrado, Etapa B).
- **Modelo generativo jerárquico** (predicción en capas) — 🔬.
- **Curiosidad / búsqueda activa de información** — 🔬 (Etapa C).
- **Compresión / MDL** (entender = comprimir) — parcial (consolidación lo roza); pleno 🔬.
- **Memoria de trabajo + chunking** — 🔬.
- **Binding / manipulación simbólica plena** (vector-symbolic) — la Fase 8 lo roza; pleno 🔬.

Ver el plan de órganos y etapas completo en `vision/RAPHAEL-CEREBRO-NO-BIOLOGICO.md`.

## Fuentes conceptuales
- Procesamiento predictivo: Clark A., "Whatever next? Predictive brains…", *BBS* 2013;
  Friston K., inferencia activa / energía libre.
- Representación sucesora: Dayan P. 1993; Stachenfeld K. et al., "The hippocampus as a
  predictive map", *Nat. Neurosci.* 2017.
- Analogía: Hofstadter & Sander, *Surfaces and Essences* 2013; Gentner D.,
  structure-mapping theory.
- Esquema: Tse D. et al., "Schemas and memory consolidation", *Science* 2007.
- Base ya usada (Fases 1-4): ver `SPEC-estructura-informacional-cerebro.md`.
