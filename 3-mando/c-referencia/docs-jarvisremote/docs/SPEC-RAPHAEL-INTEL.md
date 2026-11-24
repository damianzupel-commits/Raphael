# 🌐 Spec técnico — Raphael Intel (cerebro de inteligencia del mundo)

> **Documento de DISEÑO.** Describe cómo Raphael pasa de "asistente que responde"
> a "asistente que SABE lo que está pasando en el mundo" — juntando, resumiendo y
> haciendo buscable información pública (geopolítica, economía, ciencia, noticias,
> tecnología) en tu vault. Es la versión legal y limpia de "conocimiento es poder":
> información sobre **el mundo y los sistemas**, no vigilancia de personas.
>
> Creado: 2026-09-20. Reusa infraestructura que YA existe: no es un proyecto nuevo,
> es unificar piezas sueltas en un solo cerebro que se alimenta solo.

---

## 1. La idea en una frase

Cada día, Raphael sale a buscar qué cambió en el mundo (en los temas que a vos te
importan), lo **resume**, lo **guarda como notas** en tu vault, y te lo puede
**contar en un brief** o **responder cuando preguntás**. El valor no es juntar todo
—eso es ruido— es juntar **con dirección** y dejarlo **buscable y sintetizado**.

---

## 2. Qué reusa (no se reinventa nada)

- **El ingester de playlist** (`app/ingestion/youtube_playlist.py`): ya hace el
  patrón exacto — traer algo de afuera → resumir con el LLM → guardar una nota
  firmada 'jarvis' con formato fijo, **deduplicando** por ID y actualizando un
  índice. Raphael Intel **generaliza ese patrón** a más fuentes.
- **El vault** (`app/obsidian/`): la memoria. Notas en Markdown real, con búsqueda
  **semántica** (embeddings + coseno). Ya sabe guardar y buscar por significado.
- **El scheduler** (tareas programadas / el patrón del escaneo diario de malware en
  background): el pulso que dispara la ingesta sin que tengas que pedirla.
- **El LLM local**: el mismo que ya usás para resumir.

---

## 3. Arquitectura (4 piezas)

```
Fuentes públicas ─► [SourceIngester por fuente] ─► resumen (LLM) ─► Nota en el vault
                                                                        │
        Scheduler (diario) ──────────────────────────────────────────► │
                                                                        ▼
                                           Síntesis: (a) Brief diario  (b) Q&A sobre el vault
```

1. **SourceIngester (abstracción base).** Un contrato chico, una implementación por
   fuente: `fetch()` (trae ítems nuevos de la fuente) → `normalize()` (a un formato
   común: título, fecha, url, texto) → `summarize()` (LLM) → `save()` (nota en el
   vault, deduplicada por ID/hash, taggeada por dominio). Igual que el ingester de
   playlist, cada fuente **se saltea lo que ya tiene nota** y no rompe si una falla.

2. **Registro de fuentes por dominio.** Un mapa `dominio -> [ingesters]`, para poder
   correr "solo ciencia" o "todo". Config en archivo (qué fuentes, cada cuánto,
   filtros de relevancia), no hardcodeado.

3. **Scheduler.** Corre los ingesters en su cadencia (diaria/horaria según fuente),
   en background. Reusa el patrón del escaneo diario que ya tenés.

4. **Capa de síntesis (lo que lo hace "Jarvis").**
   - **Brief diario:** el LLM lee las notas nuevas del día y te arma un resumen
     ("qué cambió en el mundo hoy, en tus temas"). Encaja con el morning brief.
   - **Q&A:** preguntás "¿qué está pasando con X?" y responde con búsqueda semántica
     sobre TODO lo acumulado, citando las notas fuente.

---

## 4. Dominios y fuentes (todas públicas)

