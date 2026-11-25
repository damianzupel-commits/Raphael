# Raphael personal · cliente-servidor (pieza 3)

Un solo cerebro en tu PC y todas las pantallas como clientes (decisión del 24 nov 2026). El servidor `raphael_personal_api`
corre de fondo, arranca con Windows y sigue andando con el panel cerrado. La página web que sirve, el panel de escritorio y
la app del celular hablan la misma API, con los mismos datos y la misma charla.

## Instalar (una vez)
1. `2-entrega\c-despliegue\personal\instalar-personal.bat` (doble clic). Crea `.venv`, instala todo, deja el servidor como tarea
   programada de Windows ("Raphael Personal", al iniciar sesión, sin ventana) y crea `Raphael.url` en el escritorio.
2. Abrí `http://127.0.0.1:8788/`. Desde esta PC se entra sin clave; la clave de la app está en `.data\personal\clave-inicial.txt`.
3. Pestaña **Configuración**: pegá lo que tengas (NVIDIA, modelo local, etc.). Se aplica en caliente. Lo que falta no rompe nada.
4. Celular: `celular-tailscale.bat` (usa `tailscale serve` en el puerto HTTPS 8443, porque el 443 lo usa el Funnel de Empresas; solo tu red privada, **no** Funnel, sin abrir puertos, y nunca hace `serve reset`). Abrí esa
   dirección `https://….ts.net` en el celular con Tailscale prendido y entrá con la clave de la app.

Registro del servidor: `.data\personal\servidor.log`. Sacar el servicio: `instalar-servicio.bat quitar`.

## Cerebro mixto
- **Lo sensible va en local** (Ollama o LM Studio en tu PC): Seguridad, Investigación, Memoria y Operaciones (`private` en
  `modelos.personal.yaml`; el test `test_los_ids_privados_cubren…` avisa si el manifiesto de una brigada trae otro id).
- **El resto va a la nube con NVIDIA** (gratis para uso tuyo personal; si Raphael sirviera a terceros, sus términos lo tratan como producción).
- Si el modelo local no está prendido: esa brigada sigue **por reglas**, el servidor te avisa (aviso en la app, pestaña Cerebro y
  chequeo) y **no manda nada sensible a la nube**. La garantía la da la pasarela del harness (un pedido privado solo admite
  proveedores de localhost); además una dirección de modelo local que no sea localhost se rechaza.
- Cualquier rol se cambia por configuración, sin tocar código: `RAPHAEL_ROL_MANDO=local,gratis` (también VOZ, JEFE, RUTEO, COCINERO,
  EFIMERO), `RAPHAEL_PRIVADAS=trading,legales`, `OLLAMA_MODEL`, `LMSTUDIO_MODEL`, `LOCAL_LLM_URL`/`LOCAL_LLM_KIND`. El escalón pago
  (OpenRouter) existe pero apagado: `paid_cap_usd_month: 0`.

## API (versión 1, `Authorization: Bearer <token>`)
Sin sesión: `GET /api/v1/health`, `POST /api/v1/login`, `GET /` (la página).
| Ruta | Para qué |
| --- | --- |
| `POST /api/v1/chat` `{text, session}` | hablarle al orquestador maestro |
| `GET /api/v1/summary`, `/updates`, `/notices`, `POST /notices/seen` | estado, avisos (también el de "modelo local apagado") |
| `GET /api/v1/pending`, `POST /pending/{id}/approve｜reject｜resolve` | aprobaciones: solo las resuelve la persona; lo `humano` no se aprueba |
| `GET /api/v1/brain` | roles, escalones, modelo local (responde o no) y brigadas privadas |
| `GET /api/v1/brigades` | brigadas de la instalación: activas, montadas, privadas, no instaladas |
| `GET/PUT /api/v1/config`, `POST /config/clave` | claves a voluntad (nunca se devuelven completas), cambio de clave |
| `POST /api/v1/phone/pair`, `/phone/redeem`, `WS /ws/phone` | emparejar el celular con un código (QR) y enlazarlo con Operaciones |
| `GET /api/v1/voz`, `POST /voz/transcribir` (audio crudo), `POST /voz/hablar` `{text}` → `audio/wav` | voz hablada local del orquestador (`speech_from`) |

## Qué no está hecho o no está probado
- **Probado en la nube (Linux):** arranque real, API, cerebro con modelo local simulado, tests. **No probado en Windows:** los `.bat`, la tarea
  programada, el acceso directo, `icacls` ni Tailscale. **No probado:** Ollama, LM Studio, NVIDIA ni la voz real.
- La **app Android** y el **panel de escritorio** todavía son los de Empresas / el del harness: falta apuntarlos a esta API (pendiente
  de esta pieza; la página web ya cubre el uso desde el celular).
- `tailscale serve --bg --https=8443 http://127.0.0.1:8788` es la sintaxis de versiones recientes; en las viejas cambia. La dirección lleva `:8443`.
- Los ids de las brigadas en `personal.installation.yaml` (`seguridad`, `investigacion`, …) son los probables: una que todavía no
  existe se marca "no instalada" y no rompe el arranque.
- Corre mientras tu sesión de Windows está abierta; arrancar sin iniciar sesión pediría guardar tu contraseña en la tarea y administrador.
