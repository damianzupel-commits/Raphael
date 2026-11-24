# SPEC — Estructura informacional de Raphael, cerebro-símil

> Estado: **SPEC EN CONSTRUCCIÓN.** Creado el 2026-10-04. Pedido de Damian: que la
> estructura de información de Raphael funcione lo más parecido posible a un cerebro.
> Construye sobre lo que YA existe (vault semántico, memoria episódica, grafo
> unificado Vault-Fenix) y le suma la **dinámica** cerebral que falta.
> Anclado en material que Damian aportó (ver §Fuentes).

---

## 1. Tesis
Raphael ya tiene, en piezas, los **cuatro sistemas de memoria** del cerebro. Lo que
falta no son más piezas: es la **dinámica** que los hace funcionar como UN sistema.
Un cerebro no es un archivador con buscador — es una **red que asocia, reconstruye,
consolida y se recablea con el uso.** Este spec agrega esa dinámica.

## 2. Los cuatro sistemas (ya presentes) — mapeo
| Sistema (cerebro) | Qué es | En Raphael |
|---|---|---|
| **Semántica** | hechos, conocimiento del mundo | el **vault** (Obsidian) |
| **Episódica** | qué viviste, autobiográfica | `app/memory/` (esta sesión) |
| **De trabajo** | lo que tenés en la cabeza AHORA | el **contexto** de la conversación |
| **Procedural** | cómo hacer cosas, habilidades | **tools + skills + brigadas** |

La mejora es la interacción entre los cuatro, no cada uno por separado.

## 3. Las dinámicas que faltan (el corazón del spec)

### 3.1 Recuperación por asociación (spreading activation)
Hoy el recall es top-k por coseno (traé los 5 más parecidos). El cerebro **activa un
concepto y la activación se esparce por los links** a lo relacionado. **Mejora:** una
nota que matchea no se trae sola — se siguen sus `[[links]]` y se traen los vecinos
más activados (con decaimiento por distancia). Pensar en red, no en lista.

### 3.2 La memoria se MONTA, no se abre (reconstrucción) — *del video de memoria*
Hallazgo central de la ciencia de la memoria: **no recuperás un recuerdo guardado, lo
RECONSTRUÍS** de fragmentos + el contexto actual, cada vez. **Implicación de diseño:**
Raphael NO debería devolver la nota guardada tal cual; debería **reconstruir** una
respuesta a partir de fragmentos (notas, episodios, contexto). Y acá está lo lindo:
el LLM ya hace exactamente esto (genera desde el contexto recuperado) — así que en
este punto Raphael ya es MÁS cerebro que una base de datos. El diseño se inclina a
**guardar fragmentos y dejar que el recall + el LLM los reensamblen**, en vez de
guardar respuestas rígidas y finales.

### 3.3 El riesgo del diseño reconstructivo: confabulación — *del video de memoria*
La misma ciencia advierte: una memoria reconstructiva **puede fabricar recuerdos
falsos** (el experimento del "centro comercial"/Loftus, el efecto de desinformación,
una palabra que cambia lo que viste). O sea: reconstruir sin ancla = alucinar. **Por
eso el diseño exige PROVENANCE:** se guarda siempre el **fragmento crudo + su fuente**
(ya lo tenemos: el log append-only firmado Ed25519 de la memoria episódica es la
"verdad base"). La reconstrucción es la capa flexible; el crudo firmado es el ancla
contra la que se puede verificar. Reconstruir para pensar, pero poder volver al crudo
para no confabular.

### 3.4 Consolidación ("dormir")
El cerebro, durmiendo, **repite** lo del día y lo mueve de la memoria rápida
(episódica) a la integrada (semántica), abstrayendo patrones y podando ruido.
**Mejora:** un job en background que agarra episodios recientes + notas crudas y
**consolida** — fusiona duplicados, extrae la lección, refuerza links importantes,
y archiva/comprime lo de baja salience. (Ya estaba a medias en el spec de memoria
episódica; esto lo completa y lo nombra como lo que es: sueño/replay.)

### 3.5 Reconsolidación (los recuerdos se ACTUALIZAN al usarse) — *del video de memoria*
Recuperar un recuerdo lo vuelve **maleable**: se re-guarda, posiblemente modificado.
**Mejora:** cuando una nota/episodio se recupera y se usa en una tarea, se **actualiza**
con lo aprendido en esa tarea (la memoria evoluciona con el uso, no queda congelada).
Va de la mano con el fortalecimiento Hebbian.

### 3.6 Fortalecimiento por uso (Hebbian: "lo que se activa junto, se cablea junto")
Cuando dos notas se recuperan/usan juntas, su link se **fortalece** (un peso en la
arista). Con el tiempo el grafo se auto-organiza según cómo Damian REALMENTE piensa,
no cómo cargó la info. La estructura **emerge del uso.** Es lo más cerebro de todo.

