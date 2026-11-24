#!/usr/bin/env bash
# Copia de la base de la clienta (SQLite, en caliente y consistente) a datos/copias/, comprimida. Guarda las últimas 14.
# La corre el timer raphael-copia una vez por día. Uso a mano:  sudo -u raphael /opt/raphael-v2/copia.sh /opt/raphael-v2
# Pendiente para 03: llevar una copia FUERA del servidor (otro proveedor o el celular de Damián).
set -euo pipefail
RAIZ="${1:-/opt/raphael-v2}"
DB="$RAIZ/datos/raphael.sqlite"; DEST="$RAIZ/datos/copias"
[ -f "$DB" ] || { echo "Todavía no hay base en $DB"; exit 0; }
mkdir -p "$DEST"
F="$DEST/raphael-$(date +%Y%m%d-%H%M%S).sqlite"
"$RAIZ/venv/bin/python" - "$DB" "$F" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
ok = dst.execute("pragma integrity_check").fetchone()[0]
src.close(); dst.close()
sys.exit(0 if ok == "ok" else 1)
PY
gzip -f "$F"
ls -1t "$DEST"/raphael-*.sqlite.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "Copia: $F.gz"
