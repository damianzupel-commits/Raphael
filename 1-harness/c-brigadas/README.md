# Harness · c-brigadas
Las brigadas que se montan sobre el harness. El número es el del chat de cada pieza.

- `00-orquestador`: Orquestador (el que habla con la persona y reparte)
- `05-seguridad`: Seguridad
- `06-antimalware`: Antimalware
- `07-investigacion`: Investigación
- `08-geolocalizacion`: Geolocalización pública
- `09-memoria`: Memoria · Cerebro
- `10-ingesta`: Ingesta
- `11-trading`: Trading
- `12-operaciones`: Operaciones
- `13-autorreparacion`: Autorreparación
- `14-contenido`: Contenido
- `15-empresas`: Raphael Empresas
- `16-legales`: Legales

Cada brigada repite el patrón a/b/c: `a-historia/` (saber), `b-codigo/` (hacer, con `manifest.yaml`) y `c-salud/` con tres carpetas (`pruebas/`, `monitoreo/`, `mantenimiento/`). El harness las encuentra buscando `manifest.yaml`; hoy solo `15-empresas` tiene código.
