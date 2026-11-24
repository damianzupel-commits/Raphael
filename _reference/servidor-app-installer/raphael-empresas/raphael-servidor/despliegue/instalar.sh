#!/usr/bin/env bash
# Instala Raphael en un mini PC Linux (Ubuntu/Debian) del cliente.
# Uso:  ./instalar.sh RUTA/AL/perfil.yaml
# Requiere: los repos raphael-* en la misma carpeta (ver README) y conexión a internet.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
PERFIL="${1:?Pasame el perfil de la empresa: ./instalar.sh perfil.yaml}"
DATOS="$RAIZ/datos"

if ! command -v docker >/dev/null; then
  echo "Instalando Docker…"; curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi
mkdir -p "$DATOS/backups"
cp "$PERFIL" "$DATOS/perfil.yaml"
if [ ! -f "$DATOS/.env" ]; then
  cp "$RAIZ/raphael-servidor/despliegue/env.ejemplo" "$DATOS/.env"
  read -rp "Clave de licencia (RAPH-…): " LIC
  sed -i "s/^RAPHAEL_LICENCIA=.*/RAPHAEL_LICENCIA=$LIC/" "$DATOS/.env"
  KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  sed -i "s|^RAPHAEL_CLAVE_BACKUP=.*|RAPHAEL_CLAVE_BACKUP=$KEY|" "$DATOS/.env"
  echo "Completá el resto de $DATOS/.env (relay, central, WhatsApp) y volvé a correr este script."
  echo "Guardá la RAPHAEL_CLAVE_BACKUP en un lugar seguro: sin ella no se pueden abrir los backups."
  exit 0
fi
chmod 600 "$DATOS/.env"
cd "$RAIZ/raphael-servidor/despliegue"
docker compose build
docker compose run --rm raphael python -m raphael_servidor iniciar --dir /datos --perfil /datos/perfil.yaml
docker compose up -d
IP=$(hostname -I | awk '{print $1}')
echo "Listo. Panel de la dueña: http://$IP:8080  (desde un celular en la misma red WiFi)"
