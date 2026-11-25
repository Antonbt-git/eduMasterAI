"""Contraseñas (bcrypt), JWT de vida corta + refresh rotatorio, y verificación opcional de JWT de Supabase."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(raw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _encode(sub: str, kind: str, ttl: timedelta, **extra) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "typ": kind, "iat": now, "exp": now + ttl, "jti": secrets.token_hex(8), **extra}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID, roles: list[str], token_version: int) -> str:
    return _encode(str(user_id), "access", timedelta(minutes=settings.access_token_minutes),
                   org=str(org_id), roles=roles, tv=token_version)


def create_refresh_token(user_id: uuid.UUID, token_version: int) -> str:
    return _encode(str(user_id), "refresh", timedelta(days=settings.refresh_token_days), tv=token_version)


def decode_token(token: str, expected: str) -> dict:
    data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if data.get("typ") != expected:
        raise jwt.InvalidTokenError("tipo de token inválido")
    return data


def decode_supabase_token(token: str) -> dict | None:
    """Acepta tokens emitidos por Supabase Auth si SUPABASE_JWT_SECRET está configurado."""
    if not settings.supabase_jwt_secret:
        return None
    try:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError:
        return None
