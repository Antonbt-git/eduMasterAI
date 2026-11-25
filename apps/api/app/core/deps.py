"""Contexto de autorización: autenticación, RBAC y ABAC (institución, curso asignado, propiedad).

Toda autorización ocurre en backend: ocultar un botón en React no es seguridad.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.base import get_db
from ..db.models import CourseOffering, Enrollment, Instructor, Student, User
from .config import settings
from .infra import store
from .security import decode_supabase_token, decode_token


@dataclass
class Principal:
    user: User
    org_id: uuid.UUID
    roles: set[str]
    permissions: set[str]
    student_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None
    ip: str | None = None
    _course_cache: set | None = field(default=None, repr=False)

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    @property
    def is_student_only(self) -> bool:
        return self.roles == {"student"}

    def instructor_course_ids(self, db: Session) -> set[uuid.UUID]:
        if self._course_cache is None:
            self._course_cache = set()
            if self.instructor_id:
                self._course_cache = set(db.scalars(select(CourseOffering.course_id).where(CourseOffering.instructor_id == self.instructor_id)))
        return self._course_cache

    @property
    def scoped_to_assigned_courses(self) -> bool:
        """Docente sin rol de gestión ⇒ ABAC por cursos asignados."""
        return "instructor" in self.roles and not (self.roles & {"admin", "superadmin", "coordinator"})

    def can_see_student(self, db: Session, student: Student) -> bool:
        if student.organization_id != self.org_id:
            return False
        if self.student_id == student.id:
            return True
        if self.is_student_only:
            return False
        if self.scoped_to_assigned_courses:
            courses = self.instructor_course_ids(db)
            return db.scalar(select(Enrollment.id).where(Enrollment.student_id == student.id, Enrollment.course_id.in_(courses)).limit(1)) is not None
        return self.has("users:read") or self.has("grades:read_all") or self.has("analytics:read")


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)


def build_principal(db: Session, user: User, ip: str | None = None) -> Principal:
    if user.status != "active":
        raise HTTPException(403, "Usuario inactivo")
    roles = {r.code for r in user.roles}
    perms = {p.code for r in user.roles for p in r.permissions}
    st = db.scalar(select(Student.id).where(Student.user_id == user.id))
    ins = db.scalar(select(Instructor.id).where(Instructor.user_id == user.id))
    return Principal(user=user, org_id=user.organization_id, roles=roles, permissions=perms, student_id=st, instructor_id=ins, ip=ip)


def get_principal(request: Request, db: Session = Depends(get_db), authorization: str = Header(default="")) -> Principal:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "No autenticado", headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:]
    user = None
    try:
        data = decode_token(token, "access")
        user = db.get(User, uuid.UUID(data["sub"]))
        if user and data.get("tv") != user.token_version:
            raise HTTPException(401, "Sesión revocada")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.PyJWTError:
        sb = decode_supabase_token(token)
        if sb and sb.get("email"):
            user = db.scalar(select(User).where(User.email == sb["email"].lower()))
    if not user:
        raise HTTPException(401, "Token inválido")
    p = build_principal(db, user, _client_ip(request))
    # Superadmin puede operar sobre otra institución explícitamente
    org_hdr = request.headers.get("X-Organization-Id")
    if org_hdr and "superadmin" in p.roles:
        p.org_id = uuid.UUID(org_hdr)
    # Rate limiting por usuario
    if store.hit(f"rl:u:{user.id}", 60) > settings.rate_limit_per_minute:
        raise HTTPException(429, "Demasiadas solicitudes, intente en un minuto")
    request.state.principal = p
    return p


def require(*perms: str):
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        missing = [x for x in perms if not p.has(x)]
        if missing:
            raise HTTPException(403, f"Permiso requerido: {', '.join(missing)}")
        return p

    return dep


def require_any(*perms: str):
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if not any(p.has(x) for x in perms):
            raise HTTPException(403, f"Se requiere uno de: {', '.join(perms)}")
        return p

    return dep


def internal_only(x_internal_token: str = Header(default="")) -> None:
    if x_internal_token != settings.internal_service_token:
        raise HTTPException(401, "Token interno inválido")