### 3.7 Olvido adaptativo (no es una avería) — *del video de memoria*
Olvidar es una **feature**, no un bug: el cerebro deja que lo irrelevante se desvanezca
para mantener accesible lo importante. **Mejora:** decaimiento de la fuerza de
recuperación por falta de uso (nada se borra en duro — el crudo queda, §3.3 — pero
baja en el ranking del recall). Ya alineado con la Decisión 7 de la memoria episódica.

## 3-bis. Arquitectura cognitiva: qué procesador ejecuta cada dinámica
Decisión de Damian (2026-10-04): este trabajo NO lo hace un solo modelo. El cerebro
tampoco — es una **federación de regiones especializadas** + un **diálogo offline**.
Marco: **Complementary Learning Systems (McClelland, McNaughton & O'Reilly, 1995)** —
el cerebro usa DOS sistemas a propósito (hipocampo rápido/episódico + neocórtex
lento/semántico) porque uno solo sufre **interferencia catastrófica**; la consolidación
es el diálogo entre ambos. Súmese **Society of Mind (Minsky)** y, en ML, **Mixture of
Experts (MoE)**. Lo híbrido determinista+neuronal es **neuro-simbólico**.

**Lo clave:** gran parte de esto NO es un modelo, es **cómputo determinista**. Cada
dinámica declara su procesador:

| Función de memoria | Procesador | Tier |
|---|---|---|
| Spreading activation, pesos Hebbianos, decay (§3.1/3.6/3.7) | NINGÚN modelo — cómputo de grafo | **0** |
| Encoding / similitud semántica | modelo de **embeddings** (nomic, ya separado :1234) | — |
| Salience / clasificación técnico-personal (§3.3) | modelo chico/rápido | **1** |
| Consolidación / abstracción "dormir" (§3.4/3.5) | modelo barato/local, offline/batch | **1** |
| Reconstrucción / razonamiento (§3.2) | modelo principal (Sonnet) | **2** |
| Planificación dura | Opus (`planear_con_opus`) | **3** |

Mapea 1:1 a los tiers de `routing.py`/`model_registry.py`. Resultado: más cerebro Y
más barato — el modelo caro se reserva para reconstruir/razonar; la mecánica del grafo
es tier 0 (exacta, instantánea, gratis) y la cognición repetitiva va al local.

## 4. Base filosófica (de los videos de lógica/Gödel) — por qué este diseño tiene sentido
- **Wittgenstein (segundo): el significado viene del USO y el contexto**, no de
  definiciones fijas. Es exactamente la justificación del fortalecimiento Hebbian
  (§3.6) y de la recuperación dependiente de contexto.
- **Peirce: deducción / inducción / ABDUCCIÓN.** Raphael ya deduce (reglas/gates) e
  induce (patrones de episodios); falta nombrar la **abducción** (hipótesis = mejor
  explicación con datos incompletos), que el LLM hace natural. La reconstrucción (§3.2)
  ES abductiva: arma la mejor versión con lo que hay.
- **Gödel: todo sistema formal tiene verdades que no puede probar.** Humildad de
  diseño: Raphael es un sistema computacional, no finjamos que "trasciende" como
  argumenta Penrose (tesis discutida). La flexibilidad cerebro-símil (asociación,
  reconstrucción) es lo que da potencia DENTRO de los límites formales, no fuera.

## 5. Cómo se construye sobre lo que ya hay
- **Vault** (semántica) + **grafo de links** → base para spreading activation (§3.1)
  y Hebbian (§3.6): hay que agregar **pesos** a las aristas y seguir links en el recall.
- **Memoria episódica** (`app/memory/`) → ya tiene crudo firmado (provenance §3.3),
  recall, y la base de consolidación/salience (§3.4, §3.7). Falta: reconsolidación
  (§3.5) y el job de "sueño".
- **Embeddings** → siguen dando el primer hit; de ahí se esparce por links.

## 6. Fases
1. ✅ **HECHO (2026-10-04)** — **Spreading activation** en el recall. Tier 0 puro:
   `app/obsidian/spreading.py` (`propagate` pura + `search_spreading`), tool
   `obsidian_buscar_asociativo`, test `tests/test_spreading.py`. Semillas por coseno
   (embeddings) → propagación por `build_graph()` con decay + convergencia.
2. ✅ **HECHO (2026-10-04)** — **Pesos Hebbianos** en las aristas:
   `app/obsidian/hebbian.py` (`bump` pura + persistencia JSON profile-aware), wireado
   en `search_spreading(usar_pesos=True, reforzar=...)` y expuesto en la tool
   (`reforzar=true`). "Se activan juntas → se cablean juntas"; satura en cap para no
   dominar. Test `tests/test_hebbian.py`. **Pendiente de Fase 2:** reconsolidación de
   CONTENIDO (§3.5, reescribir la nota con lo aprendido) — hoy solo reforzamos la
   arista, no el cuerpo de la nota.
3. ✅ **HECHO (2026-10-05)** — **Job de consolidación ("sueño")**:
   `app/obsidian/consolidation.py`. Agrupa notas recientes relacionadas (clusters por
   coseno, core puro `_components`/`_cluster_from_pairs`), y por cluster escribe una
   nota de SÍNTESIS con el LLM local (tier 1) + refuerza las aristas Hebbianas.
   ADITIVO y reversible (nunca toca las notas originales), idempotente
   (`consolidation-id`). Tool `memoria_consolidar` (dry-run por default) + job en
   background `consolidation_loop` (default APAGADO, `CONSOLIDATION_ENABLED`). Test
   `tests/test_consolidation.py`. La poda NO borra: la hace la Fase 4 bajando ranking.
4. ✅ **HECHO (2026-10-05)** — **Olvido adaptativo** (fuerza de recuperación):
   `app/obsidian/strength.py`. Fuerza por nota que sube al usarse (bump, reconsolidación
   §3.5) y decae exponencialmente sin uso (half-life); pondera el ranking de
   `search_spreading` (`usar_fuerza`). Nunca entierra por debajo de lo neutro, nada se
   borra (el crudo queda). Core puro, tier 0. Test `tests/test_strength.py`.

### Capacidad transversal: ingesta web directa (2026-10-04)
Pedido de Damian: que Raphael pueda **indexar+embeber información directa de internet**
("una biblioteca para IA a escala personal"). Hecho en `app/obsidian/web_ingest.py`
(tool `obsidian_ingerir_web`): URL → `web_get` (fetch que escala solo, JS incluido) →
`chunk_text` (pura, por párrafos con solape) → embeber cada chunk con nomic local →
guardar como notas enlazadas con **provenance** (URL + fecha + web-ingest-id, §3.3).
NO llama al modelo de chat (tier 0 + embeddings): barato, idempotente (dedup por
web-ingest-id). El contenido ingerido queda recuperable por búsqueda semántica Y por
spreading (Fase 1), así que la "biblioteca" crece y se auto-cablea con el uso (Fase 2).
Test `tests/test_web_ingest.py`.

## 7. Estado del arte y el hueco real (investigación 2026-10-04)
Damian preguntó cómo lo hacen las empresas y si hay un hueco para construir algo propio.
- **Exa** ("search engine for AIs"): ingiere documentos de toda la web, los **chunkea y
  embebe en background** (modelo de predicción de párrafo para extraer el contenido),
  los mete en una base vectorial y busca por **coseno + keyword**. Entrena el embedding
  para "predecir el próximo link relevante" en vez de la próxima palabra. Es, a escala
  web, exactamente el pipeline de `web_ingest.py` a escala personal.
- **Firecrawl / Jina Reader**: la capa de **extracción** (URL → markdown limpio para LLM).
  Jina Reader es un endpoint gratis por-URL (`r.jina.ai`); Firecrawl hace crawl de sitio
  entero + render JS. En Raphael esa capa ya la cubre `web_get` (Scrapling con Edge).
- **Common Crawl / HuggingFace / FineWeb / The Pile**: los corpus abiertos ya digeridos.
- **Capa de acceso "cualquier IA" = MCP**: el estándar por el que un agente consulta una
  base externa. Exponer el vault como servidor MCP es el camino real de "biblioteca que
  accede cualquier IA" sin inventar protocolo.

**Restricción dura que enfoca la idea:** los embeddings son específicos del modelo — un
vector de nomic NO es intercambiable con uno de OpenAI/Cohere. No existe "embedding
universal": o se guarda texto limpio y cada IA lo embebe (lo que hace Exa), o se
estandariza un modelo. Por eso el formato compartible es **texto crudo + provenance**
(que ya guardamos), y el índice embebido es por-modelo.

**El hueco para Raphael (no competir con Exa):** una **biblioteca vertical, local,
pre-chunkeada y servida por MCP** sobre dominios donde Damian tiene algo propio (trading
Fede Esses, seguridad, su estudio). Lo universal/web-scale es moonshot de infra; lo
vertical-local-MCP es construible y ya está en marcha: `web_ingest` + vault + spreading
+ Hebbian **es** el prototipo de esa biblioteca.

## Fuentes (material aportado por Damian, 2026-10-04)
- **Video de memoria** (ciencia de la memoria humana): reconstrucción ("no abrís un
  recuerdo, lo montás"), múltiples sistemas, reconsolidación, falsos recuerdos
  (Loftus), olvido adaptativo, HSAM. → §3.2, §3.3, §3.5, §3.7. (link mvhTaPusKi8 relacionado.)
- **Video "Date un Blog"** (filosofía de la lógica y la computación): Frege, Russell,
  Wittgenstein, Círculo de Viena, Turing, Hilbert, Gödel, Peirce (inferencia), Arendt. → §4.
- **Video sobre Gödel** (incompletitud, numeración de Gödel, límites de la IA, Penrose,
  "¿qué nos hace especiales?"). → §4.
- Pendiente de revisar (otro hilo): "Xiaomi y DeepSeek… el mayor problema de tu IA
  local" (Jorge Marfil, `ytlfkXZKB9A`) — optimización de IA local, no estructura de memoria.
- Relacionado: `SPEC-memoria-episodica.md`, `BASES-ACADEMICAS-de-mis-formas.md`
  (Barabási/Seung redes, Hofstadter analogía).
