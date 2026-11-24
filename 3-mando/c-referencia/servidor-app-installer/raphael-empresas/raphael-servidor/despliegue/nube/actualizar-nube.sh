#!/usr/bin/env bash
# Actualiza Raphael con una carpeta raphael-nube nueva. Hace backup antes y deja la versión anterior por si hay que volver.
# Uso (desde la carpeta raphael-nube NUEVA):  sudo ./actualizar-nube.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAPHAEL_RAIZ:-/opt/raphael}"
PYPATH="$RAIZ/piezas/raphael-harness/src:$RAIZ/piezas/raphael-servidor/src"
[ "$(id -u)" = 0 ] || { echo "Correlo con sudo."; exit 1; }
[ -d "$AQUI/piezas/raphael-servidor" ] || { echo "No encuentro piezas/ al lado de este script."; exit 1; }

echo "Backup de la base…"
sudo -u raphael env PYTHONPATH="$PYPATH" RAPHAEL_DIR="$RAIZ/datos" "$RAIZ/venv/bin/python" -m raphael_servidor backup --dir "$RAIZ/datos" || echo "(sin backup: seguimos)"
rm -rf "$RAIZ/piezas.anterior"; cp -a "$RAIZ/piezas" "$RAIZ/piezas.anterior"
cp -a "$AQUI/piezas/." "$RAIZ/piezas/"
chown -R raphael:raphael "$RAIZ/piezas"
systemctl restart raphael
for i in $(seq 1 25); do curl -fsS http://127.0.0.1:8080/salud >/dev/null 2>&1 && { echo "Actualizado y andando."; exit 0; }; sleep 1; done
echo "No arrancó con la versión nueva: vuelvo a la anterior."
rm -rf "$RAIZ/piezas"; mv "$RAIZ/piezas.anterior" "$RAIZ/piezas"; systemctl restart raphael
exit 1
