# Investigación · b-codigo
Brigada `investigacion` v2.0.0 para el harness v2. Paquete `raphael_investigacion` (`src/`), manifiesto en `manifest.yaml` (la copia del paquete, `src/raphael_investigacion/manifest.yaml`, es la fuente; `scripts/sync_manifest.py` las iguala y un test lo comprueba). Solo importa `raphael_core` y la biblioteca estándar; PDF, Word y EXIF usan `pypdf`, `python-docx` y `Pillow` si están (extra `forense`), y si faltan lo dicen.

## Qué hay
| Módulo | Qué hace |
| --- | --- |
| `casefile.py`, `model.py` | Casos, nodos y aristas tipados (Persona, Cuenta, Host, Archivo, Evento, Transacción, Organización, Dispositivo), artefactos con sha256, retractar sin borrar, registro encadenado por hash (y firmado con HMAC si hay `INVESTIGACION_LOG_KEY`) |
| `ingest.py`, `timeline.py` | WhatsApp, Telegram, CSV, logs Apache/Nginx y auth.log, txt/md/pdf/docx, EXIF. Idempotente, sin modelo, sin adivinar estructura |
| `entities.py` | Entidades por reglas (o por modelo local) como propuestas pendientes; fusiones `mismo_que` sin combinar nodos |
| `reports.py` | Grafo, línea de tiempo e informe md/html/json que separa lo confirmado de lo pendiente |
| `scout.py`, `web.py`, `search/` | Búsqueda con fuente y fecha por afirmación, verificación contra la página, resumen del modelo validado (citas y cifras); proveedores Brave, SearXNG y `mock`; lectura de páginas que nunca toca la red local |
| `trends.py` | Temas vigilados, novedad por URL, relevancia por palabras clave, tope diario, avisos con fuente |
| `ideas.py`, `sandbox.py` | Ideas, puntaje, spec con «por definir», prototipos que solo corren aprobados en carpeta temporal aislada |
| `service.py` | Toda la lógica en un lugar; las tools de los efímeros y los comandos de los cocineros la llaman |
| `spec.py`, `cooks/`, `health.py` | Jefe con 4 efímeros privados, 4 cocineros (`forense`, `scout`, `ideas`, `tendencias`), salud y montaje |

## Adaptadores: real y simulado
Búsqueda: `brave` y `searxng` son reales (`BRAVE_SEARCH_API_KEY`, `SEARXNG_URL`); `mock` no usa red ni clave. Se elige con `config.search.providers` o `SCOUT_SEARCH_PROVIDERS`. Los tests usan `mock` y transportes simulados. Sin proveedor configurado Scout lo dice y no inventa. Plantilla de claves: `investigacion.env.plantilla`.

## Config (`installation.brigades.investigacion.config`, todo opcional)
Ver `config.py`: `private` (default `true`), `inbox_dir`, `artifacts_dir`, `reports_dir`, `search`, `trends`, `sandbox`.

## Reglas que el código hace cumplir
- Modelos locales: los cocineros llaman con `private=True` y los efímeros son `private`. Sin modelo local: reglas y aviso, nada va a la nube.
- El forense solo toma archivos de `inbox_dir` cuando lo pide un modelo, y nunca nombres de claves o credenciales.
- Propuestas de entidad y fusiones no entran solas: confirmarlas es acción de nivel `aprobacion`. `retractar` y `borrar_tema` son `irreversible`.
- `prototipo_correr` es `dangerous` (no se carga en la nube) y pide aprobación. El sandbox NO es un aislamiento de sistema operativo (ver `sandbox.py`).
- Limitaciones conocidas: las tools que registra `setup` no publican eventos ni auditan (solo los cocineros), no hay OCR, no hay firma Ed25519/DPAPI (se usa HMAC), el informe PDF se hace imprimiendo el HTML.
