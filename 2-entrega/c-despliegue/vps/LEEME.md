# Despliegue de Raphael Empresas v2 en el VPS

Kit para instalar en un VPS Ubuntu (Hetzner CX33 de referencia, Ubuntu 24.04 con Python 3.12) la instalación de la clienta: harness (`raphael-core`), orquestador en modo `secretary`, brigada `empresas` y su API con el webhook de Meta. Hecho en la pieza 15 el 23 nov 2026. Adoptado por la pieza 03 el 24 nov 2026 (rutas del árbol a/b/c verificadas).

## Pasos
1. **En la PC** armá el paquete (con la instalación real de la clienta, si ya está):
   `python 2-entrega/c-despliegue/vps/armar_paquete.py --instalacion <la-de-la-clienta>.yaml` (desde la raíz del repo; sin `--instalacion` usa la de ejemplo) → `dist/raphael-v2-nube.tgz` (`dist/` no va a git)
2. **Subilo al VPS:** `scp dist/raphael-v2-nube.tgz root@<IP>:`
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

## Antes de montar (checklist sin claves)
- [ ] VPS Hetzner CX33 con Ubuntu 24.04, acceso por clave SSH, firewall con 22, 80 y 443.
- [ ] Dominio DuckDNS apuntando a la IP del VPS.
- [ ] `installation.yaml` real de la clienta (`perfil_a_instalacion.py`), con `store.source.url` y `store.public_url`.
- [ ] `NVIDIA_API_KEY` cargada por Damián en el VPS (en `meta.env` o un `EnvironmentFile` aparte), nunca por chat; sin ella el harness degrada a reglas y lo avisa.
- [ ] App de Meta con número de prueba: recién ahí `META_MODE=real`.
- [ ] App Android compilada con `-Pservidor=https://<dominio>` y firmada con la clave respaldada fuera de git.

## Probado en la nube el 24 nov 2026
Tests de la API (26), ruff, armado del paquete (110 archivos, sin `.env`, bases ni claves), instalación en modo "solo archivos" con el layout del árbol a/b/c, arranque de la API, `/api/v1/health` y verificación del webhook. `bash -n` de los tres scripts. Sigue sin probarse en un VPS real.

## Pendiente para 03
Copia de la base fuera del servidor, alerta si el servicio se cae, alerta de tokens de Meta por vencer, y la versión del canal con push para la app.
