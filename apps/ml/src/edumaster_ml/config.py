"""Configuración del paquete ML (12-factor: todo por variables de entorno)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _path(env: str, default: str) -> Path:
    p = Path(os.getenv(env, default)).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class MLSettings:
    data_dir: Path = field(default_factory=lambda: _path("ML_DATA_DIR", "./data"))
    artifact_dir: Path = field(default_factory=lambda: _path("ML_ARTIFACT_DIR", "./artifacts"))
    api_internal_url: str = (lambda v: v if "://" in v else f"http://{v}")(os.getenv("API_INTERNAL_URL", "http://api:8000").rstrip("/"))
    internal_token: str = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me-internal-token")
    mlflow_uri: str | None = os.getenv("MLFLOW_TRACKING_URI") or None
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    seed: int = int(os.getenv("ML_SEED", "42"))
    # Supabase Storage / S3 compatible (opcional) para artefactos
    s3_endpoint: str | None = os.getenv("S3_ENDPOINT_URL") or None
    s3_bucket: str = os.getenv("S3_BUCKET", "edumaster-artifacts")


settings = MLSettings()

SKILLS = [
    "Inteligencia Artificial",
    "Machine Learning",
    "Ciencia de Datos",
    "Desarrollo Web",
    "Nube y DevOps",
]
MASTERY_LEVELS = ["Principiante", "Elemental", "Intermedio", "Avanzado", "Experto"]
N_RESOURCES = 24
SEQ_WEEKS_OBSERVED = 8
TOTAL_WEEKS = 12
