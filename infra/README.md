# infra/

Instalador y despliegue.

- Nube (Hetzner, referencia CX33: 4 vCPU, 8 GB, Ubuntu 24.04): paquete con venv + systemd + Caddy; `instalar-nube.sh <dominio>` instala y `actualizar-nube.sh` actualiza, con copia de seguridad y vuelta atrás si el servicio no queda sano.
- Instalador de la PC (Windows) para Raphael personal.
- Dominio con DuckDNS apuntando a la IP del VPS.

Código existente: `_reference/servidor-app-installer/` (incluye `raphael-servidor/despliegue/nube/`). Pieza dueña: chat 3.

## Contenido
- `cloud/`: kit del VPS hecho por el chat 15 (instalar con systemd y Caddy, actualizar con vuelta atrás, copia diaria de la base, `armar_paquete.py`, plantillas de `.env`). Probado en modo "solo archivos"; **no probado en un VPS real** y el Caddyfile sin validar.
- `client-install/`: la instalación de la clienta (`clienta.installation.yaml`: harness + orquestador en modo `secretary` + brigada Empresas). Arranca limpia; falta pasar el `perfil.yaml` real de la clienta por `perfil_a_instalacion.py`.
