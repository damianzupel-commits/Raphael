# Recuperador

- **Brigada:** 09-memoria-cerebro · Memoria · Cerebro (chat 9)
- **Tipo:** existente
- **Qué hace:** Recupera del vault la evidencia de una consulta (asociativo y por palabra clave): notas fuente con su extracto textual. Solo lectura.

## Dónde está el código actual
Rutas relativas a `_reference/memory/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `brigades/cerebro.py`

## Notas
Ayudante recuperador. Es el único ayudante declarado; todo pedido va a él.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\_reference\memory\`.