| Dominio | Fuentes | Acceso |
|---|---|---|
| **Geopolítica / noticias** | GDELT 2.0 (eventos mundiales), ACLED (conflictos), RSS de agencias, Crisis Group | GDELT y RSS libres; ACLED con registro gratis |
| **Economía** | FRED (datos de la Fed), World Bank Open Data, BCRA / INDEC (Argentina) | World Bank sin key; FRED con key gratis; Argentina vía API/algún scraping |
| **Ciencia** | arXiv, PubMed (NCBI), bioRxiv, Semantic Scholar | Todas con API gratis (algunas con rate limit) |
| **Tecnología / seguridad** | NVD (CVEs), Hacker News, GitHub Trending | NVD y HN con API libre; GitHub Trending por scraping |

Se arranca con **una fuente por dominio** y se suma desde ahí; no todas de una.

---

## 5. El principio rector: dirigido, no hoarding

El enemigo es el ruido. Reglas de diseño:
- **Filtro de relevancia por fuente:** keywords/temas que a vos te importan (config).
  No se ingiere todo lo que publica una fuente, solo lo que matchea tus intereses.
- **Se guarda el RESUMEN, no el volcado crudo.** Una nota concisa por ítem, taggeada,
  buscable. El texto completo queda linkeado, no pegado.
- **Deduplicación** por ID/hash: correr de nuevo no duplica.
- **Presupuesto por corrida:** tope de ítems nuevos por fuente por día, para que el
  vault (y el costo de LLM) no exploten.

---

## 6. La línea legal (no negociable)

Información sobre **sistemas, mercados, eventos, ciencia y el mundo público** — no
sobre personas. Nada de agregación de datos personales, reconocimiento facial,
tracking de individuos ni scraping de perfiles. Recon de personas solo si es tu
propia huella o un objetivo autorizado (y eso va por el gate de auditoría, no por acá).

---

## 7. Orden de construcción (fases, cada una chequeable)

No se construye el sistema entero de una. Se prueba el patrón con UN dominio y se expande:

1. **Fase 0 — El contrato + una fuente.** La abstracción `SourceIngester` + UNA fuente
   real end-to-end (recomendado: **arXiv**, tiene API limpia y alimenta Fénix directo).
   Prueba que traer → resumir → guardar → deduplicar funciona. *Testeable en aislado.*
2. **Fase 1 — Un dominio completo.** 2-3 fuentes del mismo dominio + el filtro de
   relevancia + el scheduler diario.
3. **Fase 2 — El brief diario.** La síntesis que te cuenta qué cambió. Encaja con el
   morning brief.
4. **Fase 3 — Q&A.** Preguntas en lenguaje natural sobre todo lo acumulado.
5. **Fase 4 — Más dominios.** Sumar geopolítica, economía, tecnología uno por uno.

> Cada fase se gana su lugar. Un solo dominio bien resumido y buscable ya es el 70%
> del valor; el resto es expansión.

---

## 8. Riesgos y decisiones abiertas

- **Rate limits / API keys:** varias fuentes las manejan; empezar por las libres.
- **Crecimiento del vault:** el resumen + dedup + presupuesto lo contienen, pero hay
  que vigilarlo. La búsqueda semántica escala bien; el brief diario acota a lo nuevo.
- **Calidad del resumen:** depende del modelo (Tier 2). Un resumen malo es peor que
  no tener la nota — vale un chequeo de calidad tipo Catador si se nota ruido.
- **¿Empujar (brief) o tirar (Q&A)?** Las dos, pero el brief es lo que lo hace sentir
  proactivo; el Q&A es lo que lo hace útil bajo demanda.

---

## Referencias
- `app/ingestion/youtube_playlist.py` — el patrón de ingesta que se generaliza.
- `docs/SPEC-HARNESS-MULTIAGENTE.md` — el motor multi-agente (una síntesis por dominio
  podría ser una mini-brigada de intel a futuro).
- Alimenta: **Fénix** (ciencia/biotec) y el **war-tracker** (geopolítica), que ya tenés.
