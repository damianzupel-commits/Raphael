# Registro · 15-raphael-empresas · Raphael Empresas

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 22 nov 2026 · Resumen de cierre · E1 a E5 + app
- Brigada Empresas nativa del harness v2 en `codigo\raphael-empresas` (2.0.0): 7 cocineros (atención, encargos, cobros, agenda, avisos, tareas, tienda), manifiesto con nivel y etiquetas en cada acción, config del negocio validada y conversor del perfil 0.4. **116 tests en verde** (los 74 de Empresas 0.4 portados nativos + 42 nuevos), Python 3.12 y 3.13, ruff limpio; la regresión vieja sobre el puente sigue en 74.
- Instalación de la clienta lista para el VPS (`codigo\instalacion`): harness + orquestador `secretary` + esta brigada, arranque (`raphael_empresas.boot.start`) y prueba de humo. Arranca limpia (decidido). Los datos son los del piloto: falta pasar su `perfil.yaml` real por `perfil_a_instalacion.py`.
- Nuevo pedido de Damián: app Android nativa (`codigo\android`, Kotlin + Compose) y su API (`codigo\raphael-empresas-api`, FastAPI, 9 tests). El APK de debug compila y el cliente Kotlin pasa un test de contrato contra la API real. **No probada en un teléfono.**
- Decidido al construir: cocinero `tareas` único para `owner_tasks` (la Secretaria del 02 usa el primer cocinero que responde), registros del negocio en `ctx.shared`, reclamo primero resuelto adentro de la brigada.
- Pendientes anotados en DISENO.md §9 para 02, 03 (montar la API y los webhooks en el VPS, push, `tienda.py`), 00 y 04. En la PC no se corrió pytest (la VM tiene Python 3.10); los 109 archivos copiados verificados por md5. Quedan para borrar a mano `obra\tmp-15\` (paquetes de copia).

## 23 nov 2026 · Resumen de cierre · segunda tanda ("construye todo lo que puedas")
- Canal de Meta en `codigo\raphael-empresas-api` (`meta.py`): webhook de WhatsApp e Instagram con firma, envío por la Graph API v26.0 en hilo aparte, ventana de 24 h con aviso a la dueña, sin duplicar reintentos, modo `mock` por defecto. Fuentes de Meta revisadas el 23 nov; **no probado contra Meta real** (faltan las cuentas, 04).
- Kit del VPS en `codigo\despliegue` (instalar con systemd y Caddy, actualizar con vuelta atrás, copia diaria de la base, `armar_paquete.py`): probado en modo "solo archivos" con el servicio andando de punta a punta; **no probado en un VPS real** y el Caddyfile sin validar.
- Tienda: adaptadores Tiendanube, Shopify (GraphQL) y WooCommerce, de solo lectura, tokens por variable de entorno (cambia la decisión de dejarlos para después: Damián pidió construir todo). App 1.1.0: avisos, estado de los canales, notificación por avisos, refresco cada 30 s.
- Tests: brigada 124, API 26, núcleo 405 y orquestador 266 sin cambios, regresión vieja 74; app con lint en 0 errores, 7 tests de modelos y el de contrato contra la API real. Ruff limpio.
- Pendientes en DISENO.md §10 (03 adopta el kit y el canal; 04 las cuentas de Meta; Damián el token de la tienda si la clienta usa una plataforma).
