#!/usr/bin/env bash
# Restauración probada (RTO objetivo ≤ 4 h). Uso: ./scripts/restore.sh backups/archivo.dump.enc
set -euo pipefail
: "${BACKUP_PASSPHRASE:?Defina BACKUP_PASSPHRASE}"
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in "$1" \
  | docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-edumaster}" -d "${POSTGRES_DB:-edumaster}" --clean --if-exists
echo "Restaurado desde $1. Ejecute smoke tests: make smoke"
