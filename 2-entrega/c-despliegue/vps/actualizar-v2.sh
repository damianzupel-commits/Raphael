#!/usr/bin/env bash
# Actualiza Raphael Empresas v2 con un raphael-v2-nube nuevo. Copia la base antes y, si no arranca, vuelve a lo anterior.
# Uso (desde la carpeta raphael-v2-nube NUEVA):  sudo ./actualizar-v2.sh
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="${RAPHAEL_RAIZ:-/opt/raphael-v2}"
PUERTO=8787
PAQUETES=(raphael-core raphael-orchestrator raphael-empresas raphael-empresas-api)
[ "$(id -u)" = 0 ] || { echo "Correlo con sudo."; exit 1; }
for p in "${PAQUETES[@]}"; do [ -d "$AQUI/piezas/$p" ] || { echo "Falta piezas/$p."; exit 1; }; done

echo "Copia de la base…"
sudo -u raphael "$RAIZ/copia.sh" "$RAIZ" || echo "(sin copia: seguimos)"
rm -rf "$RAIZ/piezas.anterior" "$RAIZ/venv.anterior"
cp -a "$RAIZ/piezas" "$RAIZ/piezas.anterior"; cp -a "$RAIZ/venv" "$RAIZ/venv.anterior"
cp -a "$AQUI/piezas/." "$RAIZ/piezas/"
cp -a "$AQUI/copia.sh" "$RAIZ/copia.sh"
"$RAIZ/venv/bin/pip" install --quiet --force-reinstall --no-deps "${PAQUETES[@]/#/$RAIZ/piezas/}"
"$RAIZ/venv/bin/pip" install --quiet "${PAQUETES[@]/#/$RAIZ/piezas/}"
chown -R raphael:raphael "$RAIZ"
systemctl restart raphael-empresas
for i in $(seq 1 30); do curl -fsS "http://127.0.0.1:$PUERTO/api/v1/health" >/dev/null 2>&1 && { echo "Actualizado y andando."; exit 0; }; sleep 1; done
echo "No arrancó con la versión nueva: vuelvo a la anterior."
rm -rf "$RAIZ/piezas" "$RAIZ/venv"; mv "$RAIZ/piezas.anterior" "$RAIZ/piezas"; mv "$RAIZ/venv.anterior" "$RAIZ/venv"
systemctl restart raphael-empresas
exit 1
