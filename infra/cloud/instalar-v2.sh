#!/usr/bin/env bash
# Instala Raphael Empresas v2 en un VPS Ubuntu (Hetzner): harness + orquestador (secretary) + brigada Empresas + API.
# Servicio que arranca solo, HTTPS automático con Caddy y copia diaria de la base.
# Uso (desde la carpeta raphael-v2-nube):  sudo ./instalar-v2.sh tu-dominio.duckdns.org
# Se puede volver a correr sin perder datos: no pisa la instalación, la base, la clave ni meta.env.
set -euo pipefail

DOMINIO="${1:?Uso: sudo ./instalar-v2.sh tu-dominio.duckdns.org}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAPHAEL_RAIZ:-/opt/raphael-v2}"            # RAPHAEL_RAIZ y RAPHAEL_SOLO_ARCHIVOS=1: probar el armado sin tocar el sistema
SOLO_ARCHIVOS="${RAPHAEL_SOLO_ARCHIVOS:-0}"
USUARIO=raphael
PIEZAS="$RAIZ/piezas"; DATOS="$RAIZ/datos"; VENV="$RAIZ/venv"; PUERTO=8787
PAQUETES=(raphael-core raphael-orchestrator raphael-empresas raphael-empresas-api)

[ "$SOLO_ARCHIVOS" = 1 ] || [ "$(id -u)" = 0 ] || { echo "Correlo con sudo: sudo ./instalar-v2.sh $DOMINIO"; exit 1; }
for p in "${PAQUETES[@]}"; do [ -d "$AQUI/piezas/$p" ] || { echo "Falta piezas/$p al lado de este script."; exit 1; }; done

echo "== 1/7 Paquetes del sistema"
if [ "$SOLO_ARCHIVOS" != 1 ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y python3 python3-venv python3-pip curl sqlite3
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
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || { echo "Hace falta Python 3.11 o más (Ubuntu 24.04 trae 3.12)."; exit 1; }

echo "== 2/7 Archivos en $RAIZ"
mkdir -p "$PIEZAS" "$DATOS/copias"
cp -a "$AQUI/piezas/." "$PIEZAS/"
cp -a "$AQUI/copia.sh" "$RAIZ/copia.sh"; chmod 755 "$RAIZ/copia.sh"
[ -f "$DATOS/installation.yaml" ] || { cp "$AQUI/clienta.installation.yaml" "$DATOS/installation.yaml"; echo ">> Instalación de ejemplo copiada: reemplazala por la de la clienta ($DATOS/installation.yaml)."; }
if [ ! -f "$DATOS/meta.env" ]; then
  cp "$AQUI/meta.env.plantilla" "$DATOS/meta.env"
  echo ">> Completá $DATOS/meta.env con las credenciales de Meta (queda en modo mock hasta que pongas META_MODE=real)."
fi
[ -f "$DATOS/tienda.env" ] || cp "$AQUI/tienda.env.plantilla" "$DATOS/tienda.env"
chmod 600 "$DATOS/meta.env" "$DATOS/tienda.env"

echo "== 3/7 Python y dependencias"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet "${PAQUETES[@]/#/$PIEZAS/}" "uvicorn[standard]"

echo "== 4/7 Chequeo de la instalación (sin red, base temporal)"
"$VENV/bin/python" - "$DATOS/installation.yaml" <<'PY'
import sys, tempfile
from raphael_empresas.boot import start
rt, rep = start(sys.argv[1], tempfile.mkdtemp(), models=False)
if rep["errors"] or "empresas" not in rt.brigades or rt.orchestrator is None:
    print("La instalación no monta:", rep["errors"]); sys.exit(1)
print("Monta bien:", ", ".join(rep["mounted"]), "· orquestador", rt.orchestrator.name)
PY

echo "== 5/7 Clave de la app (la elegís vos ahora: nadie más la puede poner)"
if ! "$VENV/bin/python" - "$DATOS" <<'PY'
import sys, pathlib
from datetime import datetime
from raphael_core.store import Store
from raphael_empresas_api.auth import Auth
db = pathlib.Path(sys.argv[1]) / "raphael.sqlite"
sys.exit(0 if db.exists() and Auth(Store(str(db)), datetime.now).has_key() else 1)
PY
then
  "$VENV/bin/raphael-empresas-api" clave --instalacion "$DATOS/installation.yaml" --datos "$DATOS"
fi
[ "$SOLO_ARCHIVOS" = 1 ] || chown -R "$USUARIO":"$USUARIO" "$RAIZ"

if [ "$SOLO_ARCHIVOS" = 1 ]; then echo "Listo (solo archivos)."; exit 0; fi

echo "== 6/7 Servicio y copia diaria"
for f in raphael-empresas.service raphael-copia.service raphael-copia.timer; do
  sed -e "s|@RAIZ@|$RAIZ|g" -e "s|@USUARIO@|$USUARIO|g" -e "s|@PUERTO@|$PUERTO|g" "$AQUI/$f" > "/etc/systemd/system/$f"
done
systemctl daemon-reload
systemctl enable --now raphael-empresas raphael-copia.timer
systemctl restart raphael-empresas

echo "== 7/7 HTTPS en https://$DOMINIO"
if command -v ufw >/dev/null && ufw status | grep -q active; then ufw allow 80/tcp; ufw allow 443/tcp; fi
sed -e "s|@DOMINIO@|$DOMINIO|g" -e "s|@PUERTO@|$PUERTO|g" "$AQUI/Caddyfile.plantilla" > /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null 2>&1 || true
systemctl restart caddy

for i in $(seq 1 30); do curl -fsS "http://127.0.0.1:$PUERTO/api/v1/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:$PUERTO/api/v1/health" >/dev/null 2>&1 || { echo "No arrancó: mirá  journalctl -u raphael-empresas -n 50"; exit 1; }
IP="$(curl -fsS https://api.ipify.org 2>/dev/null || echo '?')"
cat <<FIN

Listo: Raphael Empresas v2 está andando. IP pública: $IP
1) El dominio $DOMINIO tiene que apuntar a $IP (DuckDNS).
2) Probá https://$DOMINIO/api/v1/health desde el celular (el certificado tarda un minuto la primera vez).
3) En la app de Meta, webhook: https://$DOMINIO/webhook/meta con el META_VERIFY_TOKEN de $DATOS/meta.env.
4) Cuando esté todo, META_MODE=real en meta.env y:  sudo systemctl restart raphael-empresas
FIN
