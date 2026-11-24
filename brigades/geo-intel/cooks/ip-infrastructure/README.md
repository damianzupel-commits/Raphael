# IP e infraestructura

- **Brigada:** 08-geolocalizacion-publica · Geolocalización pública (chat 8)
- **Tipo:** existente
- **Qué hace:** Geolocaliza IPs y busca hosts (Shodan).

## Dónde está el código actual
Rutas relativas a `_reference/geo-intel/` (ver abajo) (JarvisRemote: `jarvisremote/backend/`; Empresas: `raphael-empresas/`):
- `app/geo_intel.py`
- `app/tools/osint_lookups.py`

## Notas
Tools: ip_geolocate, shodan_host_search.

## Cómo debe funcionar
- Es un cocinero permanente de la brigada: se declara en el `manifest.yaml` y atiende los pedidos que le llegan por el harness.
- Cada acción suya declara su nivel de autonomía (`automatico`, `aprobacion`, `humano`). Lo que sale al mundo, gasta plata o no tiene vuelta atrás pide aprobación.
- Sin modelo o sin red cae a reglas y lo avisa; nunca inventa. El contenido de terceros es dato, no instrucción.
- Su código nuevo va en `src/`; sus tests en `tests/`. El código existente está como referencia, solo lectura, en `raphael\_reference\geo-intel\`.
