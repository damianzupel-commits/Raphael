#!/usr/bin/env bash
# Instala Raphael en un servidor Ubuntu (Oracle Cloud, Google Cloud, cualquier VPS): servicio que arranca solo + HTTPS automático.
# Uso (desde la carpeta raphael-nube):  sudo ./instalar-nube.sh tu-dominio.duckdns.org
# Se puede volver a correr sin perder datos (no pisa el perfil, la clave ni la base).
set -euo pipefail

DOMINIO="${1:?Uso: sudo ./instalar-nube.sh tu-dominio.duckdns.org}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAPHAEL_RAIZ:-/opt/raphael}"                 # RAPHAEL_RAIZ y RAPHAEL_SOLO_ARCHIVOS=1 son para probar el armado sin tocar el sistema
SOLO_ARCHIVOS="${RAPHAEL_SOLO_ARCHIVOS:-0}"
USUARIO=raphael
PIEZAS="$RAIZ/piezas"; DATOS="$RAIZ/datos"; VENV="$RAIZ/venv"
PYPATH="$PIEZAS/raphael-harness/src:$PIEZAS/raphael-servidor/src"

[ "$SOLO_ARCHIVOS" = 1 ] || [ "$(id -u)" = 0 ] || { echo "Correlo con sudo: sudo ./instalar-nube.sh $DOMINIO"; exit 1; }
[ -d "$AQUI/piezas/raphael-servidor" ] || { echo "No encuentro la carpeta piezas/ al lado de este script."; exit 1; }

echo "== 1/6 Paquetes del sistema"
if [ "$SOLO_ARCHIVOS" != 1 ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y python3 python3-venv python3-pip curl iptables-persistent
  if ! command -v caddy >/dev/null; then
    apt-get install -y caddy || {
      apt-get install -y debian-keyring debian-archive-keyring apt-transport-https gpg
      curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
      curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
      apt-get update -y && apt-get install -y caddy
    }
  fi
  id "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$RAIZ" --shell /usr/sbin/nologin "$USUARIO"
fi

echo "== 2/6 Archivos de Raphael en $RAIZ"
mkdir -p "$PIEZAS" "$DATOS/backups"
cp -a "$AQUI/piezas/." "$PIEZAS/"
[ -f "$DATOS/perfil.yaml" ] || cp "$AQUI/perfil.yaml" "$DATOS/perfil.yaml"
if [ ! -f "$DATOS/.env" ]; then
  cat > "$DATOS/.env" <<ENV
# Configuración de este servidor. Nunca subir a GitHub.
# mock: no manda nada afuera · real: WhatsApp/Instagram de verdad
RAPHAEL_MODO=mock
RAPHAEL_PIEZAS=$PIEZAS
RAPHAEL_FUENTE_REPOS=
ENV
fi

echo "== 3/6 Python y dependencias"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet fastapi "uvicorn[standard]" httpx pydantic pyyaml cryptography
if ! grep -q '^RAPHAEL_CLAVE_BACKUP=' "$DATOS/.env"; then
  echo "RAPHAEL_CLAVE_BACKUP=$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')" >> "$DATOS/.env"
  echo ">> Guardá RAPHAEL_CLAVE_BACKUP (está en $DATOS/.env) en un lugar seguro: sin ella no se pueden abrir los backups."
fi

echo "== 4/6 Clave del panel (la elegís vos ahora, así nadie más puede ponerla primero)"
if [ ! -f "$DATOS/servidor.json" ]; then
  PYTHONPATH="$PYPATH" RAPHAEL_DIR="$DATOS" "$VENV/bin/python" -m raphael_servidor iniciar --dir "$DATOS" --perfil "$DATOS/perfil.yaml"
fi
[ "$SOLO_ARCHIVOS" = 1 ] || { chown -R "$USUARIO":"$USUARIO" "$RAIZ"; chmod 600 "$DATOS/.env" "$DATOS/servidor.json"; }

if [ "$SOLO_ARCHIVOS" = 1 ]; then echo "Listo (solo archivos)."; exit 0; fi

echo "== 5/6 Servicio que arranca solo"
sed -e "s|@RAIZ@|$RAIZ|g" -e "s|@PYPATH@|$PYPATH|g" -e "s|@USUARIO@|$USUARIO|g" "$AQUI/raphael.service.plantilla" > /etc/systemd/system/raphael.service
systemctl daemon-reload
systemctl enable --now raphael
systemctl restart raphael

echo "== 6/6 HTTPS en https://$DOMINIO"
for p in 80 443; do                                    # las imágenes de Oracle bloquean todo salvo SSH
  iptables -C INPUT -p tcp --dport "$p" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport "$p" -j ACCEPT
done
netfilter-persistent save >/dev/null 2>&1 || true
sed -e "s|@DOMINIO@|$DOMINIO|g" "$AQUI/Caddyfile.plantilla" > /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null 2>&1 || true
systemctl restart caddy

for i in $(seq 1 20); do curl -fsS http://127.0.0.1:8080/salud >/dev/null 2>&1 && break; sleep 1; done
if curl -fsS http://127.0.0.1:8080/salud >/dev/null 2>&1; then echo "Raphael está andando."; else echo "Raphael no arrancó: mirá  journalctl -u raphael -n 50"; exit 1; fi
IP="$(curl -fsS https://api.ipify.org 2>/dev/null || echo '?')"
echo
echo "Listo. IP pública de este servidor: $IP"
echo "1) Tu dominio $DOMINIO tiene que apuntar a $IP (en DuckDNS o donde lo hayas creado)."
echo "2) En Oracle Cloud abrí los puertos 80 y 443 (ver LEEME-ORACLE.md, paso 4)."
echo "3) Abrí https://$DOMINIO/panel/  (el certificado puede tardar un minuto la primera vez)."
