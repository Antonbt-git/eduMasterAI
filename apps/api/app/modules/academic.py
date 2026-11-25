"""Academic Core: cursos y contenidos, ofertas, matrículas, cohortes, competencias, rutas y evaluaciones."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_principal, require
from ..core.events import activity, audit, emit, notify
from ..core.infra import store
from ..db.base import get_db
from ..db.models import (
    Assessment, AssessmentAttempt, Cohort, Course, CourseOffering, CourseSkill, CourseUnit, Enrollment, Instructor,
    LearningPath, Lesson, PathAssignment, PathStep, Skill, SkillEvidence, Student,
)
from .common import get_or_404
from .progress import STAFF_AUDIENCE, bump_daily, recompute_enrollment

router = APIRouter(tags=["Academic Core"])
LEVELS = ("basico", "intermedio", "avanzado")


# =============================================================== Schemas
class LessonIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: str = Field("lesson", pattern="^(lesson|resource|link|file|activity)$")
    resource_url: str | None = Field(None, max_length=500)
    duration_min: int = Field(15, ge=1, le=600)

    @field_validator("resource_url")
    @classmethod
    def safe_url(cls, v):
        if v and not v.startswith(("https://", "http://", "/")):
            raise ValueError("URL inválida (solo http/https)")
        return v


class UnitIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    lessons: list[LessonIn] = []


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9\-_]+$")
    title: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=5000)
    level: str = Field("basico", pattern="^(basico|intermedio|avanzado)$")
    tags: list[str] = []
    duration_hours: int = Field(20, ge=1, le=1000)
    skill_ids: list[uuid.UUID] = []
    instructor_id: uuid.UUID | None = None
    units: list[UnitIn] = []
    cover_color: str = Field("#087FE5", pattern="^#[0-9A-Fa-f]{6}$")


class CourseUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    level: str | None = Field(None, pattern="^(basico|intermedio|avanzado)$")
    tags: list[str] | None = None
    duration_hours: int | None = Field(None, ge=1, le=1000)
    skill_ids: list[uuid.UUID] | None = None
    cover_color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


# =============================================================== Service
def course_dto(db: Session, c: Course, p: Principal | None = None, detail: bool = False) -> dict:
    stats = db.execute(select(func.count(Enrollment.id), func.avg(Enrollment.progress),
                              func.count(Enrollment.id).filter(Enrollment.status == "completed"))
                       .where(Enrollment.course_id == c.id)).one()
    offering = db.scalar(select(CourseOffering).where(CourseOffering.course_id == c.id).order_by(CourseOffering.created_at.desc()).limit(1))
    instructor = db.get(Instructor, offering.instructor_id) if offering and offering.instructor_id else None
    d = {
        "id": c.id, "code": c.code, "title": c.title, "description": c.description, "level": c.level, "status": c.status,
        "tags": c.tags, "duration_hours": c.duration_hours, "version": c.version, "cover_color": c.cover_color,
        "updated_at": c.updated_at,
        "skills": [{"id": s.skill_id, "name": s.skill.name, "weight": s.weight, "color": s.skill.color} for s in c.skills],
        "instructor": {"id": instructor.id, "name": instructor.user.full_name, "avatar_url": instructor.user.avatar_url} if instructor else None,
        "stats": {"enrolled": stats[0] or 0, "avg_progress": round(float(stats[1] or 0), 4),
                  "completed": int(stats[2] or 0)},
        "lessons_count": sum(len(u.lessons) for u in c.units),
    }
    if p and p.student_id:
        e = db.scalar(select(Enrollment).where(Enrollment.course_id == c.id, Enrollment.student_id == p.student_id))
        d["my_enrollment"] = {"id": e.id, "progress": e.progress, "status": e.status} if e else None
    if detail:
        d["units"] = [{"id": u.id, "title": u.title, "position": u.position,
                       "lessons": [{"id": l.id, "title": l.title, "kind": l.kind, "resource_url": l.resource_url, "duration_min": l.duration_min} for l in u.lessons]}
                      for u in c.units]
        d["offerings"] = [{"id": o.id, "period": o.period, "starts_at": o.starts_at, "ends_at": o.ends_at}
                          for o in db.scalars(select(CourseOffering).where(CourseOffering.course_id == c.id))]
        d["assessments"] = [{"id": a.id, "title": a.title, "type": a.type, "due_at": a.due_at, "max_score": a.max_score}
                            for a in db.scalars(select(Assessment).where(Assessment.course_id == c.id))]
    return d


def visible_courses_stmt(p: Principal, db: Session):
    stmt = select(Course).where(Course.organization_id == p.org_id)
    if p.is_student_only:
        stmt = stmt.where(Course.status == "published")
    elif p.scoped_to_assigned_courses:
        stmt = stmt.where(Course.id.in_(p.instructor_course_ids(db)))
    return stmt


def ensure_course_access(db: Session, p: Principal, course: Course, write: bool = False):
    if course.organization_id != p.org_id:
        raise HTTPException(404, "Curso no encontrado")
    if p.scoped_to_assigned_courses and course.id not in p.instructor_course_ids(db):
        raise HTTPException(403, "Curso no asignado")
    if write and not (p.has("courses:write") or (p.has("assessments:write") and course.id in p.instructor_course_ids(db))):
        raise HTTPException(403, "Sin permiso de edición")
    if p.is_student_only and course.status != "published":
        raise HTTPException(404, "Curso no encontrado")


def _set_skills(db: Session, c: Course, skill_ids: list[uuid.UUID], org_id):
    valid = set(db.scalars(select(Skill.id).where(Skill.id.in_(skill_ids), Skill.organization_id == org_id)))
    c.skills = [CourseSkill(skill_id=s, weight=1.0) for s in skill_ids if s in valid]


# =============================================================== Courses
@router.get("/courses")
def list_courses(q: str | None = None, level: str | None = None, status: str | None = None, skill_id: uuid.UUID | None = None,
                 tag: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100),
                 p: Principal = Depends(require("courses:read")), db: Session = Depends(get_db)):
    stmt = visible_courses_stmt(p, db)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Course.title).like(like), func.lower(Course.code).like(like), func.lower(Course.description).like(like)))
    if level:
        stmt = stmt.where(Course.level == level)
    if status:
        stmt = stmt.where(Course.status == status)
    if skill_id:
        stmt = stmt.where(Course.skills.any(CourseSkill.skill_id == skill_id))
    if tag:
        stmt = stmt.where(func.lower(cast(Course.tags, String)).like(f"%{tag.lower()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Course.code).limit(page_size).offset((page - 1) * page_size)).unique().all()
    return {"items": [course_dto(db, c, p) for c in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/courses", status_code=201)
def create_course(body: CourseIn, p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    if db.scalar(select(Course.id).where(Course.organization_id == p.org_id, func.lower(Course.code) == body.code.lower())):
        raise HTTPException(409, f"El código {body.code} ya existe en la institución")
    c = Course(organization_id=p.org_id, code=body.code.upper(), title=body.title, description=body.description, level=body.level,
               tags=body.tags, duration_hours=body.duration_hours, status="draft", updated_by=p.id, cover_color=body.cover_color)
    db.add(c)
    db.flush()
    _set_skills(db, c, body.skill_ids, p.org_id)
    for i, u in enumerate(body.units):
        unit = CourseUnit(course_id=c.id, title=u.title, position=i)
        unit.lessons = [Lesson(title=l.title, kind=l.kind, resource_url=l.resource_url, duration_min=l.duration_min, position=j) for j, l in enumerate(u.lessons)]
        db.add(unit)
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    instructor_id = body.instructor_id if body.instructor_id and db.get(Instructor, body.instructor_id) else None
    db.add(CourseOffering(course_id=c.id, instructor_id=instructor_id, period=period, starts_at=date.today()))
    audit(db, p, "course.created", "course", c.id, {"code": c.code})
    db.commit()
    db.refresh(c)
    return course_dto(db, c, p, detail=True)


@router.get("/courses/export")
def export_courses(p: Principal = Depends(require("courses:read")), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["code", "title", "level", "status", "duration_hours", "tags", "description"])
    for c in db.scalars(visible_courses_stmt(p, db).order_by(Course.code)):
        w.writerow([c.code, c.title, c.level, c.status, c.duration_hours, "|".join(c.tags or []), c.description])
    audit(db, p, "course.exported", "course", details={"format": "csv"})
    db.commit()
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=cursos_{date.today()}.csv"})


@router.post("/courses/import")
async def import_courses(file: UploadFile = File(...), idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
                         p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    if idempotency_key and (prev := store.get_json(f"idem:import:{p.org_id}:{idempotency_key}")):
        return {**prev, "idempotent_replay": True}
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Archivo demasiado grande (máx 2 MB)")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Solo se aceptan archivos CSV")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        code = (row.get("code") or "").strip().upper()
        title = (row.get("title") or "").strip()
        level = (row.get("level") or "basico").strip()
        if not code or not title or level not in LEVELS:
            errors.append({"row": i, "error": "code/title/level inválidos"})
            continue
        if db.scalar(select(Course.id).where(Course.organization_id == p.org_id, Course.code == code)):
            skipped += 1
            continue
        db.add(Course(organization_id=p.org_id, code=code, title=title, level=level, status="draft",
                      description=row.get("description", ""), tags=[t for t in (row.get("tags") or "").split("|") if t],
                      duration_hours=int(row.get("duration_hours") or 20), updated_by=p.id))
        created += 1
    audit(db, p, "course.imported", "course", details={"created": created, "skipped": skipped, "errors": len(errors)})
    db.commit()
    res = {"created": created, "skipped": skipped, "errors": errors}
    if idempotency_key:
        store.set_json(f"idem:import:{p.org_id}:{idempotency_key}", res, ex=86400)
    return res


@router.get("/courses/{course_id}")
def get_course(course_id: uuid.UUID, p: Principal = Depends(require("courses:read")), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    ensure_course_access(db, p, c)
    return course_dto(db, c, p, detail=True)


@router.patch("/courses/{course_id}")
def update_course(course_id: uuid.UUID, body: CourseUpdate, p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        if k != "skill_ids":
            setattr(c, k, v)
    if body.skill_ids is not None:
        _set_skills(db, c, body.skill_ids, p.org_id)
    c.version += 1
    c.updated_by = p.id
    audit(db, p, "course.updated", "course", c.id, {k: str(v) for k, v in changes.items()})
    db.commit()
    return course_dto(db, c, p, detail=True)


@router.post("/courses/{course_id}/publish")
def publish_course(course_id: uuid.UUID, p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    if not c.units or not any(u.lessons for u in c.units):
        raise HTTPException(422, "El curso necesita al menos una unidad con contenido antes de publicarse")
    c.status = "published"
    c.version += 1
    audit(db, p, "course.published", "course", c.id, {"version": c.version})
    activity(db, p.org_id, "course_published", f"Curso publicado: {c.title}", actor_id=p.id, visibility="org")
    db.commit()
    return course_dto(db, c, p, detail=True)


@router.post("/courses/{course_id}/archive")
def archive_course(course_id: uuid.UUID, p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    c.status = "archived"
    audit(db, p, "course.archived", "course", c.id)
    db.commit()
    return {"id": c.id, "status": c.status}


@router.post("/courses/{course_id}/units", status_code=201)
def add_unit(course_id: uuid.UUID, body: UnitIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    ensure_course_access(db, p, c, write=True)
    unit = CourseUnit(course_id=c.id, title=body.title, position=len(c.units))
    unit.lessons = [Lesson(title=l.title, kind=l.kind, resource_url=l.resource_url, duration_min=l.duration_min, position=j) for j, l in enumerate(body.lessons)]
    db.add(unit)
    c.version += 1
    audit(db, p, "course.unit_added", "course", c.id, {"unit": body.title})
    db.commit()
    db.refresh(c)
    return course_dto(db, c, p, detail=True)


@router.post("/courses/{course_id}/units/{unit_id}/lessons", status_code=201)
def add_lesson(course_id: uuid.UUID, unit_id: uuid.UUID, body: LessonIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    ensure_course_access(db, p, c, write=True)
    unit = db.get(CourseUnit, unit_id)
    if not unit or unit.course_id != c.id:
        raise HTTPException(404, "Unidad no encontrada")
    db.add(Lesson(unit_id=unit.id, title=body.title, kind=body.kind, resource_url=body.resource_url, duration_min=body.duration_min, position=len(unit.lessons)))
    c.version += 1
    audit(db, p, "course.lesson_added", "course", c.id, {"lesson": body.title})
    db.commit()
    db.refresh(c)
    return course_dto(db, c, p, detail=True)


@router.delete("/courses/{course_id}/lessons/{lesson_id}", status_code=204)
def delete_lesson(course_id: uuid.UUID, lesson_id: uuid.UUID, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    ensure_course_access(db, p, c, write=True)
    l = db.get(Lesson, lesson_id)
    if not l or db.get(CourseUnit, l.unit_id).course_id != c.id:
        raise HTTPException(404, "Lección no encontrada")
    db.delete(l)
    c.version += 1
    audit(db, p, "course.lesson_removed", "course", c.id, {"lesson_id": str(lesson_id)})
    db.commit()


class EnrollIn(BaseModel):
    student_ids: list[uuid.UUID] = []


@router.post("/courses/{course_id}/enroll")
def enroll(course_id: uuid.UUID, body: EnrollIn | None = None, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, course_id, p.org_id, "Curso no encontrado")
    if c.status != "published":
        raise HTTPException(409, "Solo se puede matricular en cursos publicados")
    ids = (body.student_ids if body else []) or []
    if ids and not (p.has("courses:write") or p.has("paths:write")):
        raise HTTPException(403, "No puede matricular a otros estudiantes")
    if not ids:
        if not p.student_id:
            raise HTTPException(422, "Indique estudiantes a matricular")
        ids = [p.student_id]
    offering = db.scalar(select(CourseOffering).where(CourseOffering.course_id == c.id).order_by(CourseOffering.created_at.desc()).limit(1))
    created = []
    for sid in ids:
        st = db.get(Student, sid)
        if not st or st.organization_id != p.org_id:
            continue
        if db.scalar(select(Enrollment.id).where(Enrollment.offering_id == offering.id, Enrollment.student_id == sid)):
            continue
        e = Enrollment(offering_id=offering.id, course_id=c.id, student_id=sid, organization_id=p.org_id, status="not_started")
        db.add(e)
        db.flush()
        created.append(str(e.id))
        activity(db, p.org_id, "enrollment", f"Nuevo curso iniciado: {c.title}", actor_id=p.id, subject_user_id=st.user_id)
        bump_daily(db, p.org_id, c.id, st.region, active=1)
    audit(db, p, "enrollment.created", "course", c.id, {"count": len(created)})
    db.commit()
    store.invalidate(f"dash:{p.org_id}")
    return {"created": len(created), "enrollment_ids": created}


# =============================================================== Catálogos
@router.get("/skills")
def list_skills(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return [{"id": s.id, "code": s.code, "name": s.name, "parent_skill_id": s.parent_skill_id, "color": s.color}
            for s in db.scalars(select(Skill).where(Skill.organization_id == p.org_id).order_by(Skill.code))]


class SkillIn(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    parent_skill_id: uuid.UUID | None = None
    color: str = Field("#20C8F5", pattern="^#[0-9A-Fa-f]{6}$")


@router.post("/skills", status_code=201)
def create_skill(body: SkillIn, p: Principal = Depends(require("courses:write")), db: Session = Depends(get_db)):
    s = Skill(organization_id=p.org_id, **body.model_dump())
    db.add(s)
    audit(db, p, "skill.created", "skill", details=body.model_dump(mode="json"))
    db.commit()
    return {"id": s.id, **body.model_dump()}


@router.get("/cohorts")
def list_cohorts(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Cohort, func.count(PathAssignment.id)).join(PathAssignment, PathAssignment.cohort_id == Cohort.id, isouter=True)
                      .where(Cohort.organization_id == p.org_id).group_by(Cohort.id).order_by(Cohort.start_date)).all()
    return [{"id": c.id, "code": c.code, "name": c.name, "program": c.program, "start_date": c.start_date, "assignments": n} for c, n in rows]


@router.get("/instructors")
def list_instructors(p: Principal = Depends(require("courses:read")), db: Session = Depends(get_db)):
    return [{"id": i.id, "name": i.user.full_name, "email": i.user.email, "avatar_url": i.user.avatar_url}
            for i in db.scalars(select(Instructor).where(Instructor.organization_id == p.org_id))]


# =============================================================== Learning paths
class PathIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    objective: str = Field("", max_length=3000)
    competencies: list[str] = []
    duration_weeks: int = Field(12, ge=1, le=104)
    criteria: str = Field("Completar todos los cursos con nota ≥ 70", max_length=500)
    course_ids: list[uuid.UUID] = Field(min_length=1)


class AssignIn(BaseModel):
    student_ids: list[uuid.UUID] = []
    cohort_id: uuid.UUID | None = None
    target_date: date | None = None
    exception_note: str | None = None


def path_dto(db: Session, lp: LearningPath, p: Principal) -> dict:
    steps = [{"id": s.id, "position": s.position, "course_id": s.course_id, "course_title": s.course.title, "course_code": s.course.code,
              "course_status": s.course.status, "prerequisite_course_id": s.prerequisite_course_id} for s in lp.steps]
    q = select(PathAssignment).where(PathAssignment.path_id == lp.id)
    if p.is_student_only:
        q = q.where(PathAssignment.student_id == p.student_id)
    assignments = db.scalars(q).all()
    course_ids = [s.course_id for s in lp.steps]
    my = None
    if p.student_id:
        enr = {e.course_id: e for e in db.scalars(select(Enrollment).where(Enrollment.student_id == p.student_id, Enrollment.course_id.in_(course_ids)))}
        per_step = [{"course_id": cid, "progress": enr[cid].progress if cid in enr else 0.0, "status": enr[cid].status if cid in enr else "not_started"} for cid in course_ids]
        my = {"progress": round(sum(x["progress"] for x in per_step) / max(1, len(per_step)), 4), "steps": per_step}
    avg = db.scalar(select(func.avg(Enrollment.progress)).where(Enrollment.course_id.in_(course_ids), Enrollment.organization_id == p.org_id)) if course_ids else 0
    return {"id": lp.id, "title": lp.title, "objective": lp.objective, "competencies": lp.competencies, "duration_weeks": lp.duration_weeks,
            "criteria": lp.criteria, "version": lp.version, "status": lp.status, "steps": steps, "assignments": len(assignments),
            "avg_progress": round(float(avg or 0), 4), "my_progress": my, "created_at": lp.created_at}


@router.get("/learning-paths")
def list_paths(p: Principal = Depends(require("paths:read")), db: Session = Depends(get_db)):
    stmt = select(LearningPath).where(LearningPath.organization_id == p.org_id)
    if p.is_student_only:
        stmt = stmt.where(LearningPath.status == "published")
    return [path_dto(db, lp, p) for lp in db.scalars(stmt.order_by(LearningPath.created_at.desc()))]


@router.post("/learning-paths", status_code=201)
def create_path(body: PathIn, p: Principal = Depends(require("paths:write")), db: Session = Depends(get_db)):
    courses = {c.id: c for c in db.scalars(select(Course).where(Course.id.in_(body.course_ids), Course.organization_id == p.org_id))}
    if len(courses) != len(set(body.course_ids)):
        raise HTTPException(422, "Curso inválido en la ruta")
    lp = LearningPath(organization_id=p.org_id, title=body.title, objective=body.objective, competencies=body.competencies,
                      duration_weeks=body.duration_weeks, criteria=body.criteria)
    lp.steps = [PathStep(course_id=cid, position=i, prerequisite_course_id=body.course_ids[i - 1] if i else None) for i, cid in enumerate(body.course_ids)]
    db.add(lp)
    db.flush()
    audit(db, p, "path.created", "learning_path", lp.id, {"title": lp.title})
    db.commit()
    return path_dto(db, lp, p)


@router.post("/learning-paths/{path_id}/publish")
def publish_path(path_id: uuid.UUID, p: Principal = Depends(require("paths:write")), db: Session = Depends(get_db)):
    lp = get_or_404(db, LearningPath, path_id, p.org_id, "Ruta no encontrada")
    unpublished = [s.course.code for s in lp.steps if s.course.status != "published"]
    if unpublished:
        raise HTTPException(422, f"Cursos no publicados en la ruta: {', '.join(unpublished)}")
    lp.status = "published"
    lp.version += 1
    audit(db, p, "path.published", "learning_path", lp.id, {"version": lp.version})
    db.commit()
    return path_dto(db, lp, p)


@router.post("/learning-paths/{path_id}/assign")
def assign_path(path_id: uuid.UUID, body: AssignIn, p: Principal = Depends(require("paths:write")), db: Session = Depends(get_db)):
    lp = get_or_404(db, LearningPath, path_id, p.org_id, "Ruta no encontrada")
    if lp.status != "published":
        raise HTTPException(409, "Publique la ruta antes de asignarla")
    created = 0
    if body.cohort_id:
        get_or_404(db, Cohort, body.cohort_id, p.org_id, "Cohorte no encontrada")
        db.add(PathAssignment(path_id=lp.id, cohort_id=body.cohort_id, target_date=body.target_date, exception_note=body.exception_note))
        created += 1
    for sid in body.student_ids:
        st = db.get(Student, sid)
        if st and st.organization_id == p.org_id:
            db.add(PathAssignment(path_id=lp.id, student_id=sid, target_date=body.target_date, exception_note=body.exception_note))
            notify(db, p.org_id, st.user_id, "path.assigned", f"Nueva ruta asignada: {lp.title}", lp.objective[:200], "/rutas")
            created += 1
    if not created:
        raise HTTPException(422, "Indique cohorte o estudiantes válidos")
    audit(db, p, "path.assigned", "learning_path", lp.id, body.model_dump(mode="json"))
    db.commit()
    return {"assigned": created, "path": path_dto(db, lp, p)}


# =============================================================== Evaluaciones
class QuestionIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    options: list[str] = []
    answer: str | None = None
    points: float = Field(10, gt=0, le=100)


class AssessmentIn(BaseModel):
    course_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    type: str = Field("multiple_choice", pattern="^(multiple_choice|true_false|short_answer|file|practice)$")
    max_score: float = Field(100, gt=0, le=1000)
    passing_score: float = Field(70, ge=0, le=1000)
    weight: float = Field(1.0, gt=0, le=10)
    due_at: datetime | None = None
    attempts_allowed: int = Field(2, ge=1, le=10)
    grading_rule: str = Field("best", pattern="^(best|last|average)$")
    instructions: str = Field("", max_length=4000)
    rubric: list[dict] = []
    questions: list[QuestionIn] = []
    skill_id: uuid.UUID | None = None


class AttemptIn(BaseModel):
    answers: dict[str, str] = {}
    file_url: str | None = Field(None, max_length=500)


class GradeIn(BaseModel):
    score: float = Field(ge=0)
    feedback: str = Field("", max_length=4000)


def assessment_dto(a: Assessment, hide_answers: bool, my_attempts: list | None = None) -> dict:
    qs = [{"id": str(i), "prompt": q["prompt"], "options": q.get("options", []), "points": q.get("points", 10),
           **({} if hide_answers else {"answer": q.get("answer")})} for i, q in enumerate(a.questions or [])]
    return {"id": a.id, "course_id": a.course_id, "title": a.title, "type": a.type, "max_score": a.max_score, "passing_score": a.passing_score,
            "weight": a.weight, "due_at": a.due_at, "attempts_allowed": a.attempts_allowed, "grading_rule": a.grading_rule,
            "instructions": a.instructions, "rubric": a.rubric, "questions": qs, "status": a.status, "skill_id": a.skill_id,
            "my_attempts": my_attempts}


@router.get("/assessments")
def list_assessments(course_id: uuid.UUID | None = None, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    stmt = select(Assessment).where(Assessment.organization_id == p.org_id)
    if course_id:
        stmt = stmt.where(Assessment.course_id == course_id)
    if p.scoped_to_assigned_courses:
        stmt = stmt.where(Assessment.course_id.in_(p.instructor_course_ids(db)))
    if p.is_student_only:
        enrolled = select(Enrollment.course_id).where(Enrollment.student_id == p.student_id)
        stmt = stmt.where(Assessment.course_id.in_(enrolled), Assessment.status == "published")
    out = []
    for a in db.scalars(stmt.order_by(Assessment.due_at.desc().nullslast())):
        mine = None
        if p.student_id:
            mine = [{"id": t.id, "score": t.score, "status": t.status, "submitted_at": t.submitted_at, "late": t.late}
                    for t in db.scalars(select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == p.student_id))]
        course = db.get(Course, a.course_id)
        cnt = db.scalar(select(func.count(AssessmentAttempt.id)).where(AssessmentAttempt.assessment_id == a.id))
        avg = db.scalar(select(func.avg(AssessmentAttempt.score)).where(AssessmentAttempt.assessment_id == a.id))
        out.append({**assessment_dto(a, hide_answers=True, my_attempts=mine), "course_title": course.title, "course_code": course.code,
                    "attempts_count": cnt, "avg_score": round(float(avg), 2) if avg is not None else None})
    return out


@router.post("/assessments", status_code=201)
def create_assessment(body: AssessmentIn, p: Principal = Depends(require("assessments:write")), db: Session = Depends(get_db)):
    c = get_or_404(db, Course, body.course_id, p.org_id, "Curso no encontrado")
    ensure_course_access(db, p, c, write=True)
    if body.passing_score > body.max_score:
        raise HTTPException(422, "La nota mínima no puede superar el puntaje máximo")
    if body.type in ("multiple_choice", "true_false") and not body.questions:
        raise HTTPException(422, "Agregue preguntas con respuesta correcta")
    a = Assessment(organization_id=p.org_id, **body.model_dump(exclude={"questions"}), questions=[q.model_dump() for q in body.questions])
    db.add(a)
    db.flush()
    audit(db, p, "assessment.created", "assessment", a.id, {"title": a.title})
    for e in db.scalars(select(Enrollment).where(Enrollment.course_id == c.id)):
        st = db.get(Student, e.student_id)
        notify(db, p.org_id, st.user_id, "assessment.published", f"Nueva evaluación: {a.title}", f"Curso {c.title}", "/evaluaciones")
    db.commit()
    return assessment_dto(a, hide_answers=False)


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: uuid.UUID, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    a = get_or_404(db, Assessment, assessment_id, p.org_id, "Evaluación no encontrada")
    ensure_course_access(db, p, db.get(Course, a.course_id))
    return assessment_dto(a, hide_answers=not p.has("assessments:write"))


def _grade_auto(a: Assessment, answers: dict) -> float | None:
    if a.type not in ("multiple_choice", "true_false") or not a.questions:
        return None
    total = sum(q.get("points", 10) for q in a.questions)
    got = sum(q.get("points", 10) for i, q in enumerate(a.questions)
              if str(answers.get(str(i), "")).strip().lower() == str(q.get("answer", "")).strip().lower())
    return round(a.max_score * got / max(total, 1e-9), 2)


def _after_grade(db: Session, a: Assessment, t: AssessmentAttempt, actor_id):
    st = db.get(Student, t.student_id)
    course = db.get(Course, a.course_id)
    emit(db, "assessment.submitted", {"attempt_id": str(t.id), "assessment_id": str(a.id), "assessment_title": a.title,
                                      "course_id": str(a.course_id), "student_id": str(st.id), "score": t.score, "status": t.status},
         org_id=a.organization_id, actor_id=actor_id, aggregate_id=t.id, roles=STAFF_AUDIENCE, user_ids=[st.user_id])
    bump_daily(db, a.organization_id, a.course_id, st.region, assessments=1)
    if t.score is not None:
        approved = t.score >= a.passing_score
        activity(db, a.organization_id, "assessment_graded", f"Examen de {course.title} {'aprobado' if approved else 'calificado'}",
                 actor_id=actor_id, subject_user_id=st.user_id)
        if a.skill_id:
            ratio = t.score / a.max_score
            db.add(SkillEvidence(student_id=st.id, skill_id=a.skill_id, source_type="assessment", score=round(ratio, 4),
                                 level=min(4, int(ratio * 5)), validated_by=actor_id if actor_id != st.user_id else None))
        notify(db, a.organization_id, st.user_id, "assessment.graded", f"Calificación publicada: {a.title}", f"Puntaje {t.score:.1f}/{a.max_score:.0f}", "/evaluaciones")
    enr = db.scalar(select(Enrollment).where(Enrollment.student_id == st.id, Enrollment.course_id == a.course_id))
    if enr:
        recompute_enrollment(db, enr, actor_id)


@router.post("/assessments/{assessment_id}/attempts", status_code=201)
def submit_attempt(assessment_id: uuid.UUID, body: AttemptIn, p: Principal = Depends(require("attempts:submit")), db: Session = Depends(get_db)):
    a = get_or_404(db, Assessment, assessment_id, p.org_id, "Evaluación no encontrada")
    if not p.student_id:
        raise HTTPException(403, "Solo estudiantes pueden responder")
    if not db.scalar(select(Enrollment.id).where(Enrollment.student_id == p.student_id, Enrollment.course_id == a.course_id)):
        raise HTTPException(403, "No está matriculado en el curso")
    used = db.scalar(select(func.count(AssessmentAttempt.id)).where(AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == p.student_id))
    if used >= a.attempts_allowed:
        raise HTTPException(409, f"Agotó sus {a.attempts_allowed} intentos")
    now = datetime.now(timezone.utc)
    due = a.due_at.replace(tzinfo=timezone.utc) if a.due_at and a.due_at.tzinfo is None else a.due_at
    late = bool(due and now > due)
    score = _grade_auto(a, body.answers)
    t = AssessmentAttempt(assessment_id=a.id, student_id=p.student_id, answers={**body.answers, **({"file_url": body.file_url} if body.file_url else {})},
                          score=score, late=late, status="graded" if score is not None else "submitted", submitted_at=now)
    db.add(t)
    db.flush()
    audit(db, p, "attempt.submitted", "assessment", a.id, {"attempt_id": str(t.id), "auto_score": score, "late": late})
    _after_grade(db, a, t, p.id)
    if score is None:  # requiere revisión docente
        off = db.scalar(select(CourseOffering).where(CourseOffering.course_id == a.course_id).limit(1))
        if off and off.instructor_id:
            notify(db, p.org_id, db.get(Instructor, off.instructor_id).user_id, "attempt.pending", f"Entrega pendiente de revisión: {a.title}", "", "/evaluaciones")
    db.commit()
    return {"id": t.id, "score": t.score, "status": t.status, "late": t.late, "passing_score": a.passing_score, "max_score": a.max_score}


@router.get("/assessments/{assessment_id}/attempts")
def list_attempts(assessment_id: uuid.UUID, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    a = get_or_404(db, Assessment, assessment_id, p.org_id, "Evaluación no encontrada")
    ensure_course_access(db, p, db.get(Course, a.course_id))
    stmt = select(AssessmentAttempt).where(AssessmentAttempt.assessment_id == a.id)
    if p.is_student_only:
        stmt = stmt.where(AssessmentAttempt.student_id == p.student_id)
    out = []
    for t in db.scalars(stmt.order_by(AssessmentAttempt.submitted_at.desc()).limit(500)):
        st = db.get(Student, t.student_id)
        out.append({"id": t.id, "student_id": st.id, "student_name": st.user.full_name, "score": t.score, "status": t.status,
                    "late": t.late, "submitted_at": t.submitted_at, "feedback": t.feedback})
    return out


@router.post("/assessments/{assessment_id}/attempts/{attempt_id}/grade")
def grade_attempt(assessment_id: uuid.UUID, attempt_id: uuid.UUID, body: GradeIn, p: Principal = Depends(require("assessments:write")), db: Session = Depends(get_db)):
    a = get_or_404(db, Assessment, assessment_id, p.org_id, "Evaluación no encontrada")
    ensure_course_access(db, p, db.get(Course, a.course_id), write=True)
    t = db.get(AssessmentAttempt, attempt_id)
    if not t or t.assessment_id != a.id:
        raise HTTPException(404, "Intento no encontrado")
    if body.score > a.max_score:
        raise HTTPException(422, "Puntaje mayor al máximo")
    old = t.score
    t.score, t.feedback, t.status, t.graded_by = body.score, body.feedback, "graded", p.id
    audit(db, p, "grade.changed" if old is not None else "grade.assigned", "assessment_attempt", t.id, {"old": old, "new": body.score})
    _after_grade(db, a, t, p.id)
    db.commit()
    return {"id": t.id, "score": t.score, "status": t.status}
