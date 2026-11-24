#!/usr/bin/env bash
# Instala todos los repos raphael-* en modo editable en un entorno virtual (.venv junto a los repos).
set -e
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
python3 -m venv "$RAIZ/.venv"
"$RAIZ/.venv/bin/pip" install -q --upgrade pip
"$RAIZ/.venv/bin/pip" install -q -e "$RAIZ/raphael-harness[dev]"
for repo in "$RAIZ"/raphael-*/; do
  [ "$(basename "$repo")" = "raphael-harness" ] || "$RAIZ/.venv/bin/pip" install -q -e "$repo"
done
"$RAIZ/.venv/bin/raphael" piezas
