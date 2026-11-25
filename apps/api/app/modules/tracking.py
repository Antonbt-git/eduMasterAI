"""Learning Tracking: ingesta idempotente de eventos, progreso y evidencias por estudiante."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_principal, require
from ..core.events import activity, audit
from ..core.infra import store
from ..db.base import get_db
from ..db.models import (
    AssessmentAttempt, Assessment, Course, Enrollment, LearningEvent, Prediction, Skill, SkillEvidence, Student, User,
)
from .common import get_or_404
from .progress import bump_daily, recompute_enrollment

router = APIRouter(tags=["Learning Tracking"])
EVENT_TYPES = {"session_started", "session_ended", "lesson_viewed", "activity_started", "activity_completed", "resource_opened"}


class EventIn(BaseModel):
    event_id: uuid.UUID
    event_type: str
    occurred_at: datetime
    course_id: uuid.UUID | None = None
    activity_id: str | None = Field(None, max_length=80)
    duration_seconds: int = Field(0, ge=0, le=21600, description="Duración acotada; pestaña abierta ≠ atención")
    payload: dict = {}
    payload_schema_version: int = 1
    source: str = Field("web", pattern="^(web|mobile|import|integration|demo-simulator)$")
    student_id: uuid.UUID | None = None

    @field_validator("event_type")
    @classmethod
    def valid_type(cls, v):
        if v not in EVENT_TYPES:
            raise ValueError(f"event_type no soportado: {v}")
        return v

    @field_validator("occurred_at")
    @classmethod
    def not_future(cls, v):
        v = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("occurred_at en el futuro")
        return v.astimezone(timezone.utc)

    @field_validator("payload")
    @classmethod
    def payload_limited(cls, v):
        if len(json.dumps(v, default=str)) > 16_384:
            raise ValueError("payload supera el límite de 16 KB")
        return v


def ingest_event(db: Session, p: Principal | None, body: EventIn, org_id, student: Student) -> dict:
    if db.get(LearningEvent, body.event_id):
        return {"event_id": body.event_id, "status": "duplicate", "idempotent": True}
    if body.course_id:
        enr = db.scalar(select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.course_id == body.course_id))
        if not enr:
            raise HTTPException(403, "Estudiante no matriculado en el curso")
    else:
        enr = None
    ev = LearningEvent(event_id=body.event_id, organization_id=org_id, student_id=student.id, course_id=body.course_id,
                       activity_id=body.activity_id, event_type=body.event_type, occurred_at=body.occurred_at,
                       duration_seconds=body.duration_seconds, payload=body.payload, payload_schema_version=body.payload_schema_version,
                       source=body.source)
    db.add(ev)
    db.flush()
    last_today = db.scalar(select(func.count(LearningEvent.event_id)).where(
        LearningEvent.student_id == student.id, LearningEvent.occurred_at >= body.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)))
    bump_daily(db, org_id, body.course_id or uuid.UUID(int=0), student.region, day=body.occurred_at.date(), events=1,
               seconds=body.duration_seconds, active=1 if last_today == 1 else 0)
    if enr:
        recompute_enrollment(db, enr, p.id if p else None)
        if body.event_type == "session_started" and (enr.last_activity_at is None or last_today == 1):
            activity(db, org_id, "session", f"{student.user.full_name.split()[0]} retomó {db.get(Course, enr.course_id).title}",
                     subject_user_id=student.user_id)
    return {"event_id": body.event_id, "status": "accepted", "progress": enr.progress if enr else None}


@router.post("/learning-events", status_code=202)
def post_event(body: EventIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
               p: Principal = Depends(require("events:ingest")), db: Session = Depends(get_db)):
    if body.student_id and body.student_id != p.student_id and not p.has("courses:write"):
        raise HTTPException(403, "Solo puede registrar eventos propios")
    sid = body.student_id or p.student_id
    if not sid:
        raise HTTPException(422, "student_id requerido")
    student = get_or_404(db, Student, sid, p.org_id, "Estudiante no encontrado")
    # Idempotencia de solicitud completa: misma Idempotency-Key ⇒ misma respuesta (24 h).
    cache_key = f"idem:events:{p.org_id}:{idempotency_key}" if idempotency_key else None
    if cache_key:
        cached = store.get_json(cache_key)
        if cached:
            return {**cached, "replayed": True}
    res = ingest_event(db, p, body, p.org_id, student)
    db.commit()
    if cache_key:
        store.set_json(cache_key, res, ex=86_400)
    return res


# ----------------------------------------------------------------- Estudiantes
def _risk_for(db: Session, student_id) -> float | None:
    pr = db.scalar(select(Prediction).where(Prediction.student_id == student_id, Prediction.network_key.in_(["risk_transformer", "edumaster_mtl"]))
                   .order_by(Prediction.created_at.desc()).limit(1))
    return pr.scores.get("risk_probability") if pr else None


@router.get("/students")
def list_students(q: str | None = None, course_id: uuid.UUID | None = None, region: str | None = None,
                  limit: int = Query(50, le=200), offset: int = 0, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if p.is_student_only:
        raise HTTPException(403, "Sin acceso a otros estudiantes")
    if not (p.has("users:read") or p.has("grades:read_all") or p.has("assessments:write") or p.has("analytics:read")):
        raise HTTPException(403, "Sin permiso")
    stmt = select(Student).join(User, User.id == Student.user_id).where(Student.organization_id == p.org_id)
    if p.scoped_to_assigned_courses:
        stmt = stmt.where(Student.id.in_(select(Enrollment.student_id).where(Enrollment.course_id.in_(p.instructor_course_ids(db)))))
    if course_id:
        stmt = stmt.where(Student.id.in_(select(Enrollment.student_id).where(Enrollment.course_id == course_id)))
    if region:
        stmt = stmt.where(Student.region == region)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like), func.lower(Student.external_code).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    pseudo = "analyst" in p.roles and not (p.roles & {"admin", "superadmin", "coordinator", "instructor"})
    items = []
    for s in db.scalars(stmt.order_by(User.full_name).limit(limit).offset(offset)):
        agg = db.execute(select(func.count(Enrollment.id), func.avg(Enrollment.progress), func.max(Enrollment.last_activity_at))
                         .where(Enrollment.student_id == s.id)).one()
        items.append({
            "id": s.id, "code": s.external_code,
            "name": f"Estudiante {s.external_code}" if pseudo else s.user.full_name,
            "email": None if pseudo else s.user.email,
            "avatar_url": None if pseudo else s.user.avatar_url, "region": s.region, "status": s.enrollment_status,
            "courses": agg[0], "avg_progress": round(float(agg[1] or 0), 4), "last_activity_at": agg[2], "risk_probability": _risk_for(db, s.id),
        })
    return {"items": items, "total": total, "pseudonymized": pseudo}


@router.get("/students/{student_id}/progress")
def student_progress(student_id: uuid.UUID, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    st = get_or_404(db, Student, student_id, p.org_id, "Estudiante no encontrado")
    if not p.can_see_student(db, st):
        raise HTTPException(403, "No autorizado para este estudiante")
    enrs = db.scalars(select(Enrollment).where(Enrollment.student_id == st.id)).all()
    courses = []
    for e in enrs:
        c = db.get(Course, e.course_id)
        if p.scoped_to_assigned_courses and c.id not in p.instructor_course_ids(db):
            continue
        attempts = db.execute(select(Assessment.title, AssessmentAttempt.score, Assessment.max_score, AssessmentAttempt.submitted_at)
                              .join(Assessment).where(AssessmentAttempt.student_id == st.id, Assessment.course_id == c.id)
                              .order_by(AssessmentAttempt.submitted_at)).all()
        courses.append({"enrollment_id": e.id, "course_id": c.id, "course_code": c.code, "course_title": c.title, "progress": e.progress,
                        "status": e.status, "last_activity_at": e.last_activity_at, "completed_at": e.completed_at,
                        "attempts": [{"title": a[0], "score": a[1], "max_score": a[2], "submitted_at": a[3]} for a in attempts]})
    since = datetime.now(timezone.utc) - timedelta(days=56)
    wk = func.date_trunc("week", LearningEvent.occurred_at) if db.bind.dialect.name == "postgresql" else func.strftime("%Y-%W", LearningEvent.occurred_at)
    weekly = db.execute(select(wk, func.count(), func.sum(LearningEvent.duration_seconds))
                        .where(LearningEvent.student_id == st.id, LearningEvent.occurred_at >= since).group_by(wk).order_by(wk)).all()
    evid = db.execute(select(Skill.name, SkillEvidence.source_type, func.avg(SkillEvidence.score), func.max(SkillEvidence.level))
                      .join(Skill).where(SkillEvidence.student_id == st.id).group_by(Skill.name, SkillEvidence.source_type)).all()
    return {
        "student": {"id": st.id, "name": st.user.full_name, "code": st.external_code, "region": st.region, "avatar_url": st.user.avatar_url},
        "courses": courses,
        "weekly_activity": [{"week": str(w[0])[:10], "events": w[1], "hours": round((w[2] or 0) / 3600, 2)} for w in weekly],
        "skills": [{"skill": e[0], "source": e[1], "score": round(float(e[2]), 3), "level": e[3]} for e in evid],
        "risk_probability": _risk_for(db, st.id),
        "note": "El nivel estimado por IA se muestra separado del nivel validado por evaluación docente.",
    }


@router.get("/me/progress")
def my_progress(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if not p.student_id:
        raise HTTPException(404, "El usuario no tiene perfil de estudiante")
    return student_progress(p.student_id, p, db)
