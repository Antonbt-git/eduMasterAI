# EduMaster.ai — Manual de uso

Guía práctica para **iniciar** y **trabajar** con la plataforma. Todo el material incluido está rotulado **DEMO** (datos sintéticos) hasta que se sustituyan por datos institucionales autorizados.

---

## 1. Requisitos previos

| Elemento | Detalle |
|---|---|
| Node.js | ≥ 22 (`nvm use 22`) |
| Python | 3.12 |
| Docker (opcional) | 24+ con permisos de usuario en el grupo `docker` |
| Supabase (opcional) | Proyecto con *Session Pooler* (puerto 5432) para datos remotos |
| GPU | No necesaria (entrenamiento CPU ≈ 1–2 min para las 5 redes) |

---

## 2. Cómo iniciar

### Opción A — Docker (recomendado para local completo)

```bash
make setup    # crea .env con secretos aleatorios
make up       # postgres + redis + api + ml + worker + web
```

| Servicio | URL |
|---|---|
| Web | http://localhost:8080 |
| API + OpenAPI | http://localhost:8000/api/docs |
| Métricas | http://localhost:8000/metrics |

En el primer arranque la API aplica migraciones, carga los datos DEMO y **encola el entrenamiento** de las 5 redes.

### Opción B — Supabase (la que se usó en la revisión final)

```bash
# 1. Configura .env con:
#    SUPABASE_DATABASE_URL  (Session Pooler 5432, driver psycopg)
#    SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_JWT_SECRET
#    ML_SERVICE_URL, CORS_ORIGINS, JWT_SECRET, INTERNAL_SERVICE_TOKEN

# 2. Migraciones + seguridad RLS + datos DEMO
./scripts/supabase_deploy.sh              # con datos DEMO
./scripts/supabase_deploy.sh --no-seed    # sin datos (producción)

# 3. Levantar el stack apuntando a Supabase
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build
```

Detalle completo: [`docs/DEPLOY_SUPABASE.md`](DEPLOY_SUPABASE.md).

### Opción C — Manual sin Docker (desarrollo rápido)

```bash
# API (puerto 8000)
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://<usuario>:<clave>@<host>:5432/postgres?sslmode=require"
export REDIS_URL="" ML_SERVICE_URL="http://127.0.0.1:8001" DEMO_SIMULATOR=false BOOTSTRAP_TRAINING=false
alembic upgrade head
python -m app.seed                 # datos DEMO (idempotente)
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Servicio de inferencia (puerto 8001)
cd apps/ml
python -m venv .venv && . .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
PYTHONPATH=src ML_DATA_DIR=./data ML_ARTIFACT_DIR=./artifacts \
  uvicorn edumaster_ml.inference.service:app --port 8001

# Frontend (puerto 5173)
cd apps/web
npm install
npm run dev
```

> **Nota:** el seed contra un pooler lento puede tardar; desactiva el límite de sentencias
> (`SET statement_timeout = 0`, ya lo hace `app.seed`) y no ejecutes dos seeds a la vez.

---

## 3. Credenciales

Contraseña DEMO: **`EduMaster#2026`** (cambiar `DEMO_PASSWORD` y `SEED_DEMO_DATA=false` con datos reales).

| Rol | Correo |
|---|---|
| Superadministrador | `superadmin@edumaster.ai` |
| Administrador institucional | `admin@edumaster.ai` |
| Coordinador | `coordinador@edumaster.ai` |
| Docente | `docente@edumaster.ai` |
| Estudiante | `estudiante@edumaster.ai` |
| Analista | `analista@edumaster.ai` |
| ML Engineer | `ml@edumaster.ai` |
| Auditor | `auditor@edumaster.ai` |
| Otra institución (aislamiento) | `admin@andino.edu` |

---

## 4. Cómo trabajar (módulos)

| Ruta | Módulo | Qué se hace |
|---|---|---|
| `/` | **Resumen** | KPIs, tendencias, mapa, finalización, heatmap, recomendaciones y actividad. Filtros de periodo; datos en vivo por eventos (SSE). |
| `/rutas` | **Planes de aprendizaje** | Crear rutas, competencias, prerrequisitos y asignarlas a cohortes. |
| `/cursos` | **Cursos** | Catálogo, unidades, lecciones, publicación y matrículas. |
| `/analisis` | **Análisis** | Indicadores por institución/curso/cohorte, filtros de fecha y **exportación CSV/XLSX/PDF** con marca de filtros. |
| `/tutor` | **IA Tutor** | Consultas con proveedor configurable (`AI_TUTOR_PROVIDER`). Sin proveedor = modo DEMO. |
| `/evaluaciones` | **Evaluaciones** | Bancos, rúbricas, intentos y calificación oficial (separada de la estimación IA). |
| `/certificados` | **Certificados** | Emisión, folio único, PDF/QR y **portal público de verificación** (`/verificar`). |
| `/comunidad` | **Comunidad** | Hilos, anuncios, moderación y notificaciones. |
| `/habilidades` | **Dominio de habilidades** | Heatmap por competencia/nivel (5 niveles), evidencia IA **vs** evidencia docente. |
| `/redes` | **Redes neuronales** | Topología real de las 5 redes, pesos, activaciones, inspector de capa e **inferencia real**. |
| `/recomendaciones` | **Recomendaciones IA** | Lista priorizada, aceptar/descartar/útil y métrica de utilidad. |
| `/actividad` | **Actividad** | Feed de eventos autorizados y centro de notificaciones. |
| `/administracion` | **Administración** | Usuarios, roles, catálogos, datasets, modelos y auditoría. |
| `/configuracion` | **Configuración** | Parámetros institucionalales, branding y preferencias. |

