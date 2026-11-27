# Raphael Seguridad: videos de IA y ciberseguridad

Pipeline para producir videos verticales (1080x1920, 45-90 s, español) sobre casos reales de IA y ciberseguridad.

- `GUIONES.md`: los 20 guiones (gancho, caso, problema, solución, texto en pantalla, descripción, hashtags y fuentes).
- `casos.json`: los mismos datos, en formato máquina (por ejemplo, para que la pieza 14 Contenido los programe).
- `pipeline/casos_1.py`, `casos_2.py`: el contenido fuente de los guiones.
- `pipeline/build.py`: genera los MP4 con voz TTS, subtítulos y texto en pantalla. Requiere `ffmpeg`, `espeak-ng` y `Pillow`.
- `pipeline/docs.py`: regenera `GUIONES.md` y `casos.json`.

## Generar los videos

```
python3 pipeline/build.py salida/        # los 20
python3 pipeline/build.py salida/ 2 5    # solo los casos 2 y 5
```

La voz por defecto es `espeak-ng` (`es-419`): es robótica y sirve de borrador. Para publicar conviene reemplazarla por una voz natural (por ejemplo, grabar vos la narración o usar un TTS de calidad) y reutilizar los `.srt` que se generan junto a cada video. El texto de cada narración está en `GUIONES.md`.

## Reglas
- Nada se publica sin aprobación de Damian.
- Solo casos reales con fuente. Si agregás un caso, incluí fuentes y no inventes cifras.
- Verificación: los casos 5, 17 y 18 se contrastaron con la página primaria (Anthropic, Google). El resto se redactó a partir de los medios y reportes enlazados; conviene que alguien lea la fuente antes de publicar.
