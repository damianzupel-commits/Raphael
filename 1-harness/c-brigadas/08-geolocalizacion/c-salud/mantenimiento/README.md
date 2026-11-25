# Geolocalización pública · mantenimiento
- Cambiar el manifiesto: editar el del paquete y correr `b-codigo/scripts/sync_manifest.py`.
- Las URLs y formatos de las APIs públicas viven en `fuentes/base.py` y las respuestas de muestra en `fuentes/simulado.py`: si una fuente cambia su formato, se actualizan las dos y el test de esa capa lo cubre.
- Pendiente: probar cada fuente real con internet (nadie lo hizo todavía) y verificar los límites actuales de ip-api, OpenSky y GDELT.