Cada menú se muestra/oculta por **permiso** (`perm:` en `AppShell.tsx`), pero la **autorización real siempre es en backend**.

### Flujo de trabajo típico (administrador)

1. Entrar con `admin@edumaster.ai`.
2. **Resumen** → revisar KPIs y actividad reciente.
3. **Cursos** → crear curso → publicar → asignar docente.
4. **Evaluaciones** → crear evaluación y publicarla.
5. **Análisis** → filtrar por curso/periodo y exportar.
6. **Redes neuronales** → verificar modelo en producción y ejecutar inferencia.
7. **Administración** → revisar auditoría y modelos registrados.

---

## 5. Redes neuronales (trabajo diario)

### Ver la topología
`/redes` → las 5 tarjetas muestran topología (miniatura, sin pesos) y la versión en producción.
El panel inferior permite: **seleccionar versión**, **mostrar/ocultar pesos**, **inspeccionar capa**, **cambiar velocidad**, **pausar/reiniciar**.

### Ejecutar inferencia real
Botón **«Ejecutar inferencia real»** → elige un ejemplo DEMO → devuelve probabilidad de finalización, riesgo, distribución de dominio, ranking de recursos y explicación (latencia ≈ 7 ms).

### Entrenar y publicar una versión
```bash
# Entrenar localmente (CPU)
cd apps/ml
PYTHONPATH=src ML_DATA_DIR=./data ML_ARTIFACT_DIR=./artifacts \
  python -m edumaster_ml.training.train --network all --config configs/edumaster_mtl.yaml

# Registrar la versión en producción (BD)
cd apps/api
ML_ARTIFACT_DIR=../ml/artifacts python -m scripts.register_models
```
Reinicia el servicio ML y la API para que sirvan la nueva versión.
Los artefactos viven en `apps/ml/artifacts/<red>/<versión>/` (`model.pt`, `meta.json`, `metrics.json`).

---

## 6. Datos DEMO y seed

```bash
# Recrear/actualizar datos DEMO (idempotente; reinicia si están incompletos)
cd apps/api
python -m app.seed
```
- Fase 1: instituciones, usuarios, cursos, estudiantes.
- Fase 2: matrículas, intentos, evidencias.
- Fase 3: métricas diarias (alimenta el dashboard).
- Fase 4: certificados, rutas, comunidad, notificaciones.
- Fase final: ~41 000 eventos en lotes (en segundo plano).

---

## 7. Pruebas y calidad

```bash
make test        # api + ml + web
make test-api    # pytest apps/api
make test-ml     # pytest apps/ml
make test-web    # npm test + typecheck + build
make smoke       # ./scripts/smoke.sh (sanity del stack levantado)
```

---

## 8. Operación

| Acción | Comando |
|---|---|
| Ver logs | `make logs` |
| Parar | `make down` |
| Backup | `./scripts/backup.sh` |
| Restaurar | `./scripts/restore.sh <archivo>` |
| Verificar restauración | `./scripts/verify-restore.sh` |
| Regenerar secretos | `make secrets` |

---

## 9. Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `Redes neuronales` vacío | Servicio ML caído → comprobar `curl http://127.0.0.1:8001/health` y `ML_SERVICE_URL`. |
| `429 Too Many Requests` en producción | Throttling del proxy (p. ej. Render). Se añadieron reintentos con backoff y un endpoint batched `/ml/networks/topologies`. |
| `max clients reached in session mode` | Pool de Supabase agotado → no ejecutar seeds concurrentes; termina sesiones `idle in transaction` (`pg_terminate_backend`). |
| `QueryCanceled ... statement timeout` | Supabase impone timeout → `app.seed` ejecuta `SET statement_timeout = 0`. |
| `duplicate key ... uq_organizations_code` | Seed incompleto → reinicia limpiando `EMA` e `IAT` (ya lo hace el seed). |
| `503 Servicio de inferencia no disponible` | `ML_SERVICE_URL` mal apuntado o ML sin artefactos. |
| Login falla en Supabase | Verificar `SUPABASE_JWT_SECRET`/`JWT_SECRET` y que el usuario exista (`python -m app.seed`). |

---

## 10. Referencias

- Arquitectura: [`docs/architecture/`](architecture/)
- Despliegue Supabase: [`docs/DEPLOY_SUPABASE.md`](DEPLOY_SUPABASE.md)
- Despliegue Vercel + Render: [`docs/DEPLOY_VERCEL_SUPABASE_RENDER.md`](DEPLOY_VERCEL_SUPABASE_RENDER.md)
- Seguridad: [`docs/SEGURIDAD.md`](SEGURIDAD.md)
- QA: [`docs/QA_PLAN.md`](QA_PLAN.md)
- Metodología: [`docs/METODOLOGIA.md`](METODOLOGIA.md)
