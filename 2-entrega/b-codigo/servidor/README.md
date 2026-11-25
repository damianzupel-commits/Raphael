# 2-entrega/b-codigo/servidor

Servidor FastAPI de cada instalación: panel web, login, webhook de Meta (`/webhook/meta`), licencia, copias de seguridad y avisos.

## Cómo debe funcionar
- Una instalación por cliente: usuario del sistema, carpeta, base, claves y dominio propios.
- Sin `OPENROUTER_API_KEY` (u otro proveedor) cae a reglas y lo avisa. Las claves las carga Damián en el servidor; nunca pasan por un chat.
- Corre detrás de Caddy con HTTPS (Meta lo exige).

## Código existente
`raphael\3-mando\c-referencia\servidor-app-installer\raphael-empresas\raphael-servidor` (0.4.0, 28 tests; incluye `tienda.py`, conectores, seguridad y servicios). Pieza dueña: chat 3.

## API nueva de Empresas (chat 15)
En `api/`: FastAPI (`raphael-empresas-api`) que expone la brigada Empresas a la app, con el canal de Meta (`meta.py`: webhook de WhatsApp e Instagram con firma, envío por la Graph API v26.0, ventana de 24 h con aviso a la dueña, sin duplicar reintentos, modo `mock` por defecto). 33 tests. Ver `api/API.md`. **No probado contra Meta real**: faltan las cuentas (pieza 04). Pendiente de la pieza 03: adoptarla y montarla en el VPS.

## Raphael personal, cliente-servidor (pieza 3, 25 nov)
En `api/src/raphael_personal_api/` (mismo paquete `raphael-empresas-api`, otro módulo): servidor de Raphael personal sobre el orquestador en modo `master`. Cerebro mixto (lo privado solo en local, el resto NVIDIA, roles cambiables por configuración), API de charla, aprobaciones, estado del cerebro, configuración y voz, y una página web que sirve de cliente. Instalación y arranque con Windows en `2-entrega/c-despliegue/personal/` (ver su `LEEME.md`). Tests en `api/tests/test_personal.py`.
