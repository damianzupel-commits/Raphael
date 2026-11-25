# Memoria · Cerebro · b-codigo
Brigada `memoria` 2.0.0 para el harness v2 (contrato ≥2.1). Portada de `3-mando/c-referencia/memory/`.

## Qué hay
| Módulo | Qué hace |
| --- | --- |
| `vault.py` | Vault de notas Markdown con frontmatter (autores `jarvis`/`human`, carpetas temáticas, grafo de wikilinks, índice por categoría, exportar .zip) |
| `embeddings.py` | Adaptador real (`LocalEmbedder`, servidor local LM Studio/Ollama; rechaza direcciones que no son de la PC) y simulado (`MockEmbedder`); índice de vectores en el espacio de la brigada |
| `graph.py` | Cómputo puro: activación propagada, MMR, confianza, analogía estructural, huecos, clusters con umbral + brecha |
| `learning.py` | Hebb, fuerza de recuperación (olvido adaptativo), sucesión/sorpresa, crédito por resultado |
| `episodes.py` | Memoria episódica: crudo, episodios, clasificación fail-safe a personal, registro con cadena de hashes |
| `brain.py` | El Cerebro: búsqueda híbrida, asociativa, evidencia, componer, analogías, curiosidad, consolidar |
| `actions.py` | Las 7 acciones con efecto (niveles en el manifiesto) |
| `cooks/` | `recuperador`, `consolidador`, `asociativo`, `proactivo` |

## Reglas
- Todo pedido a un modelo va **privado**; sin modelo local → reglas y aviso (`memoria.degradada`). Ver `modelos.memoria.yaml`.
- Sin embeddings → palabra clave y aviso. Con el servidor apagado la nota se guarda igual, sin vector (`reindexar` lo arregla).
- El contenido de terceros (eventos `memoria.captura`, `nota.ingerida`, mensajes) es dato; un mensaje de un tercero nunca lee el vault.
- `consolidar`, `olvidar` y `exportar_vault` piden aprobación; el resto es aditivo y local.

## Entradas por evento
`memoria.captura {brigada, title, content, tags, fuente}`, `memoria.turno {conv_id, history, dominio}` y `nota.ingerida` (Ingesta; si `ruta` cae dentro del vault solo se indexa).

## Probar
`cd ../c-salud/pruebas && python -m pytest -q` (149 tests, sin red). Claves y datos: `memoria.env.plantilla`.
