# Geolocalización pública · monitoreo
- Healthcheck: `raphael_geolocalizacion.health:check` (declarado en el manifiesto). Da mal solo con config inválida (`modo`, `pines_max`). Que falte una clave o que una fuente no responda NO es salud mala: el cocinero avisa y sigue. En modo simulado el detalle lo dice ("SIMULADO").
- Comando `fuentes`: modo y qué claves están cargadas (sin valores).
- Alertas: un pendiente de `buscar_shodan` o `borrar_pines` espera a Damián en el panel.
- Si una capa sale vacía con aviso "No pude leer…": la fuente pública cayó o limitó (OpenSky anónimo y ip-api tienen límites). Se reintenta sola al pedir de nuevo (caché 10 s a 1 día según la capa).
