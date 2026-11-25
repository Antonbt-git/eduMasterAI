#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"
curl -fsS "$BASE/health/ready" >/dev/null
curl -fsS "$BASE/api/v1/audit-logs/verify" | grep -q '"valid":true'
echo "restore verification OK"
