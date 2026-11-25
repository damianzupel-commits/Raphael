# Registro · 08-geolocalizacion · Geolocalización pública

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 2026-11-25 · hilo "Construir pieza 08 Geolocalización"
**Resumen de cierre.**
- Se portó la brigada al harness v2 (`geolocalizacion` 1.0.0, edición personal): cocineros `ip-infra`, `cripto` y `capas`; acciones `buscar_shodan` (aprobación, spend+external) y `borrar_pines` (aprobación, irreversible); 6 comandos de lectura; evento `pin.agregado`; health y setup que validan la config.
- Fuentes enchufables: `FuentesReales` (urllib, caché, fail-soft) y `FuentesSimuladas` (mismas respuestas que las APIs, marcadas como muestra). Claves solo por variable de entorno (`geolocalizacion.env.plantilla`); sin clave la capa avisa cuál falta y no inventa. IPs privadas rechazadas; el texto de terceros se limpia y es dato.
- 88 tests y suite de contrato en verde, ruff limpio, todo sin red. **No probado con internet ni con claves reales.**
- Se simplificó: no se portaron las tools con `register_tool` (no hay jefe ni efímeros todavía) ni el stream AIS permanente (ahora es una muestra de unos segundos por pedido).
- Pendiente para el coordinador: sumar la suite `geolocalizacion` a `gate.py`, el aporte de `a-historia/lienzo-aporte.md` al lienzo y la línea en `ESTADO.md`. Pendiente para el Centro de Mando/Servidor: dibujar los pines (`pin.agregado`, comando `pines`) y las capas en el globo.
