#!/usr/bin/env bash
# Despliega el esquema y la seguridad de EduMaster.ai en un proyecto Supabase.
#   1) Copia .env.example a .env y completa SUPABASE_DATABASE_URL (Session Pooler, puerto 5432)
#   2) ./scripts/supabase_deploy.sh            (migraciones + RLS + datos DEMO)
#      ./scripts/supabase_deploy.sh --no-seed  (sin datos DEMO, p. ej. producción)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${SUPABASE_DATABASE_URL:?Defina SUPABASE_DATABASE_URL en .env}"
PSQL_URL="${SUPABASE_DATABASE_URL/postgresql+psycopg:/postgresql:}"

echo "▶ Migraciones Alembic contra Supabase"
docker run --rm -e DATABASE_URL="$SUPABASE_DATABASE_URL" edumaster/api:${TAG:-latest} alembic upgrade head \
  || (cd apps/api && DATABASE_URL="$SUPABASE_DATABASE_URL" alembic upgrade head)

echo "▶ Seguridad: RLS, revocación de anon/authenticated, auditoría inmutable y bucket privado"
psql "$PSQL_URL" -v ON_ERROR_STOP=1 -f infra/supabase/002_rls_security.sql

if [[ "${1:-}" != "--no-seed" ]]; then
  echo "▶ Datos DEMO rotulados"
  docker run --rm -e DATABASE_URL="$SUPABASE_DATABASE_URL" edumaster/api:${TAG:-latest} python -m app.seed \
    || (cd apps/api && DATABASE_URL="$SUPABASE_DATABASE_URL" python -m app.seed)
fi
echo "✔ Supabase listo. Levanta el stack con:"
echo "  docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build"
