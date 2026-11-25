#!/usr/bin/env bash
# Backup cifrado de PostgreSQL (RPO objetivo ≤ 24 h). Requiere BACKUP_PASSPHRASE.
set -euo pipefail
: "${BACKUP_PASSPHRASE:?Defina BACKUP_PASSPHRASE}"
TS=$(date -u +%Y%m%dT%H%M%SZ); mkdir -p backups
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-edumaster}" -Fc "${POSTGRES_DB:-edumaster}" \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE > "backups/edumaster_${TS}.dump.enc"
echo "Backup: backups/edumaster_${TS}.dump.enc"
