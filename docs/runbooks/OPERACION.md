# Runbooks de operación

## Despliegue
1. `git pull && make setup` (no sobrescribe secretos existentes).
2. `TAG=$(git rev-parse --short HEAD) GIT_COMMIT=$TAG docker compose up -d --build`
3. El contenedor `api` aplica `alembic upgrade head` antes de arrancar.
4. `make smoke` — health, login, dashboard y estado de las 5 redes.
Ambientes: `local` → `development` → `staging` → `production` (variable `ENVIRONMENT`). En staging/producción la API rechaza secretos débiles y desactiva la promoción automática de modelos.

## Rollback de aplicación
`TAG=<versión anterior> docker compose up -d` (las migraciones son aditivas; si una migración debe revertirse: `docker compose exec api alembic downgrade -1` tras backup).

## Rollback de modelo
UI: *Redes neuronales → Registro de modelos → Rollback*, o `POST /api/v1/ml/networks/{key}/rollback`. Vuelve a producción la última versión aprobada; queda en auditoría (`model.rollback`).

## Backup y restauración (RPO ≤ 24 h, RTO ≤ 4 h)
```bash
BACKUP_PASSPHRASE=... ./scripts/backup.sh                 # pg_dump cifrado AES-256
BACKUP_PASSPHRASE=... ./scripts/restore.sh backups/x.dump.enc
make smoke
```
Programar `backup.sh` diario (cron). Probar restauración mensualmente en staging. Volúmenes `mlartifacts` y `mldata`: copiar con `docker run --rm -v edumaster-ai_mlartifacts:/a -v $PWD/backups:/b alpine tar czf /b/artifacts.tgz /a`. En Supabase activar PITR.

## Incidentes
| Síntoma | Diagnóstico | Acción |
|---|---|---|
| Chip «Sin conexión» | `docker compose logs api` / Redis caído | El navegador reconecta solo; reiniciar `redis`/`api` |
| Entrenamiento en cola indefinida | `docker compose logs worker` | Reiniciar `worker`; el run queda en `queued` y se puede relanzar |
| 503 «Servicio de inferencia no disponible» | `docker compose ps ml` | La API degrada; reiniciar `ml` |
| Cadena de auditoría inválida | *Administración → Auditoría → Verificar integridad* | Preservar evidencia, restaurar backup, escalar a seguridad |
| Drift de features (PSI > 0.25) | `edumaster_ml.monitoring.drift` | Reentrenar con dataset nuevo y pasar por aprobación |

Cada respuesta de error incluye `correlation_id`, que aparece en los logs estructurados de la API.
