# Despliegue con Supabase

Supabase aporta PostgreSQL gestionado (con backups) y Storage. Redis, la API, el servicio ML, el worker y la web siguen en contenedores (cualquier VPS, Railway, Render, Fly.io, ECS o Kubernetes).

## 1. Crear el proyecto
1. En https://supabase.com crea un proyecto y guarda la **contraseña de la base de datos**.
2. En *Project Settings → Database → Connection string* elige **Session pooler** (puerto 5432; el transaction pooler 6543 no admite las sentencias preparadas de SQLAlchemy).
3. En *Project Settings → API* copia `Project URL`, la clave `anon` y el **JWT Secret**.

## 2. Completar `.env`
```env
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_JWT_SECRET=<JWT secret>
SUPABASE_DATABASE_URL=postgresql+psycopg://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require
ENVIRONMENT=production
PUBLIC_WEB_URL=https://tu-dominio
CORS_ORIGINS=https://tu-dominio
SEED_DEMO_DATA=false          # true solo para una demo
BOOTSTRAP_TRAINING=true       # entrena las 5 redes al inicio (la promoción automática se desactiva en producción)
```
Genera `JWT_SECRET` e `INTERNAL_SERVICE_TOKEN` con `./scripts/gen-secrets.sh --write`. En `staging`/`production` la API **se niega a arrancar** con secretos débiles.

## 3. Migrar y asegurar
```bash
docker compose build api
./scripts/supabase_deploy.sh            # con datos DEMO
./scripts/supabase_deploy.sh --no-seed  # producción
```
El script ejecuta `alembic upgrade head`, aplica `infra/supabase/002_rls_security.sql` (RLS en todas las tablas, sin acceso para `anon`/`authenticated`, auditoría inmutable y bucket privado `edumaster-artifacts`) y opcionalmente carga los datos DEMO.

Alternativa manual: pega `infra/supabase/001_schema.sql` y luego `002_rls_security.sql` en el *SQL Editor*.

## 4. Levantar el stack
```bash
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build
./scripts/smoke.sh https://tu-dominio
```

## 5. Supabase Auth (opcional)
Con `SUPABASE_JWT_SECRET` configurado, la API acepta también tokens emitidos por Supabase Auth y los asocia al usuario con el mismo correo. Los permisos siguen viniendo de los roles de EduMaster.

## Notas de seguridad
- Nunca subas `.env` al repositorio; usa el gestor de secretos de tu plataforma.
- La clave `service_role` no es necesaria para la API (usa la conexión de base de datos).
- Activa *Point-in-Time Recovery* en Supabase para RPO menor a 24 h.
