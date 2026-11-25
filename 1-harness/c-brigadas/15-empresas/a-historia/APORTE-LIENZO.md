# Aporte de la pieza 15 para `LIENZO-DAMIAN.md` y `ESTADO.md` (los integra el coordinador)

## Para LIENZO-DAMIAN.md: Cobros de Empresas
| Qué hace falta | Dónde se saca | Dónde se pega | Qué se prueba después |
| --- | --- | --- | --- |
| Datos de la cuenta de la dueña: alias, CBU/CVU, titular, banco | Los tiene la dueña | Config de la instalación: `brigades.empresas.config.payments` (`alias`, `cbu`, `holder`, `bank`) o `perfil-clienta` | Mandar un presupuesto de prueba y ver que el mensaje trae los datos; "ya transferí" deja la confirmación a la dueña |
| `MP_ACCESS_TOKEN` (de prueba primero) | mercadopago.com.ar/developers > Tus integraciones > Credenciales | `raphael.env` (plantilla: `15-empresas/b-codigo/empresas.env.plantilla`) | Poner `payments.mercadopago.mode: real`; presupuesto de prueba: la dueña recibe "mandar link de pago"; pagar con usuario de prueba |
| `MP_WEBHOOK_SECRET` | Tu aplicación > Webhooks > Clave secreta | `raphael.env` | Pago de prueba: llega el aviso y queda "Mercado Pago acreditó…" para confirmar |
| URL de avisos (`payments.mercadopago.notification_url`) | `https://<servidor>/webhook/mercadopago` | Config de la instalación; la misma URL en Webhooks (evento "Pagos") de la app de Mercado Pago | Igual que arriba |
Para andar sin cuenta: `payments.mercadopago.mode: mock` (links de mentira, circuito completo).

## Para ESTADO.md (cuando se cierre el hilo)
Cobros de Empresas: Mercado Pago (adaptador real + simulado) y transferencia con datos de cuenta; la dueña confirma siempre. Brigada: 137 tests, puerta 863 en verde (25 nov). No probado contra Mercado Pago real.

## Pendiente para la pieza 3 (Servidor)
Falta el endpoint `POST /webhook/mercadopago` en la API: debe llamar al comando `empresas/cobros/mp_aviso` con `{payment_id: <data.id del query>, headers: {x-signature, x-request-id}, query: {data.id}}` y responder 200 rápido (Mercado Pago reintenta si tarda más de ~22 s). Sumar las dos claves nuevas al chequeo de arranque y a `QUE-CARGAR.md`.
