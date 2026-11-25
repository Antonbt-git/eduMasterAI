# Runbook — Restauración de base de datos

1. Detener la API (`docker compose stop api`).
2. Restaurar el dump: `pg_restore -d edumaster /backups/edumaster-YYYYMMDD.dump`.
3. Ejecutar migraciones: `alembic upgrade head`.
4. Verificar integridad de auditoría: `GET /api/v1/audit-logs/verify`.
5. Reiniciar la API y comprobar `/health/ready`.
6. Validar con `scripts/verify-restore.sh`.
