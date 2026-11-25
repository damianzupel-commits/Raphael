# Aplicar arreglo (gate y guardarraíl)

- **Brigada:** 13-autorreparacion · Autorreparación (chat 13)
- **Tipo:** existente
- **Qué hace:** Aplica arreglos con compuerta y guardarraíl.

## Código nuevo (harness v2, 25 nov 2026)
`b-codigo/src/raphael_selfrepair/cooks/apply.py` (cocinero `aplicar`), `guardrail.py`, `fixer.py`. Tests en `c-salud/pruebas/`. Lo de abajo es el origen portado.

## Dónde está el código actual
Rutas relativas a `3-mando/c-referencia/self-repair/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/selfrepair/gate.py`
- `app/selfrepair/guardrail.py`
- `app/codeedit/`
- `app/tools/code_edit.py`

## Notas
Tool: code_apply_fix.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\self-repair\`.
