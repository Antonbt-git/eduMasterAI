#!/bin/sh
# Ajusta permisos de los volúmenes montados (discos de Render, volúmenes Docker) y
# ejecuta el proceso como usuario sin privilegios (uid 10002).
set -e
for d in "${ML_ARTIFACT_DIR:-/artifacts}" "${ML_DATA_DIR:-/data}"; do
  mkdir -p "$d"
  [ "$(id -u)" = "0" ] && chown -R 10002:0 "$d" 2>/dev/null || true
done
if [ "$(id -u)" = "0" ]; then
  exec setpriv --reuid=10002 --regid=0 --clear-groups "$@"
fi
exec "$@"
