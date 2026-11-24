# Instalación de la clienta (VPS)

- `clienta.installation.yaml`: la instalación (edición `cloud`, orquestador `secretary`, brigada `empresas`). Hoy con los datos del ejemplo piloto: reemplazarlos con `perfil_a_instalacion.py` sobre el `perfil.yaml` real.
- `requirements-vps.txt`: los tres paquetes (harness, orquestador, brigada).

## Probar
```
# desde la raíz del repo, con los paquetes instalados (ver requirements-vps.txt)
python 1-harness/c-brigadas/15-empresas/b-codigo/scripts/arrancar.py --instalacion 2-entrega/c-despliegue/instalacion-clienta/clienta.installation.yaml --datos .data/datos-prueba --probar --estado
```
`--probar` corre un recorrido de humo sin red en una base temporal. Sin `--probar` usa `--datos` (ahí queda `raphael.sqlite`).

## Subirla al VPS
Con el kit de `../vps/` (ver su `LEEME.md`): `armar_paquete.py` en la PC, `instalar-v2.sh <dominio>` en el VPS.
Ahí quedan la API de la app, el webhook de Meta (`/webhook/meta`), HTTPS con Caddy, systemd y la copia diaria de la base.
El kit ya está adoptado (24 nov). Pendiente: copia de la base fuera del servidor y alertas.
