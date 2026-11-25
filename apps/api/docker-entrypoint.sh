#!/bin/sh
set -e
echo "[entrypoint] Ejecutando migraciones versionadas (alembic upgrade head)…"
for i in 1 2 3 4 5 6 7 8 9 10; do
  alembic upgrade head && break
  echo "[entrypoint] Base de datos no disponible, reintento $i/10"; sleep 3
done
if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m app.seed
fi
exec "$@"
