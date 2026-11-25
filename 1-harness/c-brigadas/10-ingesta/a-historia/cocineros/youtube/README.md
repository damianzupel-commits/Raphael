# YouTube (videos y listas)

- **Brigada:** 10-ingesta · Ingesta (chat 10)
- **Tipo:** existente
- **Qué hace:** Ingiere videos y listas de reproducción, y vigila listas.

## Código nuevo (harness v2)
En `1-harness/c-brigadas/10-ingesta/b-codigo/src/raphael_ingesta/`: `cooks/youtube.py` y `adapters/youtube.py` (portado de `youtube_playlist.py`, `playlist_watcher.py` y la tool `ingestion.py`).

Acciones: `ingerir_video`, `ingerir_lista`, `vigilar`. Un video por acción; la lista se encola. Subtítulos con yt-dlp (manuales antes que automáticos; es, en, pt); 429 con reintento. **No probado contra YouTube real**: `c-salud/mantenimiento/probar_real.py`.

## Dónde estaba el código viejo
Rutas relativas a `3-mando/c-referencia/ingestion/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/ingestion/youtube_playlist.py`
- `app/ingestion/playlist_watcher.py`
- `app/tools/ingestion.py`

## Notas
Tools: youtube_ingest_video, youtube_ingest_playlist.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código está en `b-codigo/src/`; sus tests en `c-salud/pruebas/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\ingestion\`.
