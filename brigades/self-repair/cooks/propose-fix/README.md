# Proponer arreglo

- **Brigada:** 13-autorreparacion · Autorreparación (chat 13)
- **Tipo:** existente
- **Qué hace:** Propone arreglos al código.

## Dónde está el código actual
Rutas relativas a `_reference/self-repair/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/selfrepair/propose.py`
- `app/selfrepair/models.py`
- `app/selfrepair/store.py`
- `app/tools/selfrepair.py`

## Notas
Tool: selfrepair_propose_fix.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\_reference\self-repair\`.
