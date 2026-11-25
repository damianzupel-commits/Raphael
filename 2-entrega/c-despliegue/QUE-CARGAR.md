# Qué cargar y dónde

Un solo arranque, sin ninguna clave previa. Las claves se cargan, cambian o sacan **desde la pantalla de Configuración** (`http://127.0.0.1:8787/config`, o la dirección pública del túnel + `/config`), sin tocar archivos ni código; se aplican en el momento, sin reiniciar (las de la tienda piden reiniciar). Se guardan solo en el archivo local **`raphael.env`** (fuera de git) y la pantalla nunca las muestra completas: solo "cargada" y los últimos 4 caracteres. Editar el archivo a mano sigue andando igual.

**Primer acceso:** en el primer arranque Raphael genera sola la clave de la app (formato `xxxx-xxxx-xxxx`), la muestra una vez en la ventana y la deja en `.data\empresas\clave-inicial.txt`. Con ella entrás a Configuración; ahí podés cambiarla (se borra `clave-inicial.txt`). El acceso directo abre la pantalla solo.
Sin una clave el sistema no se rompe, degrada: sin IA responde por reglas, sin Meta real el canal queda en `mock` (no manda nada a nadie).

## Dónde va el archivo
| Dónde corre | Archivo | Cómo se crea |
| --- | --- | --- |
| PC de Damián (Windows) | `D:\Raphael Ultimate\raphael\.data\empresas\raphael.env` | `2-entrega\c-despliegue\windows\arrancar.bat` lo crea la primera vez desde `raphael.env.plantilla` |
| VPS (cuando haya) | `/opt/raphael-v2/datos/meta.env` (el kit ya lo lee; también se lee `raphael.env` y `tienda.env` en la misma carpeta) | `instalar-v2.sh` |

Está fuera de git (`.data/`, `*.env`). Las claves **nunca** van al repo ni al chat. Si una variable ya existe en el entorno del sistema, esa gana sobre el archivo.

## Qué cargar
| Variable | Para qué | Dónde se consigue | Si falta |
| --- | --- | --- | --- |
| `OPENROUTER_API_KEY` | IA: la voz de la Secretaria con la dueña, el ruteo y las brigadas que usen modelo. Principal DeepSeek V4 Flash, con `data_collection=deny` | openrouter.ai → Keys (empieza con `sk-or-`) | Responde por reglas. Lo dice el chequeo |
| `META_MODE` | `mock` (no manda nada) o `real` | Lo cambiás vos, a `real`, cuando lo demás esté completo | Queda en `mock` |
| `META_VERIFY_TOKEN` | Contraseña del webhook | La inventás vos (texto largo) y la pegás igual en la app de Meta | Con `real`, no arranca el canal |
| `META_APP_SECRET` | Firma de cada webhook (rechaza lo que no venga de Meta) | developers.facebook.com → tu app → Configuración → Básica | Con `real`, no arranca el canal |
| `META_WA_TOKEN` + `META_WA_PHONE_ID` | WhatsApp: token permanente del usuario del sistema e id del número | Meta Business → usuarios del sistema; WhatsApp → configuración de la API | No hay WhatsApp |
| `META_IG_TOKEN` (+ `META_IG_HOST`) | Instagram (mensajes directos) | Instagram API with Instagram Login, cuenta profesional | No hay Instagram |
| `RAPHAEL_PUBLIC_URL` | Solo informativa: el chequeo te escribe la URL del webhook para pegar en Meta | La que te dé el túnel | Nada, solo no te muestra la URL |
| `TIENDANUBE_TOKEN` / `SHOPIFY_TOKEN` / `WOO_KEY` + `WOO_SECRET` | Catálogo, solo si la clienta usa esa tienda (`store.source.kind` en su instalación) | El panel de cada tienda | Sin catálogo conectado |
| `NVIDIA_API_KEY` | Solo pruebas de desarrollo; ningún escalón la usa por defecto | build.nvidia.com | Nada |

Además, dos cosas que no son claves:
- **Clave de la app de la dueña:** se genera sola la primera vez; se cambia desde Configuración o con `arrancar.bat clave` (mínimo 8 caracteres).
- **Perfil real de la clienta:** hoy la instalación trae datos de ejemplo (Taller Ejemplo). Se carga después de la entrevista con `1-harness\c-brigadas\15-empresas\b-codigo\scripts\perfil_a_instalacion.py`, y el resultado se guarda como `.data\empresas\installation.yaml`.

El modelo, los escalones y el tope mensual de gasto en IA están en `1-harness/b-codigo/src/raphael_core/models/modelos.yaml` (hoy USD 5 por mes, supuesto a ajustar). Los slugs y precios de ese archivo son supuestos sin verificar contra openrouter.ai/models.

## Arrancar en la PC (Windows)
1. `2-entrega\c-despliegue\windows\arrancar.bat chequear` → lista qué está cargado y qué falta, sin mostrar ningún valor. Se puede correr las veces que haga falta.
2. `arrancar.bat` (o el acceso directo) → levanta todo (harness, Secretaria, brigada Empresas, API y canal de Meta) en `127.0.0.1:8787` y imprime el chequeo.
3. Túnel: `tailscale funnel --bg 8787` y `tailscale funnel status` para ver la URL pública (verificarlo con la versión de Tailscale instalada). Esa URL + `/webhook/meta` es lo que se pega en la app de Meta, suscripto a `messages`. Poné la URL en `RAPHAEL_PUBLIC_URL` para que el chequeo la repita.
4. Cuando todo esté: `META_MODE=real`, y `arrancar.bat chequear --real` tiene que terminar sin faltantes (código 0).

Requiere que la PC esté prendida y con Python 3.12 y el `.venv` del repo (el mismo de la puerta). `arrancar.bat` agrega las cuatro piezas al `PYTHONPATH`, no hace falta instalarlas.

## Qué hace el sistema sin cada clave
- **Sin `OPENROUTER_API_KEY`:** todo funciona por reglas. Las respuestas a clientes **siempre** son por reglas con la información cargada (decisión de la brigada Empresas: no inventar nada); la IA entra en la conversación con la dueña, el ruteo y el reporte.
- **Sin Meta real:** los mensajes de clientes entran por el webhook (o por la API de pruebas) y las respuestas quedan registradas en lugar de salir.
- **Sin túnel:** la app y los webhooks solo se ven desde la propia PC.
- Lo irreversible (presupuestos, pagos, mensajes salientes con decisión) siempre espera la aprobación de la dueña.
