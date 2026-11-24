# Consolidador y destilador

- **Brigada:** 09-memoria · Memoria · Cerebro (chat 9)
- **Tipo:** existente
- **Qué hace:** Consolida memoria y destila lo capturado.

## Dónde está el código actual
Rutas relativas a `3-mando/c-referencia/memory/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/obsidian/consolidation.py`
- `app/memory/capture.py`
- `app/memory/distiller.py`
- `app/memory/classifier.py`
- `app/memory/recall.py`
- `app/memory/store.py`
- `brigades/memory_service.py`

## Notas
Tool: memoria_consolidar. Agrupación propuesta según nombres de archivo.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\memory\`.
