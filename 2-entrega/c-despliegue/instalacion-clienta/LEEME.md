# Instalación de la clienta (VPS)

- `clienta.installation.yaml`: la instalación (edición `cloud`, orquestador `secretary`, brigada `empresas`). Hoy con los datos del ejemplo piloto: reemplazarlos con `perfil_a_instalacion.py` sobre el `perfil.yaml` real.
- `requirements-vps.txt`: los tres paquetes (harness, orquestador, brigada).

## Probar
```
cd ..\raphael-empresas
python scripts\arrancar.py --instalacion ..\instalacion\clienta.installation.yaml --datos ..\..\..\..\obra\datos-prueba --probar --estado --dev ..\..\..\..\nucleo\02-orquestador\codigo
```
`--probar` corre un recorrido de humo sin red en una base temporal. Sin `--probar` usa `--datos` (ahí queda `raphael.sqlite`).

## Subirla al VPS
Con el kit de `..\despliegue\` (ver su `LEEME.md`): `armar_paquete.py` en la PC, `instalar-v2.sh <dominio>` en el VPS.
Ahí quedan la API de la app, el webhook de Meta (`/webhook/meta`), HTTPS con Caddy, systemd y la copia diaria de la base.
Pendiente para 03: revisar y adoptar ese kit; copia de la base fuera del servidor; alertas.
