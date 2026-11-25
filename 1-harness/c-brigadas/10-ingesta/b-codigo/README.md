# Ingesta · b-codigo
La brigada **ingesta** (pieza 10) para el harness v2, versión 2.0.0. Mete conocimiento nuevo al vault desde YouTube, la web y arXiv. Cada nota guarda su origen (URL y fecha).

## Qué hay
- `manifest.yaml` (y su copia dentro del paquete, que es la fuente: `scripts/sync_manifest.py`): 3 cocineros, 10 acciones con su nivel, 5 comandos de lectura, eventos y config.
- `src/raphael_ingesta/`
  - `base.py`: lo común (cola, no duplicar, resumir, guardar, vigilar, borrar).
  - `cooks/youtube.py`, `cooks/web.py`, `cooks/arxiv.py`: un cocinero por fuente.
  - `adapters/`: **uno real y uno simulado por fuente**. `real` toca la red (httpx, yt-dlp opcional); `mock` da datos fijos. Se elige con `modo: real | simulado` (global) o `modos: {youtube: simulado}`.
  - `summary.py`: resumen con el modelo del harness (rol `cocinero`) o, sin modelo, por reglas (extractivo, sin inventar, y la nota lo dice).
  - `vault.py`: notas en Markdown (Obsidian) en `<RAPHAEL_VAULT_DIR>/Ingesta/<fuente>/`. Sin carpeta, la nota queda en el almacén de la brigada y viaja en el evento `nota.ingerida`.
  - `safeurl.py`: solo sitios públicos (nada de localhost ni red interna, tampoco por redirección).
  - `health.py`: salud y `setup`.
- `ingesta.env.plantilla`: lo que hay que cargar (todo opcional). Lista completa en `LIENZO-DAMIAN.md`.

## Cómo trabaja
- La persona dueña manda un link (video, lista, página, paper) y la brigada lo ingiere. **Solo mensajes confiables**: un tercero no dispara ingestas.
- Una acción procesa **un** ítem. Una lista o una búsqueda de arXiv se **encola** y se vacía de a pocos en cada `tick` (`por_pasada`), así ninguna pasa el tope de tiempo del harness.
- Idempotente por id de fuente (video, paper, URL sin `#`). Lo que falla sin arreglo (video sin subtítulos) queda en `fallidos` y no se reintenta solo; un fallo transitorio se reintenta 3 veces con espera creciente.
- **Autonomía:** ingerir, encolar y revisar son `automatico` (leen fuentes públicas y escriben notas, reversible); `vigilar` (deja la brigada trabajando sola) y `borrar_nota` (irreversible) piden `aprobacion`. Cambiable por instalación (`autonomy: {"ingesta.ingerir_video": "aprobacion"}`).
- **Terceros = dato:** el texto va al modelo entre `<contenido_externo>`, la respuesta se sanea (sin `[[enlaces]]` inventados, una línea de título) y nada se ejecuta.
- Eventos: publica `nota.ingerida` (con el contenido, para que Memoria la tome por el harness) e `ingesta.fallo`. No consume ninguno.

## Probar
```bash
cd ../c-salud/pruebas && python -m pytest        # 73 tests, sin red ni claves
ruff check ../..
python ../c-salud/mantenimiento/probar_real.py   # UNA vez en la PC: prueba los adaptadores reales contra la red
```
