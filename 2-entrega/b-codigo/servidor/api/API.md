# API de Raphael Empresas · versión 1

La usa la app Android de la dueña (`..\android\`). Se para sobre la instalación de la clienta (harness v2 + orquestador en modo `secretary` + brigada `empresas`) y solo hace lo que la dueña podría hacer en el panel. Todas las decisiones pasan por el Policy Engine del harness: la API no ejecuta nada por su cuenta.

Hecha en la pieza 15 a pedido de Damián (22 nov 2026). Desde el 23 nov trae también el **canal de Meta** (webhook de WhatsApp e Instagram y envío por la Graph API, `meta.py`) y el kit del VPS está en `..\despliegue\`. **Pendiente para 03:** revisarlo y adoptarlo (o reemplazarlo por el servidor nuevo).

## Levantar
```
pip install -e .                      # con raphael-core, raphael-orchestrator y raphael-empresas instalados
raphael-empresas-api clave  --instalacion ..\instalacion\clienta.installation.yaml --datos datos
raphael-empresas-api servir --instalacion ..\instalacion\clienta.installation.yaml --datos datos --port 8787
```
- Escucha en `127.0.0.1` por defecto: el HTTPS lo pone Caddy adelante (`reverse_proxy 127.0.0.1:8787`).
- La **clave de la dueña se pone solo desde la consola del servidor** (`clave`), nunca por la API. Se guarda su hash (PBKDF2-SHA256 con sal) en la base de la instalación, espacio `_api`. Cambiarla cierra todas las sesiones.
- Corre el `tick` del harness cada 60 s (recordatorios de turnos, catálogo, salud).
- Un candado serializa las operaciones sobre el runtime (el harness y su SQLite no están pensados para escrituras en paralelo).

## Autenticación
`POST /api/v1/login {"key", "device"}` → `{"token", "user", "business"}`. Después, `Authorization: Bearer <token>` en todo.
- Token al azar de 32 bytes; se guarda solo su hash. Vence a los 90 días sin uso.
- 5 claves malas en 5 minutos desde la misma dirección → 15 minutos bloqueada (`429`).
- Sin clave puesta → `409`. Token inválido o vencido → `401`.

## Rutas
| Método y ruta | Qué hace |
|---|---|
| `GET /api/v1/health` | Sin sesión. `{ok, api, version, brigade, brigade_version, ready}` (`ready` = hay clave puesta) |
| `POST /api/v1/login` · `POST /api/v1/logout` | Sesión |
| `GET /api/v1/summary` | Negocio, pendientes (y cuántos humanos), estado de los cocineros, salud, avisos sin ver. Sin datos de clientes |
| `GET /api/v1/updates` | Para el aviso en segundo plano: `{pending, pending_human, latest, items[-5:], notices_unseen, notice_latest, notice_last}` |
| `GET /api/v1/pending` | Pendientes: `{id, type, level, summary, contact, created, data, editable, can}` |
| `POST /api/v1/pending/{id}/approve {"changes"}` | Solo nivel `aprobacion`. `changes` solo con los campos `editable` de ese tipo, validados: `price`/`amount` (número > 0), `date` (AAAA-MM-DD), `time` (HH:MM). Devuelve `{state, text}` (lo que se le mandó al cliente) |
| `POST /api/v1/pending/{id}/reject {"reason"}` | Rechaza (Cobros vuelve a esperar la seña, por ejemplo) |
| `POST /api/v1/pending/{id}/resolve {"reply"}` | Solo nivel `humano`. Con `reply`, le llega al cliente; vacío = resuelto sin escribirle |
| `POST /api/v1/secretary {"text", "session"}` | Charla con la Secretaria del orquestador: `{text, suggestions, tasks, card, meta.warnings}`. Las órdenes ("aprobá la 2") piden "¿Confirmo?" y se ejecutan solo con un "sí" |
| `GET /api/v1/orders?all=false` · `GET /api/v1/orders/{n}` | Encargos (en curso o todos) |
| `POST /api/v1/orders/{n}/status {"status"}` | `en_confeccion`, `prueba`, `listo`, `entregado` o `cancelado`. Avisos le escribe al cliente solo |
| `GET /api/v1/appointments` | Turnos confirmados desde hoy |
| `GET /api/v1/deposits` | Señas `waiting` (esperando) y `notified` (el cliente avisó que pagó) |
| `GET /api/v1/questions` | Preguntas que el bot no supo responder |
| `GET /api/v1/catalog?q=` | Estado del catálogo de la tienda y productos (hasta 200) |
| `GET /api/v1/conversation/{canal:id}` | Últimos 30 mensajes con ese contacto |
| `GET /api/v1/notices` · `POST /api/v1/notices/seen` | Avisos (envíos fallidos, brigada con problemas…), del más nuevo al más viejo, con `seen`; marcar todos como vistos |
| `GET /api/v1/channels` | Canal de Meta: `{mode: mock\|real, channels, problems, graph_version}` (sin mostrar ningún token) |
| `GET /webhook/meta` | Sin sesión. Verificación de Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| `POST /webhook/meta` | Sin sesión, **firmado por Meta** (`X-Hub-Signature-256` con el app secret; sin firma válida → `403`). Contesta al toque `{received}` y procesa atrás; los reintentos de Meta no se procesan dos veces |

Errores: `{"detail": "<mensaje en castellano para mostrar tal cual>"}` con `400` (la brigada lo rechazó), `401`, `404` (el pendiente no existe o ya se resolvió), `409` (no corresponde: aprobar algo humano, etc.), `422` (dato inválido), `429`.

## Campos editables por tipo
| Tipo | Se puede cambiar al aprobar |
|---|---|
| `enviar_presupuesto` | `price` |
| `confirmar_pago` | `amount` |
| `confirmar_turno` | `date`, `time` |
| `cancelar_pedido` | nada |

## Canal de Meta (`meta.py`)
- Config por variables de entorno (en el VPS, `datos/meta.env`): `META_MODE` (`mock` por defecto: no sale nada), `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_WA_TOKEN`, `META_WA_PHONE_ID`, `META_IG_TOKEN`, `META_IG_HOST`, `META_GRAPH_VERSION` (v26.0).
- WhatsApp: `POST graph.facebook.com/v26.0/<PHONE_NUMBER_ID>/messages`, partido en pedazos de 4096. Instagram: `POST graph.instagram.com/v26.0/me/messages`, pedazos de 1000 bytes.
- Fuera de la ventana de 24 h desde el último mensaje del cliente no se manda: queda un aviso para la dueña con el texto, para que le escriba ella.
- Los envíos salen en un hilo aparte. Si Meta los rechaza (token vencido, etc.), aviso para la dueña. Los tokens nunca van a los logs.
- Fuentes revisadas el 23 nov 2026 en developers.facebook.com. **No probado contra Meta real** (no hay cuentas todavía, pendiente para 04): probado con la Graph API falsa.

## Tests
`python -m pytest` (33 tests: API, canal de Meta, claves y chequeo de arranque y armado del paquete del VPS). El cliente de la app se prueba contra esta API con `scripts\servidor_de_prueba.py` y `ApiContractTest` de la app (ver `..\android\README.md`).
