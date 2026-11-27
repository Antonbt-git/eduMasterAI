# EduMaster.ai — Manual del responsable

Documento para la **dirección del proyecto**: qué hay, qué falta, cómo se gobierna, cómo se despliega y qué decisiones debe aprobar. Continúa el [`MANUAL_USO.md`](MANUAL_USO.md) (uso diario) y complementa la [`Guía de arquitectura`](../architecture/ARQUITECTURA.md).

---

## 1. Qué es la plataforma hoy

**EduMaster.ai** es una plataforma web empresarial de aprendizaje con analítica en tiempo real y **cinco redes neuronales PyTorch** gobernadas (versionadas, con baseline, model card, aprobación y rollback).

| Capa | Estado | Detalle |
|---|---|---|
| Frontend React | ✅ Operativo | 14 módulos, tema oscuro, responsive, accesibilidad AA parcial |
| API FastAPI | ✅ Operativa | RBAC multi-institución, JWT con rotación, auditoría con hash encadenado |
| PostgreSQL / Supabase | ✅ Operativo | Migraciones Alembic, RLS, auditoría inmutable, bucket privado |
| Realtime (SSE) | ✅ Operativo | Outbox → Redis → SSE autorizado, reconexión con `Last-Event-ID` |
| ML — inferencia | ✅ Operativa | 5 redes en producción, latencia ≈ 7 ms |
| ML — entrenamiento | ✅ Operativo | Worker RQ + PyTorch CPU, registro/ aprobación/ rollback |
| Datos | ⚠️ DEMO | 360 estudiantes, 41 482 eventos, 909 matrículas, 9 421 métricas diarias |
| Despliegue | ⚠️ Parcial | Docker local completo; Render/Supabase con limitaciones de rate limit |

> **Regla:** todos los datos están rotulados **DEMO** (sintéticos). Se sustituyen por datos institucionales sin rehacer la interfaz.

---

## 2. Decisiones que debe aprobar el responsable

| # | Decisión | Recomendación |
|---|---|---|
| 1 | Objetivo predictivo inicial | Finalización de curso (etiqueta observable y con ventana temporal) |
| 2 | Umbral de revisión humana | Toda recomendación con impacto académico requiere confirmación docente |
| 3 | Política de privacidad y retención | Definir antes de ingestar datos reales; conservación mínima |
| 4 | Procedimiento de aprobación de modelos | Dos personas (revisor + aprobador), artefactos inmutables, revocación auditada |
| 5 | Datos institucionales | Autorizar historial lícito, completo, seudonimizado y documentado |
| 6 | Infraestructura y dominio | Proveedor, TLS, copias de seguridad y recuperación |
| 7 | UAT | Cuentas de prueba con personal académico, sin usar predicciones experimentales |

**No habilitar `EDUMASTER_ML_INFERENCE_ENABLED` ni promover modelos a producción hasta completar la validación independiente.**

---

## 3. Roles y permisos

| Rol | Responsabilidad | Permisos clave |
|---|---|---|
| Superadministrador | Gobierno global, tenants, auditoría | Todos |
| Administrador institucional | Operación de la institución | Usuarios, cursos, reportes, configuración |
| Director / coordinador | Seguimiento académico | Cohortes, alertas, reportes |
| Docente | Gestión de enseñanza | Sus cursos y grupos |
| Estudiante | Aprendizaje | Registros propios |
| Analista | Analítica y datasets | Datos seudonimizados, agregados |
| ML Engineer | Ciclo de vida del modelo | Entrenar y registrar (no aprobar) |
| Auditor | Control y cumplimiento | Lectura de bitácoras, sin modificación |

La autorización se valida **siempre en backend**; ocultar un botón en React no es seguridad. Cada módulo comprueba permiso **e** institución (aislamiento multi-tenant).

---

## 4. Cómo desplegar

### Local (Docker)
```bash
make setup && make up      # .env con secretos + stack completo
make smoke                 # health, login, dashboard, 5 redes
```

