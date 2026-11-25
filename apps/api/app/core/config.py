"""Configuración externa por ambiente (12-factor). Secretos SOLO por variables de entorno."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "EduMaster.ai API"
    environment: str = Field("local", description="local | development | staging | production")
    api_prefix: str = "/api/v1"
    public_web_url: str = "http://localhost:8080"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Base de datos (PostgreSQL local o Supabase)
    database_url: str = "postgresql+psycopg://edumaster:edumaster@localhost:5432/edumaster"
    db_pool_size: int = 10
    db_echo: bool = False

    # Redis (caché, colas, pub/sub realtime). Vacío => modo en memoria (solo desarrollo/tests)
    redis_url: str = ""

    # Seguridad
    jwt_secret: str = "dev-only-change-me-please-32bytes-minimum!!"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    internal_service_token: str = "change-me-internal-token"
    rate_limit_per_minute: int = 240
    login_rate_limit_per_minute: int = 10

    # Supabase (opcional): acepta JWT de Supabase Auth y usa Storage S3
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # ML
    ml_service_url: str = "http://ml:8001"
    training_queue: str = "training"
    default_dataset_version: str = "demo-v1"
    bootstrap_training: bool = True

    # IA Tutor (APIs externas opcionales)
    ai_tutor_provider: str = "none"  # none | anthropic | openai
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Demo
    seed_demo_data: bool = True
    demo_simulator: bool = True
    demo_password: str = "EduMaster#2026"

    @field_validator("ml_service_url", "public_web_url")
    @classmethod
    def _with_scheme(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        return v if "://" in v else f"http://{v}"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
