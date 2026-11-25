# EduMaster.ai — Plataforma empresarial de aprendizaje inteligente (edición Nebula)

**Aprende • Practica • Destaca.** Gestión académica, analítica en tiempo real y **cinco redes neuronales PyTorch** gobernadas (versionadas, con baseline, model card, aprobación y rollback), con un visualizador que muestra la topología real y enciende las **sinapsis** cuando llega una inferencia o una época de entrenamiento.

> Todos los datos incluidos están rotulados **DEMO** (sintéticos). Se sustituyen por datos institucionales sin rehacer la interfaz.

## Arranque rápido con Docker

```bash
make setup          # crea .env con secretos aleatorios (scripts/gen-secrets.sh --write)
make up             # docker compose up -d --build
```

| Servicio | URL |
|---|---|
| Aplicación web | http://localhost:8080 |
| API + OpenAPI interactivo | http://localhost:8000/api/docs |
| Métricas Prometheus | http://localhost:8000/metrics |
| MLflow (`--profile mlops`) | http://localhost:5000 |
| Grafana (`--profile monitoring`) | http://localhost:3000 |

En el primer arranque la API aplica migraciones, carga datos DEMO y **encola el entrenamiento de las 5 redes** en el worker. Abre *Redes neuronales* y verás las curvas de pérdida y la retropropagación en vivo (≈1–2 min en CPU).

### Cuentas demo (contraseña `EduMaster#2026`)

| Rol | Correo |
|---|---|
| Superadministrador | superadmin@edumaster.ai |
| Administrador institucional | admin@edumaster.ai |
| Coordinador | coordinador@edumaster.ai |
| Docente | docente@edumaster.ai |
| Estudiante | estudiante@edumaster.ai |
| Analista de datos | analista@edumaster.ai |
| ML Engineer | ml@edumaster.ai |
| Auditor | auditor@edumaster.ai |
| Otra institución (pruebas de aislamiento) | admin@andino.edu / estudiante@andino.edu |

Cambia `DEMO_PASSWORD` y pon `SEED_DEMO_DATA=false` antes de usar datos reales.

## Supabase

```bash
# 1. En .env: SUPABASE_DATABASE_URL (Session Pooler 5432), SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET
make supabase        # migraciones + RLS + auditoría inmutable + bucket privado + datos DEMO
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build
```
Guía paso a paso: [`docs/DEPLOY_SUPABASE.md`](docs/DEPLOY_SUPABASE.md).

## Vercel + Supabase + Render

`render.yaml` (Blueprint: API, ML+worker con disco, Key Value) y `apps/web/vercel.json` incluidos. Guía: [`docs/DEPLOY_VERCEL_SUPABASE_RENDER.md`](docs/DEPLOY_VERCEL_SUPABASE_RENDER.md).

## Las 5 redes neuronales

| Red | Arquitectura | Métrica (test) | Baseline | Parámetros |
|---|---|---|---|---|
| `edumaster_mtl` | Dense tabular + GRU temporal → fusión LayerNorm/Dropout → 4 cabezas (finalización, dominio, riesgo, ranking) | compuesta 0.706 | 0.676 | 13 131 |
| `completion_mlp` | MLP calibrado (temperature scaling) | ROC-AUC 0.964 | 0.962 | 1 005 |
| `mastery_ordinal` | Red ordinal CE + EMD² (5 niveles) | macro-F1 0.642 | 0.631 | 2 281 |
| `risk_transformer` | Transformer Encoder (2 bloques, 4 cabezas) + contexto | PR-AUC 0.853 | 0.850 | 18 945 |
| `reco_ranker` | Two-tower con interacción u⊙v, pérdida BPR + ListNet | NDCG@5 0.988 | 0.263 (popularidad) | 1 693 |

Cifras del dataset DEMO (no son resultados educativos reales). Fichas completas en [`docs/model-cards/`](docs/model-cards/). Una versión **solo se publica si supera su baseline interpretable** o con justificación auditada.

## Arquitectura

```
apps/
  web/   React 19 + TypeScript + Vite + Tailwind 4 + TanStack Query + Zustand + ECharts + Canvas 2D
  api/   FastAPI (monolito modular por dominios) + SQLAlchemy 2 + Alembic + JWT + RBAC/ABAC + Outbox + SSE
  ml/    PyTorch: dataset DEMO, pipeline DataOps de 10 pasos, 5 redes, baselines, servicio de inferencia y worker RQ
infra/   SQL de Supabase (esquema + RLS), Prometheus, Grafana
docs/    arquitectura, API, diccionario de datos, datasheet, model cards, runbooks, seguridad y trazabilidad
```
Detalle y diagrama: [`docs/architecture/ARQUITECTURA.md`](docs/architecture/ARQUITECTURA.md). Cumplimiento punto por punto de los dos documentos de requisitos: [`docs/TRAZABILIDAD.md`](docs/TRAZABILIDAD.md).

## APIs externas (opcionales)

| Integración | Variable | Uso |
|---|---|---|
| Anthropic Claude | `AI_TUTOR_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` | IA Tutor generativo |
| OpenAI o compatible (Groq, OpenRouter, Ollama…) | `AI_TUTOR_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` | IA Tutor generativo |
| Supabase | `SUPABASE_*` | PostgreSQL gestionado, Storage, aceptación de JWT de Supabase Auth |
| DiceBear | — | Avatares generados |
| Google Fonts | — | Tipografías Sora e Inter |

Sin claves, el tutor funciona con reglas y las recomendaciones del modelo propio.

## Desarrollo local sin Docker

```bash
# Requisitos: Python 3.13, Node 22, PostgreSQL 16, Redis 7
cd apps/api && pip install -r requirements.txt && alembic upgrade head && python -m app.seed && uvicorn app.main:app --port 8000
cd apps/ml && pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
PYTHONPATH=src uvicorn edumaster_ml.inference.service:app --port 8001 &   PYTHONPATH=src rq worker training
cd apps/web && npm install && npm run dev      # http://localhost:5173 (proxy /api → :8000)
```

## Pruebas

```bash
make test     # API (19), ML (9), web (typecheck + vitest + build)
make smoke    # smoke tests post-despliegue
```
