# 2 · Entrega

Lo que lleva Raphael a la gente: el servidor, la app del celular y el despliegue en el VPS.

- `a-conocimiento/`: spec del servidor, la app y el instalador, y el log de la pieza (chat 3).
- `b-codigo/`: `servidor/` (API FastAPI y canal de Meta, 26 tests), `android/` (app 1.1.0, compila, sin probar en teléfono) y `panel-escritorio/` (el código del panel vive en `1-harness/b-codigo/panel/`).
- `c-despliegue/`: `vps/` (kit de Hetzner con systemd y Caddy), `instalacion-clienta/` (la instalación de la primera clienta) y `cuentas-y-apis/` (Meta, IA, Hetzner y DuckDNS, chat 4; nunca claves).
