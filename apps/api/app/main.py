"""EduMaster.ai — API FastAPI (monolito modular por dominios)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from .api.v1.router import api_router
from .core.config import settings
from .core.infra import store
from .core.observability import CorrelationMiddleware, configure_logging, install_error_handlers, log
from .db.base import SessionLocal, engine
from .modules.realtime import outbox_publisher
from .workers.simulator import run_simulator

configure_logging(settings.environment)

if settings.environment in ("staging", "production"):
    weak = [n for n, v in (("JWT_SECRET", settings.jwt_secret), ("INTERNAL_SERVICE_TOKEN", settings.internal_service_token))
            if v.startswith(("dev-only", "change-me", "cambia")) or len(v) < 32]
    if weak:
        raise RuntimeError(f"Secretos inseguros en {settings.environment}: {', '.join(weak)}. Use scripts/gen-secrets.sh")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    tasks = [asyncio.create_task(outbox_publisher(stop))]
    if settings.demo_simulator:
        tasks.append(asyncio.create_task(run_simulator(stop)))
    try:
        from .modules.ml import bootstrap_if_needed

        with SessionLocal() as db:
            bootstrap_if_needed(db)
    except Exception as exc:
        log.warning("bootstrap_training_skipped", error=str(exc))
    log.info("api_started", env=settings.environment)
    yield
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Plataforma empresarial de aprendizaje inteligente y redes neuronales. Contratos OpenAPI versionados (/api/v1).",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/v1/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Correlation-Id", "Content-Disposition"])
app.add_middleware(CorrelationMiddleware)
install_error_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)

try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(excluded_handlers=["/metrics", "/health.*", ".*/stream"]).instrument(app).expose(app, include_in_schema=False)
except ImportError:  # pragma: no cover
    pass


@app.get("/health/live", tags=["Operación"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Operación"])
def ready():
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
    checks["redis"] = "ok" if (store.r and store.r.ping()) else ("memoria" if not settings.redis_url else "error")
    try:
        checks["ml_service"] = "ok" if httpx.get(f"{settings.ml_service_url}/health", timeout=2).status_code == 200 else "error"
    except Exception:
        checks["ml_service"] = "no disponible (degradado)"
    ok = checks["database"] == "ok"
    return {"status": "ready" if ok else "degraded", "checks": checks}
