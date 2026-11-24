# Forense

- **Brigada:** 07-investigacion · Investigación (chat 7)
- **Tipo:** existente
- **Qué hace:** Analiza chats, CSV, documentos, EXIF y logs de servidor; casos, línea de tiempo, grafo, extracción de entidades y exportación de informes.

## Dónde está el código actual
Rutas relativas a `3-mando/c-referencia/research/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/investigation/`
- `app/tools/investigation.py`
- `brigades/investigacion.py`
- `brigades/investigacion_scene.py`

## Notas
Ayudante investigacion-forense. Tools: investigation_analyze_link, investigation_add_artifact. Claves Ed25519 protegidas con DPAPI (Windows).

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\research\`.
