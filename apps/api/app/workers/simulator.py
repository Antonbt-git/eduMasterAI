"""Simulador DEMO de actividad: genera eventos de aprendizaje REALES (persistidos, rotulados source=demo-simulator)
a través del mismo servicio de ingesta. Se activa/desactiva por institución en Configuración.

No es una animación falsa: cada evento recorre validación → persistencia → agregados → Outbox → SSE.
"""
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..core.config import settings
from ..core.observability import log
from ..db.base import SessionLocal
from ..db.models import Assessment, AssessmentAttempt, CourseUnit, Enrollment, Lesson, Organization, Student
from ..modules.academic import _after_grade
from ..modules.tracking import EventIn, ingest_event


def tick(rnd: random.Random) -> None:
    with SessionLocal() as db:
        for org in db.scalars(select(Organization).where(Organization.status == "active")):
            if not (org.settings or {}).get("demo_simulator"):
                continue
            enr = db.scalar(select(Enrollment).where(Enrollment.organization_id == org.id, Enrollment.status == "in_progress")
                            .order_by(func.random()).limit(1))
            if not enr:
                continue
            st = db.get(Student, enr.student_id)
            r = rnd.random()
            if r < 0.12:
                a = db.scalar(select(Assessment).where(Assessment.course_id == enr.course_id, Assessment.type == "multiple_choice").limit(1))
                used = db.scalar(select(func.count(AssessmentAttempt.id)).where(AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == st.id)) if a else 99
                if a and used < a.attempts_allowed:
                    answers = {str(i): (q["answer"] if rnd.random() < 0.75 else q["options"][0]) for i, q in enumerate(a.questions)}
                    from ..modules.academic import _grade_auto
                    t = AssessmentAttempt(assessment_id=a.id, student_id=st.id, answers=answers, score=_grade_auto(a, answers), status="graded")
                    db.add(t)
                    db.flush()
                    _after_grade(db, a, t, None)
                    db.commit()
                    continue
            lessons = list(db.scalars(select(Lesson.id).join(CourseUnit).where(CourseUnit.course_id == enr.course_id).order_by(CourseUnit.position, Lesson.position)))
            etype = rnd.choice(["session_started", "lesson_viewed", "lesson_viewed", "activity_completed"])
            body = EventIn(event_id=uuid.uuid4(), event_type=etype, occurred_at=datetime.now(timezone.utc), course_id=enr.course_id,
                           activity_id=str(rnd.choice(lessons[: max(1, int(len(lessons) * min(1.0, enr.progress + 0.35)))])) if lessons and etype != "session_started" else None,
                           duration_seconds=rnd.randint(90, 1800), source="demo-simulator", payload={"label": "DEMO"})
            ingest_event(db, None, body, org.id, st)
            db.commit()


async def run_simulator(stop: asyncio.Event) -> None:
    if not settings.demo_simulator:
        return
    rnd = random.Random()
    log.info("demo_simulator_started")
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick, rnd)
        except Exception as exc:
            log.warning("demo_simulator_error", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=rnd.uniform(2.5, 5.0))
        except asyncio.TimeoutError:
            pass
