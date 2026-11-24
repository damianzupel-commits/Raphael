# Raphael Scout

**Producto #1 de la suite Raphael: investigación / intel continuo.**

Scout investiga temas en la web real y captura lo que encuentra como notas
trazables a su fuente, en tu vault. Es el primer módulo separado del monolito
JarvisRemote (2026-11-02). Blueprint de producto completo en
[`../../docs/SPEC-PRODUCTO-INVESTIGACION.md`](../../docs/SPEC-PRODUCTO-INVESTIGACION.md).

## Por qué existe como módulo aparte

El Raphael completo le manda al modelo **~50 tools** en cada turno (~29K tokens
de request). Scout usa un **set chico de 8 tools** enfocadas en investigar y
capturar → el request baja a unos pocos K. Eso lo hace:

- **Liviano** → entra en tiers de API gratis con límite de TPM bajo (ej. Groq
  free, 8.000 tokens/min, donde el Raphael completo no entra).
- **Rápido** también en local (menos contexto que procesar).
- **Portable** → el día que viva en su propio repo, arrastra poco.

## Qué reusa del núcleo (no lo duplica)

- Cliente LLM OpenAI-compatible (vía `scout/config.py`).
- Registro y ejecutor de tools: `app.tools.call_tool` + `openai_tool_schemas()`
  filtrado a `SCOUT_TOOL_NAMES`.
- A través de esas tools: el vault de Obsidian y el navegador del núcleo.

Lo único propio de Scout es un **loop de agente fino** (`scout/engine.py`): no
arrastra `run_agent` del monolito (gates de PC, mission_control, phone_link,
persistencia FastAPI).

## BYOM — traé tu propio modelo

Scout tiene su **propia** config de modelo, independiente del Raphael grande.
Variables de entorno (todas opcionales; si faltan, cae a la config del núcleo):

| Variable             | Qué es                         | Fallback              |
|----------------------|--------------------------------|-----------------------|
| `SCOUT_LLM_BASE_URL` | endpoint OpenAI-compatible     | `LMSTUDIO_BASE_URL`   |
| `SCOUT_LLM_API_KEY`  | api key                        | `LLM_API_KEY`         |
| `SCOUT_LLM_MODEL`    | nombre del modelo              | `LMSTUDIO_MODEL`      |
| `SCOUT_CAPTURE_DIR`  | carpeta donde captura notas    | `RESEARCH_WORKING_DIR`|

### Ejemplo: apuntar Scout a Groq free (sin tocar el Raphael grande)

En `backend/.env`:

```
SCOUT_LLM_BASE_URL=https://api.groq.com/openai/v1
SCOUT_LLM_API_KEY=gsk_tu_key_de_groq
SCOUT_LLM_MODEL=openai/gpt-oss-120b
```

Como el request de Scout es chico, **sí entra** en el límite gratis de Groq
(a diferencia del Raphael completo).

## Cómo correrlo solo

```bash
cd backend
python -m scout "investigá el estado de los LLM locales en 2026"
```

Sin argumentos entra en modo interactivo. Al arrancar imprime a qué modelo y
endpoint está apuntando (para confirmar el BYOM de un vistazo).

Programático:

```python
from scout import run_scout
texto, history = await run_scout("tu tema")
```

## Alcance (qué entra y qué no)

- **Entra:** investigar a pedido (`research_topic`), capturar notas trazables,
  leer/listar lo ya capturado para no repetir, archivos de trabajo (`fs_*`).
- **Para Memoria (producto #2), NO Scout** (SPEC decisión #5): la dedup y
  búsqueda **semántica** fina (embeddings). Scout captura en crudo; Memoria
  ordena. `obsidian_search_notes` acá es solo para evitar repetir trabajo obvio.
- **v1.1+ (todavía no):** research autónomo/continuo (`proactive.py`), digest
  diario, más tipos de fuente. El loop continuo y los watchers de `app/ingestion`
  son el dominio de Scout pero aún no están cableados a este engine.

## Estado

Fase 1 de la separación: módulo con superficie propia (identidad + engine
liviano + CLI + BYOM), reusando el núcleo. Próximos pasos en el SPEC §5.
