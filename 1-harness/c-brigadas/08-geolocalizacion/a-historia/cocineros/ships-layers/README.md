# Barcos y capas del globo

- **Brigada:** 08-geolocalizacion · Geolocalización pública (chat 8)
- **Tipo:** existente
- **Qué hace:** Capas del mapa y seguimiento de barcos.

## Dónde está el código actual
Rutas relativas a `3-mando/c-referencia/geo-intel/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/geo_ships.py`
- `app/geo_layers.py`

## Notas
Agrupación propuesta según nombres de archivo.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\3-mando\c-referencia\geo-intel\`.
