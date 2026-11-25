# Registro · 15-empresas · Raphael Empresas

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

## 24 nov 2026 · Resumen de cierre · preparación de la entrevista a la clienta
- Creado `INTERVIEW.md` (raíz de esta rama): preguntas por módulo con el supuesto actual y una columna de respuesta; las ★ bloquean la entrega.
- Creado `a-historia/perfil-clienta.borrador.yaml`: perfil con cada dato marcado SUPUESTO o FALTA. No se cargaron los precios ni los datos del piloto como si fueran de ella. No se validó contra el esquema ni se corrieron tests (solo documentos).
- Revisión de alcance de Tienda (INTERVIEW §9): se mantiene solo lectura; se supone que no tiene tienda web (`kind: none`) hasta que responda 6.1; los tres adaptadores de plataforma siguen sin probarse contra tiendas reales.
- No se ajustó ningún módulo: sin respuestas serían inventos. Los ajustes posibles y de qué pregunta dependen están en INTERVIEW §10.
- Pendiente: que Damián haga la entrevista y anote las respuestas; después, cargar el perfil real y ajustar módulos. Tema para Legales (16): factura/monotributo y qué datos de clientas se guardan (Ley 25.326, a verificar con fuente vigente).

## 25 nov 2026 · Resumen de cierre · cobros (Mercado Pago y transferencia)
- Nuevo `pay/` (proveedor de pagos con adaptador real de Mercado Pago y uno simulado) y cobros con dos vías: transferencia (alias, CBU, titular y banco en la config; la dueña confirma a mano) y Mercado Pago (`payments.mercadopago.mode`: off, mock o real). Con Mercado Pago activo, al enviarse el presupuesto se crea el link y la dueña aprueba mandarlo (`enviar_link_pago`, nueva acción `aprobacion`); cuando Mercado Pago avisa el pago (`mp_aviso`) se verifica la firma, se lee el pago y se deja `confirmar_pago` pendiente: nunca se confirma solo.
- Sin token en modo real cae a transferencia y lo dice (`mp_estado`). El token nunca se loguea. 13 tests nuevos: brigada 137, puerta 863 en verde, ruff limpio.
- **Sin verificar contra la documentación (no se pudo leer):** el texto que se firma en el webhook, los campos exactos de la preferencia (`init_point`, `back_urls`, etc.). Están marcados en `pay/mercadopago.py` y hay que probarlos con una cuenta de prueba antes de cobrar.
- IA de Empresas: sigue por OpenRouter vía el harness (sin cambios); sin clave, reglas.
- Pendiente para 03: el endpoint `/webhook/mercadopago` en la API y las claves nuevas en el chequeo. Lo que va al lienzo y a ESTADO está en `APORTE-LIENZO.md`.

## 25 nov 2026 · Resumen de cierre · eventos hacia Legales (pedido del coordinador, pieza 16)
- Nuevo `legal.py` y tres eventos publicados (declarados en el manifiesto, sin importar ninguna brigada): `revision.pedida` {text, ref} antes de mandar presupuesto, cancelación, link de pago, aviso de estado y respuestas de la dueña; `consentimiento.recibido` {contact, purpose, channel, evidence} cuando un cliente acepta recibir avisos; `baja.solicitada` {contact, channel} cuando pide la baja.
- La baja le gana a cualquier conversación abierta (encargo, turno): los cocineros se la pasan a Atención. La revisión es solo un aviso, no frena el envío. Las frases de alta y baja son reglas simples (`legal.py`): hay que revisarlas con la clienta. Brigada 141 tests, puerta 867 en verde.
- 25 nov (misma sesión): las claves de Mercado Pago pasan a `MP_ACCESS_TOKEN` y `MP_WEBHOOK_SECRET` (el nombre del catálogo de cuentas y del servidor, para que Damián cargue uno solo); `MERCADOPAGO_*` sigue andando como alias.
