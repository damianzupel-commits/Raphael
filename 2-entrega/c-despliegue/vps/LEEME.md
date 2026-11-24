# Despliegue de Raphael Empresas v2 en el VPS

Kit para instalar en un VPS Ubuntu (Hetzner CX33 de referencia, Ubuntu 24.04 con Python 3.12) la instalación de la clienta: harness (`raphael-core`), orquestador en modo `secretary`, brigada `empresas` y su API con el webhook de Meta. Hecho en la pieza 15 el 23 nov 2026. **Pendiente para 03:** revisarlo y adoptarlo, o reemplazarlo por el servidor nuevo.

## Pasos
1. **En la PC** armá el paquete (con la instalación real de la clienta, si ya está):
   `python armar_paquete.py --instalacion ..\instalacion\clienta.installation.yaml` → `obra\raphael-v2-nube.tgz`
2. **Subilo al VPS:** `scp obra\raphael-v2-nube.tgz root@<IP>:`
3. **En el VPS:** `tar xzf raphael-v2-nube.tgz && cd raphael-v2-nube && sudo ./instalar-v2.sh <tu-dominio>.duckdns.org`
   Te pide la clave de la app (mínimo 8 caracteres). Queda en modo `mock`: no le escribe a nadie.
4. **DuckDNS:** el dominio tiene que apuntar a la IP del VPS. Caddy saca el certificado solo.
5. **App:** entrá con `https://<tu-dominio>` y la clave.
6. **Meta (con la 04):** completá `/opt/raphael-v2/datos/meta.env` (verify token, app secret, tokens e ids). En la app de Meta, webhook `https://<tu-dominio>/webhook/meta`, suscripto a `messages`. Cuando esté todo: `META_MODE=real` y `sudo systemctl restart raphael-empresas`.

## Qué deja instalado
| | |
|---|---|
| `/opt/raphael-v2/piezas` y `venv` | los 4 paquetes y su Python |
| `/opt/raphael-v2/datos/installation.yaml` | la instalación (no se pisa al reinstalar ni al actualizar) |
| `/opt/raphael-v2/datos/raphael.sqlite` | la base de la clienta (pendientes, encargos, conversaciones, clave hasheada) |
| `/opt/raphael-v2/datos/meta.env` | credenciales de Meta (`chmod 600`, nunca a git) |
| `/opt/raphael-v2/datos/tienda.env` | tokens de la tienda si usa Tiendanube, Shopify o WooCommerce (`chmod 600`) |
| `/opt/raphael-v2/datos/copias/` | copia diaria de la base a las 04:17, comprimida, se guardan 14 (`raphael-copia.timer`) |
| `raphael-empresas.service` | la API en `127.0.0.1:8787`, arranca sola, usuario `raphael` sin login, sistema de solo lectura salvo `datos/` |
| Caddy | HTTPS en el dominio; solo pasan `/api/v1/*` y `/webhook/meta` |

## Actualizar
Paquete nuevo → `sudo ./actualizar-v2.sh` desde la carpeta nueva: copia la base, guarda piezas y venv anteriores y, si no arranca en 30 s, vuelve a la versión anterior.

## Comandos útiles
- Logs: `journalctl -u raphael-empresas -n 100 -f`
- Copia a mano: `sudo -u raphael /opt/raphael-v2/copia.sh /opt/raphael-v2`
- Cambiar la clave de la app: `sudo -u raphael /opt/raphael-v2/venv/bin/raphael-empresas-api clave --instalacion /opt/raphael-v2/datos/installation.yaml --datos /opt/raphael-v2/datos`. Con el servicio frenado; cierra todas las sesiones.

## Probado (23 nov 2026, en la nube)
Armado del paquete, instalación en modo "solo archivos" (venv, paquetes, chequeo, clave), arranque de la API con el entorno de `meta.env`, salud, verificación del webhook y copia de la base. **No probado en un VPS de verdad:** systemd, Caddy, DuckDNS y Meta real.

## Pendiente para 03
Copia de la base fuera del servidor, alerta si el servicio se cae, alerta de tokens de Meta por vencer, y la versión del canal con push para la app.
