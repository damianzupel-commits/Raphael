#!/usr/bin/env bash
# Actualiza todos los repos y reconstruye. Si los tests fallan, vuelve atrás y deja corriendo la versión anterior.
set -uo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
declare -A ANTES
for r in "$RAIZ"/raphael-*/; do
  ANTES["$r"]=$(git -C "$r" rev-parse HEAD)
  git -C "$r" pull --ff-only || { echo "No se pudo actualizar $r"; exit 1; }
done
cd "$RAIZ/raphael-servidor/despliegue"
if docker compose build; then
  docker compose exec -T raphael python -m raphael_servidor backup || true
  docker compose up -d
  echo "Actualizado."
else
  echo "Los tests fallaron: vuelvo a la versión anterior."
  for r in "${!ANTES[@]}"; do git -C "$r" reset --hard "${ANTES[$r]}"; done
  exit 1
fi
