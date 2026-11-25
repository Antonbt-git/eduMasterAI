#!/bin/sh
# Inferencia + worker de entrenamiento en un mismo contenedor (Render, Railway, etc.):
# comparten el disco de artefactos. En docker compose se usan como servicios separados.
set -e
rq worker training --url "$REDIS_URL" --with-scheduler &
WORKER_PID=$!
trap 'kill $WORKER_PID 2>/dev/null' TERM INT
exec uvicorn edumaster_ml.inference.service:app --host 0.0.0.0 --port "${PORT:-8001}" --workers 1
