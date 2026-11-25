"""Logs estructurados (JSON), correlation_id por solicitud y errores normalizados."""
from __future__ import annotations

import contextvars
import logging
import time
import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

# CSP por tipo de respuesta: la API no debe cargar recursos; la documentación
# interactiva (Swagger UI) sí necesita sus CDN habituales.
_DOCS_PATHS = ("/api/docs", "/redoc", "/api/v1/openapi.json")
_CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_CSP_DOCS = ("default-src 'self' https://cdn.jsdelivr.net https://unpkg.com; img-src 'self' data: https:; "
             "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
             "frame-ancestors 'none'; base-uri 'self'")


def _csp(path: str) -> str:
    return _CSP_DOCS if path.startswith(_DOCS_PATHS) else _CSP_API


def configure_logging(env: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer() if env != "local" else structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


log = structlog.get_logger("edumaster")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or uuid.uuid4().hex
        correlation_id_var.set(cid)
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = cid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _csp(request.url.path)
        if settings.environment in ("staging", "production"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if not request.url.path.endswith("/stream"):
            log.info("http", method=request.method, path=request.url.path, status=response.status_code,
                     ms=round((time.perf_counter() - t0) * 1000, 1))
        structlog.contextvars.clear_contextvars()
        return response


def error_body(code: str, message: str, details=None) -> dict:
    return {"code": code, "message": message, "details": details, "correlation_id": correlation_id_var.get()}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exc(_req, exc: HTTPException):
        code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict",
                422: "validation_error", 429: "rate_limited"}.get(exc.status_code, "error")
        msg = exc.detail if isinstance(exc.detail, str) else "Error"
        details = None if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(error_body(code, msg, details), status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation(_req, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(error_body("validation_error", "Datos inválidos", details), status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(_req, exc: Exception):
        log.exception("unhandled", error=str(exc))
        return JSONResponse(error_body("internal_error", "Error interno. Reporte el correlation_id."), status_code=500)
