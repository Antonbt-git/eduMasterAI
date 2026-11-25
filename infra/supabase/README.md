# Supabase

| Archivo | Uso |
|---|---|
| `001_schema.sql` | Esquema completo generado desde las migraciones Alembic (`alembic upgrade head --sql`). Equivale a la migración `0001`. |
| `002_rls_security.sql` | RLS activado en todas las tablas, revocación de acceso a `anon`/`authenticated`, auditoría inmutable y bucket privado. |

La forma recomendada es **no** pegar el SQL a mano sino ejecutar `scripts/supabase_deploy.sh`, que corre Alembic contra Supabase (deja la tabla `alembic_version` coherente para futuras migraciones), aplica `002_rls_security.sql` y carga los datos DEMO. Ver `docs/DEPLOY_SUPABASE.md`.
