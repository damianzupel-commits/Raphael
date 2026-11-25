# raphael-contenido · Brigada Contenido (harness v2)

Video, imágenes, Instagram, copys y calendario, campañas y analítica. Se monta en el harness v2 (`raphael-core`, contrato 2.1) por su `manifest.yaml`. Solo importa `raphael_core` y la stdlib (más pydantic y pyyaml): ninguna otra brigada. Publicar, subir o activar anuncios y grabar la pantalla siempre piden aprobación.

## Cocineros
| Id | Qué hace | Acciones (nivel) |
|---|---|---|
| `video` | ffmpeg con carpeta fija y original intacto; editor de proyectos con línea de tiempo; Whisper para transcribir | `editar_video`, `proyecto_crear`, `proyecto_editar`, `proyecto_renderizar` (automático) · `grabar_pantalla` (aprobación, solo edición personal) |
| `instagram` | Deja el video con su texto como PENDIENTE (huella SHA-256) y publica un Reel solo tras la aprobación | `preparar_publicacion`, `descartar_publicacion` (automático) · `publicar_instagram` (aprobación, externo, irreversible) |
| `imagen` | Flux.1 Schnell (imagen) y Wan 2.2 (video) con ComfyUI en la GPU de la PC; copia lo generado a `entrada/` | `generar_imagen`, `generar_video` (automático) |
| `contenido` | Copys, guiones, carruseles y calendario editorial con el tono de la marca; sin modelo usa plantillas y lo avisa | `redactar_copy`, `agendar_post`, `quitar_del_calendario` (automático) |
| `campanas` | Borradores de anuncios con presupuesto (tope en la config) y segmentación | `crear_borrador_anuncio`, `descartar_borrador` (automático) · `subir_campana_pausada` (aprobación) · `activar_campana` (aprobación, GASTA) |
| `analitica` | Métricas de Instagram y recomendaciones por reglas, con la cantidad de datos a la vista | `sincronizar_metricas` (automático, solo lee) |

Los trabajos pesados (render, ComfyUI, subir un Reel) se encolan y corren de a uno en un hilo aparte; el estado se ve con el comando `trabajos` y el `tick` publica el evento al terminar.

## Eventos
Publica: `video.listo`, `imagen.lista`, `publicacion.preparada`, `publicacion.publicada`, `copy.listo`, `campana.borrador`, `campana.activada`, `metricas.sincronizadas`, `contenido.trabajo_fallido` y **`revision.pedida`** (antes de publicar un texto, para que Legales lo revise). Consume `pendiente.rechazado`.
No recibe mensajes de clientes, así que no publica `consentimiento.recibido` ni `baja.solicitada` (los emite quien reciba los opt-in y las bajas, hoy Empresas).

## Adaptadores (real, simulado y "sin clave")
Cada cosa que es de la persona tiene tres adaptadores (`src/raphael_contenido/adapters/`, `entorno.py`):
- **real**: lee su clave del entorno (lista y para qué sirve cada una en `.env.plantilla`);
- **simulado**: `mode: mock` en la config o `CONTENIDO_MODO=mock`; los resultados llevan `simulado: true` y los mensajes lo dicen. Los tests corren con este;
- **sin clave**: el real al que le falta una variable: avisa cuál, el resto de la brigada anda, y nada se inventa (una publicación sin clave queda pendiente).

| Servicio | Variables | Probado |
|---|---|---|
| Instagram (publicar Reels, métricas) | `IG_USER_ID`, `IG_ACCESS_TOKEN`, `IG_GRAPH_VERSION` | solo con HTTP falso; falta cuenta real |
| Anuncios (Meta Ads) | `META_ADS_ACCOUNT_ID`, `META_ADS_ACCESS_TOKEN` | solo con HTTP falso; crea SOLO la campaña, en pausa |
| ComfyUI | `COMFYUI_URL`, `COMFYUI_OUTPUT_DIR` | solo con HTTP falso; falta la GPU de la PC |
| ffmpeg / Whisper | `VIDEO_FFMPEG_PATH`, `VIDEO_EDIT_DIR`, `VIDEO_WHISPER_MODEL`… | ffmpeg real probado en la nube (ediciones y render); Whisper no |

## Config
En `installation.brigades.contenido.config` (ver `config.py`): `mode`, `brand` (nombre, tono, público, temas, hashtags, palabras a evitar), `video.dir`, `instagram`, `campaigns` (moneda, tope de presupuesto diario) y `analytics`.

## Probar
```
cd ..\c-salud\pruebas
python -m pytest              # usa src\ y raphael-core del proyecto (o RAPHAEL_CORE_SRC)
python ..\..\b-codigo\scripts\sync_manifest.py   # si cambiás el manifiesto del paquete
```
Los tests de las ediciones portadas usan ffmpeg real si está instalado y se saltean si no.
