# SPEC — Producto #1: Investigación (research continuo)

> Blueprint para separar la primera brigada del monolito y lanzarla como producto.
> Creado 2026-11-01 con Claude. Es el MVP cuña de la "suite Raphael" (ver la charla
> de productos estilo Adobe). NO se ejecuta nada hasta que Damian confirme el scope.

---

## 0. TL;DR

- **Qué es:** un agente que **investiga y se mantiene al día solo**, y guarda todo en
  un **cerebro local tuyo** (notas Markdown estilo Obsidian, trazables a la fuente).
- **Para quién:** entusiastas de IA / gente que quiere estar al día de temas que le
  importan sin depender de newsletters o de pagar un chatbot.
- **Diferencial (clavar esto o se pierde entre los grandes):** corre **local y gratis**,
  es **autónomo y continuo** (trabaja mientras no estás), **vos elegís las fuentes**, y
  **vos sos dueño de los datos** (notas en tu disco, no en la nube de otro).
- **Regla de oro:** esto es **UNA cuña**. Memoria/Cerebro es el complemento que sale
  justo después (producto #2), no ahora.

---

## 1. Capacidades

### MVP (v1 — lo que se lanza primero)
1. **Investigar a pedido** (`research_topic`): le pedís un tema → navega la web real
   (varias páginas), extrae el texto con la fuente citada, y lo guarda como nota
   trazable. Deduplica contra lo que ya tenés (no repite) y linkea notas relacionadas.
2. **Fuentes en continuo** (`ingestion/` + watchers): agregás fuentes (playlist de
   YouTube, arxiv, páginas web) → cada tanto revisa si hay algo nuevo y lo ingiere
   como nota/resumen, solo. Esto es el "se mantiene al día" del pitch.
3. **Tu base de conocimiento local**: todo queda como notas Markdown (compatibles con
   Obsidian), organizadas por categoría, con fuentes. Tuyas, en tu disco.

### Después (v1.1 / v2 — NO en el primer lanzamiento)
- **Research autónomo** (`proactive.py`): que amplíe temas por su cuenta sin que lo
  pidas. (Hoy es liviano; lo madurамos para v1.1.)
- **Digest/resumen diario** ("esto es lo nuevo relevante de hoy").
- Más tipos de fuente (RSS, podcasts, X/Twitter, etc.).
- La capa de **organización/adaptación** = eso es el **producto #2 (Memoria)**.

---

## 2. Arquitectura: núcleo compartido vs producto

Clave (lo del Clean Architecture): **no construimos un harness nuevo.** Un **núcleo
compartido** + este producto enchufado encima.

**Núcleo compartido (lo usan TODOS los productos de la suite):**
- Loop del agente + cliente LLM (local/Ollama) + ruteo de modelo.
- Vault de Obsidian + embeddings (búsqueda semántica).
- Tool de navegador (Playwright/Edge).
- Config + gates de seguridad (sandbox FS, instrucción-vs-dato, etc.).

**Específico de este producto (lo que se "separa"):**
- `tools/research.py` (`research_topic`).
- `ingestion/` entero (`sources.py`, `base.py`, `youtube_playlist.py`,
  `arxiv_source.py`, `playlist_watcher.py`).
- `proactive.py` (loop continuo) — pero apagado por default en v1.
- `research_cases.py` (hilos de investigación).
- `obsidian/web_ingest.py` (ingesta de web puntual).

**Qué NO va en este producto (importante):**
- `app/investigation/` (parsers forenses: exif, logs, chats, csv, docs) — eso es
  **forense de evidencia**, otra brigada/producto. El nombre "Investigación · FORENSE"
  del panel confunde: el producto que lanzamos es **research/intel**, no forense.
- Seguridad, Trading, Operaciones, Antimalware, etc. — otros productos/más adelante.

---

## 3. Lo que un desconocido instala y corre (el desafío real)

Esto es lo más difícil del MVP, y hay que ser honestos: hoy Raphael corre en la PC de
Damian con su setup. Para que **otra persona** lo use necesita:
- **Ollama + un modelo local chico** (para los resúmenes). Para esta audiencia (IA
  enthusiasts) "corre local con Ollama" es un **punto a favor** (privacidad, gratis),
  pero el instalador tiene que **chequear/instalar Ollama y bajar el modelo solo**.
- **Un modelo de embeddings** (para dedup/búsqueda semántica del vault). Idealmente
  servido por el mismo Ollama (no LM Studio aparte) para simplificar el install.
- **Playwright + un navegador** (para `research_topic`). Playwright baja su propio
  Chromium → se resuelve con `playwright install`.
- **yt-dlp** (para fuentes de YouTube).
- **Carpeta de notas** (vault). El MVP puede traer una propia; compatible con Obsidian
  si el user ya lo tiene.

**Meta de empaque v1:** un **instalador de un paso** (script o ejecutable) que deje
todo listo y un comando/acceso directo para arrancar. Sin esto, no hay MVP real: un
producto que solo corre en la máquina del autor no es un producto.

---

## 4. Riesgos / lo honesto

- **Espacio competido:** "mantenete al día con IA" lo prometen muchos. Sin el
  diferencial (local, autónomo, tus fuentes, tus datos) bien clavado en el pitch,
  se pierde. El diferencial es real — hay que comunicarlo, no asumirlo.
- **Empaque > features:** el 70% del laburo del MVP es que **otro** lo pueda correr.
  No subestimar esto.
- **Ingesta de YouTube NUNCA probada contra YouTube real** (lo dice el propio código):
  hay que validarla end-to-end antes de prometerla como feature.
- **Depende del motor andando:** hoy el chat local todavía no responde (modelo local
  pendiente). Sin eso, no hay resúmenes ni research → no hay MVP. **Prerrequisito.**
- **Calidad con modelo chico:** los resúmenes con un modelo local chico (ej. 8B) son
  más flojos que con frontera. Hay que calibrar expectativas / elegir bien el modelo.

---

## 5. Plan de extracción (tus pasos 1-5, para ESTE producto)

1. **Confirmar scope** (este doc) — qué entra en el MVP, qué no.
2. **Motor andando** (prerrequisito): modelo local + embeddings funcionando.
3. **Separar el núcleo compartido** en un paquete reutilizable (agente, LLM, vault,
   browser, config) — sin duplicarlo.
4. **Armar el producto** = núcleo + módulos de §2 + una UI/CLI mínima + instalador.
5. **Validar end-to-end** (research_topic real + una fuente real de YouTube) en una
   máquina "limpia" (no la de Damian).
6. **Publicar en GitHub** (repo propio del producto, sin secretos) + README con el pitch.
7. **Facebook** + recoger reportes de bugs.

---

## 6. Decisiones tomadas (2026-11-01, con Damian)

1. **Nombre: `Raphael Scout`** (research/intel). La suite sigue el patrón "Raphael
   <producto>" (ej. Raphael Mind = Memoria). Verificar que no choque antes de publicar.
2. **v1 INCLUYE el research autónomo/continuo** — es el enganche del producto, no se
   difiere. ⚠️ Implica madurar `proactive.py` (hoy es flaco: solo "suma un dato a un
   caso") para que sea un feature vendible de verdad → sube el alcance de v1.
3. **BYOM — "traé tu propio modelo".** El producto es el **harness + las tools**; el
   usuario enchufa el cerebro que quiera: su Ollama/LM Studio local, o su API
   (OpenAI/OpenRouter/Anthropic, cualquier endpoint OpenAI-compatible). Esto **elimina
   el mayor dolor de empaque** (no se bundlea modelo). Asteriscos: (a) los embeddings
   de la memoria semántica también necesitan un modelo → configurable, o traer uno
   chico embebido; (b) con modelo local chico, los resúmenes son más flojos → avisarlo.
4. **Filtro por interés + carpetas a elección.** El usuario **declara de antemano qué
   le interesa POR FUENTE** (ej: conecta un diario pero solo quiere fútbol; un blog
   gamer pero solo LoL). El harness **recopila en crudo SOLO lo que matchea**, en la
   **carpeta que el usuario elija**. Se integra con el Obsidian del user si lo tiene.
   ⚠️ Esto **da vuelta la filosofía vieja del código** ("la relevancia es una etiqueta,
   NUNCA un filtro" — ver `youtube_playlist.DEFAULT_RELEVANCE_TOPICS`): esa regla era
   para el uso personal de Damian (no perder nada propio). En el PRODUCTO, para otros
   usuarios, **el filtro ES el valor** → la relevancia SÍ filtra, configurable por fuente.
5. **Embeddings → Memoria, NO Scout.** Scout **recopila en crudo**; los embeddings y la
   búsqueda/dedup semántica son tarea del **Cerebro/Memoria** (producto #2). Implica
   sacar de `research_topic` el chequeo "ya cubierto" (similitud coseno) y el linkeo
   semántico de notas relacionadas — eso lo hace Memoria sobre lo que Scout dejó crudo.
   Beneficio: **Scout queda aún más liviano** — sin embedder; la captura cruda ni
   siquiera necesita modelo (el resumen/filtro inteligente sí usa el chat BYOM,
   opcional). Refuerza el pipeline: Scout trae crudo, Memoria ordena.

### Impacto de estas decisiones en el scope
- **§1 Capacidades:** agregar a v1 el **research autónomo** (#2) y el **filtro de
  interés por fuente con captura cruda a carpeta elegida** (#4).
- **§3 Empaque:** cambia a **BYOM** (#3) — ya no se bundlea Ollama+modelo; el instalador
  configura el endpoint del modelo del user (local o API) + un embedder.