### Supabase (datos remotos)
```bash
./scripts/supabase_deploy.sh              # migraciones + RLS + datos DEMO
./scripts/supabase_deploy.sh --no-seed    # sin datos (producción)
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build
```

### Producción (Vercel + Supabase + Render)
Blueprint en `render.yaml` + `apps/web/vercel.json`. Guía: `docs/DEPLOY_VERCEL_SUPABASE_RENDER.md`.

**Ambientes:** `local` → `development` → `staging` → `production` (variable `ENVIRONMENT`). En staging/producción la API rechaza secretos débiles y desactiva la promoción automática de modelos.

---

## 5. Operación diaria

| Tarea | Frecuencia | Comando / acción |
|---|---|---|
| Verificar salud | Diaria | `make smoke` |
| Backup cifrado | Diaria (cron) | `BACKUP_PASSPHRASE=… ./scripts/backup.sh` |
| Restauración de prueba | Mensual | `./scripts/restore.sh <archivo>` en staging |
| Revés de modelo | Según métricas | UI *Redes neuronales → Rollback* |
| Drift de features | Mensual | PSI > 0.25 ⇒ reentrenar y pasar por aprobación |
| Regenerar secretos | Solo incidencia | `make secrets` |

Runbooks completos: [`docs/runbooks/OPERACION.md`](runbooks/OPERACION.md) y [`RESTAURACION.md`](runbooks/RESTAURACION.md). Objetivos **RPO ≤ 24 h**, **RTO ≤ 4 h**.

---

## 6. Entregables del documento maestro (§18)

| Entregable | Estado |
|---|---|
| Documento de requisitos | ✅ `docs/REQUISITOS.md` + especificación |
| Diseño UX/UI | ✅ Tema Nebula, componentes, responsive, estados vacíos/carga/error |
| Código frontend | ✅ 14 módulos con rutas protegidas y pruebas |
| Código backend | ✅ API versionada, RBAC, OpenAPI en `/api/docs` |
| Base de datos | ✅ Migraciones, índices, ERD, backup/restore |
| Dataset | ✅ DEMO rotulado + datasheet + manifiestos SHA-256 |
| Pipeline ML | ✅ ETL, validación, features, split temporal, reproducibilidad |
| Modelo | ✅ 5 redes, baseline, model card, registro y aprobación |
| Visualizador neuronal | ✅ Canvas con topología y estados reales |
| Realtime | ✅ Contratos de eventos, autorización, reconexión |
| Seguridad | ✅ Matriz de permisos, pruebas, auditoría inmutable |
| QA | ✅ Suite automatizada; **UAT pendiente** |
| Operación | ✅ Docker, CI, observabilidad, runbooks, backup |

---

## 7. Brechas y riesgos abiertos

1. **PostgreSQL 16 en local no validado con Docker en este entorno** (permisos del daemon). Supabase sí verificado.
2. **UAT y accesibilidad** sin aceptación formal.
3. **Datos reales**: sin ellos, las métricas no acreditan desempeño predictivo.
4. **Rate limit en Render** (plan gratuito): la UI de redes dispara varias peticiones; ya hay reintentos con backoff y endpoint batched, pero conviene subir de plan.
5. **IA Tutor** sin proveedor LLM configurado (modo DEMO).
6. **CI en GitHub Actions** propuesta (`ci.yml`), no ejecutada en este entorno.

---

## 8. Checklist previo a producción

- ☐ Alcance, roles y criterios de aceptación firmados.
- ☐ `ENVIRONMENT=production` y secretos fuertes (sin valores por defecto).
- ☐ `SEED_DEMO_DATA=false` y `DEMO_PASSWORD` cambiado.
- ☐ Datos institucionales autorizados, seudonimizados y con base legal.
- ☐ Modelo validado temporalmente, aprobado por dos personas y con rollback probado.
- ☐ Backup diario programado y restauración probada en staging.
- ☐ TLS, dominio y monitorización activos.
- ☐ UAT completado con personal académico.
