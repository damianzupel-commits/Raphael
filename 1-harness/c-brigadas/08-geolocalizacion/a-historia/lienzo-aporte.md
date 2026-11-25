# Aporte al lienzo de Damián · pieza 08 Geolocalización
(Para que el coordinador lo sume a `3-mando/a-conocimiento/LIENZO-DAMIAN.md`.) Todo es opcional: sin claves andan IPs, cripto y las capas libres.

| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| `SHODAN_KEY` | https://account.shodan.io (la búsqueda por API necesita cuenta paga o créditos) | variable de entorno / `raphael.env`, ver `1-harness/c-brigadas/08-geolocalizacion/b-codigo/geolocalizacion.env.plantilla` | «shodan: product:nginx country:AR» → queda pendiente → aprobar → pines en el globo |
| `AISSTREAM_KEY` + `pip install websockets` | https://aisstream.io (gratis) | ídem | «barcos» → muestra de 8 s del stream |
| `FIRMS_MAP_KEY` | https://firms.modaps.eosdis.nasa.gov/api/map_key (gratis) | ídem | «incendios» |
| `WINDY_WEBCAMS_KEY` | https://api.windy.com/keys (gratis) | ídem | «cámaras» |
| `OPENWEATHER_KEY` | https://home.openweathermap.org/api_keys (gratis) | ídem | «clima» |
| `OPENCELLID_KEY` + `OPENCELLID_BBOX` | https://opencellid.org (gratis); bbox = lat_sur,lon_oeste,lat_norte,lon_este | ídem | «antenas» |
| `RAPHAEL_GEO_MODO=simulado` (opcional) | no es una clave | ídem | ver el globo con datos de muestra |

Probar todo sin claves ya: poner el modo simulado. Sin ninguna clave y en modo real, cada capa con clave dice cuál falta.
Decisión pendiente: ip-api.com gratis solo usa HTTP (sin cifrar); si querés cifrado hace falta otro proveedor o plan.
