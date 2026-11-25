# Registro · 12-operaciones · Operaciones

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Portar Operaciones al harness v2 (hilo "Construir pieza 12")
Resumen de cierre:
- Se portó la brigada completa desde `c-referencia/operations/`: 4 cocineros (`pc`, `phone`, `browser-web`, `supervisor`), jefe con 3 efímeros, 39 tools y 7 acciones con su nivel, healthcheck y paquete `raphael-operaciones`. 96 tests y ruff en verde; suite de contrato en verde. Solo edición personal.
- Todo lo que toca el mundo tiene adaptador real y simulado (por defecto simulado). El modo real tiene cada interruptor de riesgo apagado; lo que actúa pide aprobación. El modelo es **solo local** (decisión de Damián, 25 nov): sin modelo local el reporte sale degradado y no se manda nada a la nube (test).
- Cambios respecto de JarvisRemote: guarda de red local en `web_get` (también por redirección); `format` ya no bloquea cualquier texto con esa palabra; `killpg` en POSIX arrancaba el proceso sin sesión propia (podía matar al servidor); mover no pisa destinos; sin `web_credential_save` (las contraseñas pasan por variables, no por el modelo); capturas dentro del sandbox; el supervisor usa modelo local (antes Sonnet en la nube) y queda apagado por defecto.
- **No probado:** el escritorio real (Windows: pyautogui/pywinauto/pywin32), Playwright real, Scrapling, el celular real (la app Android) ni un modelo local real. Todo eso se prueba en la PC de Damián (pasos en el LIENZO).
- Límites conocidos: los guardarraíles de texto no son un sandbox; el supervisor no ve el pedido original (solo tool y argumentos); una acción ejecutada por un cocinero corre bajo el tope de 60 s del harness (los comandos largos van por el efímero); la guarda de red no cubre DNS rebinding.
- Pendiente para pieza 3 (servidor): endpoint `/ws/phone` y emparejamiento por QR usando `raphael_operaciones.adapters.phone.link` (ver README de b-codigo).
- Pendiente para el coordinador: ver el mensaje de cierre del hilo (`modelos.yaml`, `gate.py`, LIENZO, ESTADO).
