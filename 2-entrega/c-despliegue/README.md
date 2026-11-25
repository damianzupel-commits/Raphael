# Entrega · c-despliegue
- `vps/`: el kit del VPS (instalar y actualizar con vuelta atrás, systemd, Caddy, copia diaria y `armar_paquete.py`). Probado solo en modo "solo archivos".
- `instalacion-clienta/`: la instalación de la clienta (harness + orquestador en modo `secretary` + brigada Empresas). Falta pasar su `perfil.yaml` real.
- `QUE-CARGAR.md`: el único documento de claves (qué cargar y dónde). `raphael.env.plantilla`: el archivo de claves, y `windows/arrancar.bat`: el arranque en la PC de Windows (chequeo, clave y servidor).
- `cuentas-y-apis/`: cuentas externas (Meta, WhatsApp, Instagram de prueba, proveedor de IA, Hetzner y DuckDNS). Nunca se guardan claves acá.
