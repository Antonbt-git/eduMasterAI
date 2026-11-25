#!/usr/bin/env bash
# Smoke tests post-despliegue (health checks + login + KPIs).
set -euo pipefail
BASE=${1:-http://localhost:8080}
curl -fsS "$BASE/healthz" >/dev/null && echo "✔ web"
curl -fsS "$BASE/api/v1/../../health/ready" >/dev/null 2>&1 || curl -fsS "${API:-http://localhost:8000}/health/ready"; echo
TOKEN=$(curl -fsS "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@edumaster.ai","password":"EduMaster#2026"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -fsS "$BASE/api/v1/dashboard/summary" -H "Authorization: Bearer $TOKEN" >/dev/null && echo "✔ dashboard"
curl -fsS "$BASE/api/v1/ml/networks" -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json;[print("✔",n["key"],n["state"]) for n in json.load(sys.stdin)]'
