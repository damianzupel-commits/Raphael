#!/usr/bin/env bash
# Corre los tests de cada repo por separado (como lo haría su CI) y al final la prueba integrada.
# Uso: desde la carpeta que contiene los repos raphael-*:  raphael-harness/scripts/tests-todos.sh
set -u
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-python3}"
fallos=0
for repo in "$RAIZ"/raphael-*/; do
  nombre="$(basename "$repo")"
  printf '%-22s ' "$nombre"
  if (cd "$repo" && "$PY" -m pytest -q -p no:cacheprovider >/tmp/raphael-test.log 2>&1); then
    tail -1 /tmp/raphael-test.log
  else
    echo "FALLA"; tail -20 /tmp/raphael-test.log; fallos=$((fallos+1))
  fi
done
exit $fallos
