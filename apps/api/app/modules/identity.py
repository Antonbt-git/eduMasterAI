"""Identity & Access: autenticación, sesiones, usuarios, roles e instituciones."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import Principal, build_principal, get_principal, require
from ..core.events import audit
from ..core.infra import store
from ..core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from ..db.base import get_db
from ..db.models import Instructor, Organization, Role, Student, User
from .common import DTO, get_or_404

router = APIRouter(tags=["Identity & Access"])


# ----------------------------------------------------------------- Schemas
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    organization_code: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(DTO):
    id: uuid.UUID
    email: str
    full_name: str
    status: str
    title: str | None = None
    avatar_url: str | None = None
    roles: list[str] = []
    last_login_at: datetime | None = None


class MeOut(UserOut):
    organization: dict
    permissions: list[str]
    student_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=200)
    roles: list[str] = Field(min_length=1)
    password: str = Field(min_length=10, max_length=128)
    title: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=3, max_length=200)
    roles: list[str] | None = None
    status: str | None = Field(None, pattern="^(active|suspended)$")
    title: str | None = None


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "status": u.status, "title": u.title,
            "avatar_url": u.avatar_url, "last_login_at": u.last_login_at, "roles": [r.code for r in u.roles]}


# ----------------------------------------------------------------- Service
def issue_tokens(u: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(u.id, u.organization_id, [r.code for r in u.roles], u.token_version),
        refresh_token=create_refresh_token(u.id, u.token_version),
        expires_in=settings.access_token_minutes * 60,
    )


def authenticate(db: Session, body: LoginIn, ip: str | None) -> User:
    key = f"rl:login:{ip}:{body.email.lower()}"
    if store.hit(key, 60) > settings.login_rate_limit_per_minute:
        raise HTTPException(429, "Demasiados intentos. Espere un minuto.")
    q = select(User).where(func.lower(User.email) == body.email.lower())
    if body.organization_code:
        q = q.join(Organization).where(Organization.code == body.organization_code)
    users = list(db.scalars(q))
    user = next((u for u in users if verify_password(body.password, u.password_hash)), None)
    if not user:
        audit(db, None, "auth.login_failed", "user", details={"email": body.email.lower(), "ip": ip},
              org_id=users[0].organization_id if users else None, actor_email=body.email.lower())
        db.commit()
        raise HTTPException(401, "Credenciales inválidas")
    if user.status != "active":
        raise HTTPException(403, "Usuario suspendido")
    return user


# ----------------------------------------------------------------- Router
@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    user = authenticate(db, body, ip)
    user.last_login_at = datetime.now(timezone.utc)
    p = build_principal(db, user, ip)
    audit(db, p, "auth.login", "user", user.id)
    db.commit()
    return issue_tokens(user)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        data = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(401, "Refresh token inválido")
    if store.get_json(f"revoked:{data['jti']}"):
        raise HTTPException(401, "Refresh token ya utilizado")
    user = db.get(User, uuid.UUID(data["sub"]))
    if not user or user.token_version != data.get("tv"):
        raise HTTPException(401, "Sesión revocada")
    store.set_json(f"revoked:{data['jti']}", 1, ex=settings.refresh_token_days * 86400)  # rotación
    return issue_tokens(user)


@router.post("/auth/logout", status_code=204)
def logout(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    p.user.token_version += 1  # revoca todos los tokens vigentes
    audit(db, p, "auth.logout", "user", p.id)
    db.commit()


@router.get("/auth/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal)):
    return {**_user_out(p.user), "organization": {"id": str(p.org_id), "name": p.user.organization.name, "code": p.user.organization.code,
                                                  "timezone": p.user.organization.timezone},
            "permissions": sorted(p.permissions), "student_id": p.student_id, "instructor_id": p.instructor_id}


@router.get("/users")
def list_users(q: str | None = None, role: str | None = None, limit: int = 50, offset: int = 0,
               p: Principal = Depends(require("users:read")), db: Session = Depends(get_db)):
    stmt = select(User).where(User.organization_id == p.org_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    if role:
        stmt = stmt.where(User.roles.any(Role.code == role))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(User.full_name).limit(min(limit, 200)).offset(offset)).all()
    return {"items": [_user_out(u) for u in rows], "total": total}


@router.post("/users", status_code=201)
def create_user(body: UserCreate, p: Principal = Depends(require("users:write")), db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.organization_id == p.org_id, func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "Ya existe un usuario con ese email en la institución")
    if "superadmin" in body.roles and "superadmin" not in p.roles:
        raise HTTPException(403, "Solo un superadministrador puede asignar ese rol")
    roles = list(db.scalars(select(Role).where(Role.code.in_(body.roles))))
    if len(roles) != len(set(body.roles)):
        raise HTTPException(422, "Rol inválido")
    u = User(organization_id=p.org_id, email=body.email.lower(), full_name=body.full_name, title=body.title,
             password_hash=hash_password(body.password), roles=roles,
             avatar_url=f"https://api.dicebear.com/9.x/notionists/svg?seed={uuid.uuid4().hex[:8]}")
    db.add(u)
    db.flush()
    if "student" in body.roles:
        db.add(Student(user_id=u.id, organization_id=p.org_id, external_code=f"ST-{u.id.hex[:6].upper()}"))
    if "instructor" in body.roles:
        db.add(Instructor(user_id=u.id, organization_id=p.org_id, staff_code=f"IN-{u.id.hex[:6].upper()}"))
    audit(db, p, "user.created", "user", u.id, {"roles": body.roles})
    db.commit()
    return _user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: UserUpdate, p: Principal = Depends(require("users:write")), db: Session = Depends(get_db)):
    u = get_or_404(db, User, user_id, p.org_id, "Usuario no encontrado")
    changes = body.model_dump(exclude_none=True)
    if body.roles is not None:
        if "superadmin" in body.roles and "superadmin" not in p.roles:
            raise HTTPException(403, "Solo un superadministrador puede asignar ese rol")
        u.roles = list(db.scalars(select(Role).where(Role.code.in_(body.roles))))
        u.token_version += 1
    for k in ("full_name", "status", "title"):
        if getattr(body, k) is not None:
            setattr(u, k, getattr(body, k))
    if body.status == "suspended":
        u.token_version += 1
    audit(db, p, "user.updated" if body.roles is None else "user.roles_changed", "user", u.id, changes)
    db.commit()
    return _user_out(u)


@router.get("/roles")
def list_roles(p: Principal = Depends(require("users:read")), db: Session = Depends(get_db)):
    return [{"code": r.code, "name": r.name, "permissions": sorted(x.code for x in r.permissions)} for r in db.scalars(select(Role))]


@router.get("/organizations")
def list_orgs(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    q = select(Organization) if "superadmin" in p.roles else select(Organization).where(Organization.id == p.org_id)
    return [{"id": o.id, "name": o.name, "code": o.code, "status": o.status, "timezone": o.timezone} for o in db.scalars(q)]


@router.get("/settings")
def get_settings_(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    org = db.get(Organization, p.org_id)
    return {"organization": {"name": org.name, "code": org.code, "timezone": org.timezone},
            "settings": {"demo_simulator": True, "recommendation_threshold": 0.5, "risk_alert_threshold": 0.6, **(org.settings or {})},
            "integrations": {"ai_tutor_provider": settings.ai_tutor_provider, "supabase": bool(settings.supabase_url),
                             "redis": bool(settings.redis_url)}}


class SettingsIn(BaseModel):
    timezone: str | None = None
    demo_simulator: bool | None = None
    recommendation_threshold: float | None = Field(None, ge=0, le=1)
    risk_alert_threshold: float | None = Field(None, ge=0, le=1)


@router.put("/settings")
def put_settings(body: SettingsIn, p: Principal = Depends(require("settings:write")), db: Session = Depends(get_db)):
    org = db.get(Organization, p.org_id)
    data = body.model_dump(exclude_none=True)
    if "timezone" in data:
        org.timezone = data.pop("timezone")
    org.settings = {**(org.settings or {}), **data}
    audit(db, p, "settings.updated", "organization", org.id, body.model_dump(exclude_none=True))
    db.commit()
    return get_settings_(p, db)
