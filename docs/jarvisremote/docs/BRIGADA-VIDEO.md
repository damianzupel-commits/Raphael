# Brigada de Video (edición por pedido)

Edita video por instrucciones («recortá del 1:00 al 2:30», «uní estos dos con fundido y poné un título», «sacame tres clips
para redes»). Es el spec `backend/brigades/video.py` ejecutado por el motor genérico (ver `PLAYBOOK-brigadas.md`); las tools
están en `backend/app/tools/video_edit.py` y el núcleo en `backend/app/video_edit.py`, sobre **ffmpeg** y **Whisper local**.

No es un editor con línea de tiempo: no hay vista previa ni arrastre de clips. Cada operación genera un archivo nuevo.

## Decisiones de Damian

- **Carpeta fija.** Solo trabaja en `Documentos\Videos-Raphael` (`VIDEO_EDIT_DIR` la cambia): los videos van en `entrada\` y los
  resultados salen en `salida\`. Una ruta que salga de ahí (absoluta, `..`, enlace simbólico) se rechaza.
- **El original nunca se modifica.** Toda operación escribe un archivo nuevo con nombre único; nada se pisa ni se borra.

Las dos reglas las hace cumplir el núcleo, no un prompt: ffmpeg corre con `-n` (si el destino existiera, falla) y toda ruta
se resuelve y se comprueba antes de abrirla.

## Qué sabe hacer

| Ayudante | Para qué | Tools |
|---|---|---|
| `montaje` | Recortar, unir, transiciones, velocidad, convertir, quitar silencios, girar, fundidos, reversa, GIF, capturas | `video_recortar`, `video_unir`, `video_transicion`, `video_velocidad`, `video_convertir`, `video_quitar_silencios`, `video_rotar`, `video_fundidos`, `video_reversa`, `video_gif`, `video_captura`, `video_escenas` |
| `imagen` | Color y filtros, títulos, logo o video superpuesto, zoom, estabilizar, pantalla verde, vertical | `video_color`, `video_texto`, `video_superponer`, `video_encuadrar`, `video_estabilizar`, `video_pantalla_verde`, `video_vertical` |
| `sonido` | Normalizar volumen, reducir ruido, música de fondo, extraer el audio | `video_audio`, `video_convertir` |
| `subtitulos` | Transcribir (Whisper en esta PC) y subtitular, quemado o como pista | `video_transcribir`, `video_subtitular` |
| `clips` | Clips verticales para redes, eligiendo los tramos por lo que se dice | `video_transcribir`, `video_escenas`, `video_recortar`, `video_vertical`, `video_subtitular` |
| `info` (por defecto) | Pasivo: lista y lee. No edita | `video_listar`, `video_info`, `video_escenas` |

Todos tienen además `video_listar` y `video_info`. Ninguno tiene shell, filesystem, red ni navegador.

Un pedido que encadena oficios («recortá y después subtitulá») lo planifica el jefe en orden: cada ayudante trabaja sobre el
archivo que dejó el anterior.

## Cómo se usa

- Pestaña **Video** del orquestador, o `/video <pedido>` desde cualquier lado.
- En la pestaña Orquestador, un pedido con un verbo de edición **y** un video («subtitulá charla.mp4») va solo a Video.
  «Buscá videos de Rust en la web» no tiene verbo de edición: va a Investigación.
- Video no entra todavía al trabajo conjunto con otras brigadas.

## Requisitos

- **ffmpeg** en esta PC: `winget install Gyan.FFmpeg`, o `pip install imageio-ffmpeg`, o su ruta en `VIDEO_FFMPEG_PATH`.
- Para transcribir: `pip install -r requirements-voice.txt` (faster-whisper, el mismo de la voz local).

## Carga de la PC

Recodificar video y transcribir usan la CPU al máximo durante minutos, y esta PC tiene antecedentes de apagarse bajo carga
sostenida. Por eso: un solo trabajo a la vez, pocos hilos (`VIDEO_FFMPEG_THREADS`, por defecto la mitad de los núcleos, máximo
4), prioridad baja del proceso, y las operaciones que pueden copian los streams sin recodificar (recortar rápido, unir clips
iguales, cambios de audio). Si la PC sufre, bajá `VIDEO_FFMPEG_THREADS` a 1 o 2.

## Validación

```powershell
cd backend
.venv\Scripts\python.exe -m validation.video
```

Cinco pasos, todos en una carpeta temporal: alcance y ruteo (sin modelo ni ffmpeg); carpeta fija y operaciones (con las tools
reales sobre un video sintético; sin ffmpeg quedan SIN VALIDAR); y un pedido en lenguaje natural (necesita el modelo).

## Límites honestos

- El corte rápido (sin recodificar) cae en el cuadro clave más cercano; `preciso=true` corta exacto pero recodifica.
- Los títulos usan la fuente Arial del sistema; no hay plantillas ni animaciones de texto más allá del fundido.
- «Mejores momentos» los elige el modelo leyendo la transcripción: no mira la imagen.
- La estabilización es básica (`deshake`), no la de un editor profesional.
- La reversa admite hasta 30 s y un GIF hasta 15 s.
- Probada solo con videos sintéticos chicos, en Linux. Falta probarla con videos reales en la PC de Damian.


## Editor de proyectos (línea de tiempo) — la IA y el usuario editan lo mismo

- **Proyecto** (`app/video_proyecto.py`): un JSON en `Videos-Raphael/proyectos/`. Cinco pistas: **V1** video (clips uno tras otro, con
  **transiciones** entre clips), **O1** capas (**imágenes, GIFs animados o videos superpuestos** donde quieras: centro `x`/`y`, `escala`, `opacidad`,
  `rotacion`, `pos`, `dur`, fundidos; pueden solaparse entre sí y con todo), **T1** textos, **A1** música/locución y **A2** efectos de sonido.
  Por clip de video: recorte, velocidad (0.25–4), volumen, brillo, contraste, saturación, zoom, desenfoque, nitidez, viñeta, espejo, giro 90°,
  filtros de color (bn, sepia, cálido, frío, vintage…) y fundidos. Transiciones (xfade): fundido, fundido a negro/blanco, disolver, deslizar ×4,
  limpiar, círculo, zoom, pixelar, radial; el clip que entra se solapa con el anterior y la duración total se recalcula. Formato vertical /
  horizontal / cuadrado. Los originales no se tocan: `renderizar` deja un archivo nuevo en `salida/` (un solo ffmpeg).
- **Efectos de sonido**: Raphael genera un pack propio **sintético** en `Videos-Raphael/efectos/` (ding, campana, pop, tic, whoosh, subida, caída,
  alerta; con ffmpeg, sin descargas ni copyright, nunca pisa archivos tuyos). Son sonidos simples: para efectos de estudio dejá los tuyos en `efectos/`.
- **No incluye** (todavía): keyframes/animación de capas en el tiempo, máscaras, chroma key, corrección de color por curvas, estabilización,
  subtítulos automáticos dentro del proyecto. No es un reemplazo de DaVinci/Premiere; sí cubre el armado típico de reels.
- **Una sola lista de operaciones** (`agregar_clip`, `agregar_overlay`, `agregar_texto`, `recortar`, `dividir`, `mover`, `borrar`, `ajustar`, `formato`, `renombrar`)
  que usan igual el panel y la IA (tools `video_proyecto_crear/ver/editar/renderizar`, ayudante `edicion`). Es **atómica** (si una falla no se aplica
  ninguna), lleva **número de revisión** (`rev_base`: si el otro cambió el proyecto, se rechaza y hay que releer), **deshacer/rehacer** y registra
  quién cambió (`usuario` o `ia`).
- **Panel** (pestaña Video): reproductor con vista previa liviana y **las capas dibujadas encima** (arrastrás para mover, la esquina cambia el tamaño),
  línea de tiempo de 5 pistas (arrastrar mueve, los bordes recortan, click elige; las transiciones se ven rayadas), parámetros del clip, biblioteca
  (imágenes/GIFs entran como capa en el cursor, 🔊 como efecto; ▣ manda un video como capa), dividir en el cursor, texto, deshacer/rehacer y render final. Consulta el proyecto cada 2 s: lo que hace la IA aparece
  solo. El pedido que se le escribe a la brigada viaja con el proyecto abierto, el clip elegido y el cursor.
- API: `/api/video/proyectos` (listar/crear/leer), `/ops`, `/deshacer`, `/rehacer`, `/render`, `/api/video/medios` y `/api/video/media/<archivo>`.

## Grabar pantalla y publicar en Instagram

- `video_grabar_pantalla`: ventana por título o escritorio completo (solo si se pide: puede mostrar claves), tiempo fijo, deja el video en `entrada/`.
- `video_preparar_publicacion`: deja la publicación **pendiente**. Ninguna tool publica: aprobar es `POST /api/publicaciones/{id}/aprobar` (acción del
  usuario). Necesita `IG_USER_ID` e `IG_ACCESS_TOKEN` en el `.env`; probado con un cliente simulado, falta la primera publicación real.
