# raphael-geolocalizacion · Brigada Geolocalización pública (harness v2)

OSINT de infraestructura con fuentes públicas. Solo infraestructura: nada de ubicar personas. Se monta por `manifest.yaml` (la fuente de verdad); solo importa `raphael_core` y la stdlib (`websockets` es opcional, solo para barcos).

- `src/raphael_geolocalizacion/cooks/`: `ip_infra`, `cripto`, `capas`.
- `src/raphael_geolocalizacion/fuentes/`: `base.py` (qué pedir y cómo leerlo), `real.py` (internet, caché, fail-soft) y `simulado.py` (datos de muestra con el mismo formato que las APIs).
- `pines.py` (pines del globo, tope 500), `validar.py` (coordenadas, IPs públicas, cripto, texto de terceros), `claves.py` (variables de entorno), `health.py`.
- `geolocalizacion.env.plantilla`: todas las claves opcionales, vacías. Nunca se escribe una clave real en el repo.

Config (`installation.brigades.geolocalizacion.config`): `modo` (`real` | `simulado`), `pines_max` (10 a 5000).
Si cambiás el manifiesto del paquete: `python scripts/sync_manifest.py` (el de la raíz es la copia que encuentra el cargador).
Probar: `cd ../c-salud/pruebas && python -m pytest`.
