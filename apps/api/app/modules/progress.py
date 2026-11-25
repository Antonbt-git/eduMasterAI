"""Servicio de progreso transaccional y evidencias (compartido por tracking y evaluaciones)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..core.events import activity, emit, notify
from ..core.infra import store
from ..db.models import (
    Assessment, AssessmentAttempt, Course, CourseUnit, DailyMetric, Enrollment, LearningEvent, Lesson, Student, User,
)

STAFF_AUDIENCE = ["superadmin", "admin", "coordinator", "instructor"]


def course_lesson_ids(db: Session, course_id) -> list[str]:
    return [str(i) for i in db.scalars(select(Lesson.id).join(CourseUnit).where(CourseUnit.course_id == course_id))]


def best_scores(db: Session, student_id, course_id) -> dict:
    assessments = db.execute(select(Assessment.id, Assessment.passing_score, Assessment.grading_rule)
                             .where(Assessment.course_id == course_id, Assessment.status == "published")).all()
    agg = {r[0]: r for r in db.execute(
        select(AssessmentAttempt.assessment_id, func.max(AssessmentAttempt.score), func.avg(AssessmentAttempt.score))
        .where(AssessmentAttempt.student_id == student_id, AssessmentAttempt.status == "graded",
               AssessmentAttempt.assessment_id.in_([a[0] for a in assessments]))
        .group_by(AssessmentAttempt.assessment_id)).all()}
    out = {}
    for aid, passing, rule in assessments:
        r = agg.get(aid)
        out[str(aid)] = {"passing": passing, "score": None if not r else (r[2] if rule == "average" else r[1])}
    return out


def recompute_enrollment(db: Session, enr: Enrollment, actor_id=None) -> Enrollment:
    lessons = course_lesson_ids(db, enr.course_id)
    seen = set(db.scalars(select(LearningEvent.activity_id).where(
        LearningEvent.student_id == enr.student_id, LearningEvent.course_id == enr.course_id,
        LearningEvent.event_type.in_(["lesson_viewed", "activity_completed"]))))
    lesson_ratio = len(seen & set(lessons)) / max(1, len(lessons)) if lessons else 0.0
    scores = best_scores(db, enr.student_id, enr.course_id)
    passed = sum(1 for s in scores.values() if s["score"] is not None and s["score"] >= s["passing"])
    assess_ratio = passed / len(scores) if scores else lesson_ratio
    progress = round(min(1.0, 0.6 * lesson_ratio + 0.4 * assess_ratio), 4)
    prev_status = enr.status
    enr.progress = progress
    enr.last_activity_at = datetime.now(timezone.utc)
    if enr.status == "not_started" and progress > 0:
        enr.status = "in_progress"
    student = db.get(Student, enr.student_id)
    course = db.get(Course, enr.course_id)
    emit(db, "learning.progress.updated",
         {"enrollment_id": str(enr.id), "student_id": str(enr.student_id), "course_id": str(enr.course_id),
          "course_title": course.title, "progress": progress, "region": student.region},
         org_id=enr.organization_id, actor_id=actor_id, aggregate_id=enr.id, roles=STAFF_AUDIENCE + ["analyst"], user_ids=[student.user_id])
    if progress >= 0.999 and prev_status != "completed":
        enr.status = "completed"
        enr.completed_at = datetime.now(timezone.utc)
        emit(db, "course.completed", {"enrollment_id": str(enr.id), "student_id": str(enr.student_id), "course_id": str(enr.course_id),
                                      "course_title": course.title}, org_id=enr.organization_id, aggregate_id=enr.id,
             roles=STAFF_AUDIENCE + ["analyst"], user_ids=[student.user_id])
        activity(db, enr.organization_id, "course_completed", f"Curso de {course.title} completado", subject_user_id=student.user_id, visibility="org")
        notify(db, enr.organization_id, student.user_id, "course.completed", f"¡Completaste {course.title}!",
               "Ya puedes solicitar tu certificado.", "/certificados")
        bump_daily(db, enr.organization_id, enr.course_id, student.region, completions=1)
    store.invalidate(f"dash:{enr.organization_id}")
    return enr


def bump_daily(db: Session, org_id, course_id, region: str, day: date | None = None, events=0, seconds=0, assessments=0, completions=0, active=0):
    """Actualización incremental del agregado diario (upsert)."""
    day = day or datetime.now(timezone.utc).date()
    vals = dict(organization_id=org_id, day=day, course_id=course_id, region=region, events=events, learning_seconds=seconds,
                assessments=assessments, completions=completions, active_students=active, computed_at=datetime.now(timezone.utc))
    if db.bind.dialect.name == "postgresql":
        stmt = pg_insert(DailyMetric).values(**vals)
        stmt = stmt.on_conflict_do_update(
            index_elements=["organization_id", "day", "course_id", "region"],
            set_={"events": DailyMetric.events + events, "learning_seconds": DailyMetric.learning_seconds + seconds,
                  "assessments": DailyMetric.assessments + assessments, "completions": DailyMetric.completions + completions,
                  "active_students": DailyMetric.active_students + active, "computed_at": vals["computed_at"]})
        db.execute(stmt)
    else:
        row = db.get(DailyMetric, (org_id, day, course_id, region))
        if row:
            row.events += events; row.learning_seconds += seconds; row.assessments += assessments
            row.completions += completions; row.active_students += active
        else:
            db.add(DailyMetric(**vals))


def student_user(db: Session, student_id) -> User:
    return db.get(Student, student_id).user
