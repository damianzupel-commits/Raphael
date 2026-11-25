# Registro · 14-contenido · Contenido

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Portada al harness v2 (hilo "Construir pieza 14 Contenido")
**Resumen de cierre**
- Portado desde `3-mando/c-referencia/content/`: `video_edit` y `video_proyecto` (casi tal cual, con ffmpeg y Whisper inyectables), `publicaciones` (Instagram: preparar con huella y publicar tras aprobar), `image_gen`/`video_gen`/`_comfyui_shared` (ComfyUI). Los modos con ayudantes pasaron a acciones de cocineros; los 12 tests portados de proyecto pasan, con ffmpeg real.
- Nuevos: cocineros `contenido` (copys, guiones, carruseles, calendario; sin modelo cae a plantillas y lo avisa, no inventa), `campanas` (borrador → subir en pausa → activar, las dos últimas con aprobación; activar gasta y nunca baja a automático) y `analitica` (métricas y recomendaciones por reglas con la cantidad de datos a la vista).
- Todo lo que necesita algo de Damián es enchufable: adaptador real, simulado y "sin clave" por servicio; `.env.plantilla` con las variables. 54 tests en verde (contrato en personal y cloud, ningún import ajeno, plantilla completa, nada con efecto en automático); `ruff` limpio.
- Pedido de Legales (pieza 16): se publica `revision.pedida` al preparar y al publicar un texto. Contenido no recibe mensajes, así que `consentimiento.recibido` y `baja.solicitada` no los emite.
- Decidido: los trabajos pesados se encolan y corren de a uno (el guard del harness corta a los 60 s); `grabar_pantalla` falla cerrado fuera de la edición personal.
**Pendiente**
- Probar contra Instagram, Meta Ads (solo crea la campaña en pausa; el conjunto de anuncios y el anuncio se arman a mano con `exportar`) y ComfyUI reales; los nombres de métricas de Meta son supuestos.
- Sin portar: arranque/cierre automático de ComfyUI y descarga de VRAM de Ollama; `video_frames` (extraer cuadros para modelos con visión); `recording` (grabación por sesión, solo Windows); fotos y carruseles en Instagram (hoy solo Reels); Whisper sin probar.
- Pendiente para Orquestador: ruteo y confirmación de las acciones de esta brigada (señales en el manifiesto). Pendiente para Servidor/Cuentas: cargar `IG_*`/`META_ADS_*` en `raphael.env`.
