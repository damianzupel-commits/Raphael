# Vigilancia de tendencias

- **Brigada:** 07-investigacion · Investigación (chat 7)
- **Tipo:** nuevo
- **Qué hace:** Sigue los temas que el cliente define y avisa cuando hay algo relevante, con resumen y fuentes.

## Dónde está el código actual
Rutas relativas a `3-mando/c-referencia/research/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- (sin código previo)

## Notas
Nuevo, sobre los bucles proactivos.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\research\`.
