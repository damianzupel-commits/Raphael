# Navegador y web

- **Brigada:** 12-operaciones · Operaciones (chat 12)
- **Tipo:** existente
- **Qué hace:** Abre el navegador y trae páginas.

## Dónde está el código actual
Rutas relativas a `_reference/operations/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/tools/browser.py`
- `app/tools/web_get.py`

## Notas
Tools: browser_open, web_get.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\_reference\operations\`.
