"""Construcción de features autorizadas y versionadas desde la BD (mismas definiciones que el pipeline ML)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Assessment, AssessmentAttempt, Course, CourseSkill, Enrollment, LearningEvent, Skill

FEATURE_SCHEMA_VERSION = "1.0"
WEEKS = 8
LEVEL_IDX = {"basico": 0, "intermedio": 1, "avanzado": 2}
SKILL_ORDER = ["IA", "ML", "DS", "WEB", "OPS"]


def build_features(db: Session, student_id, course_id=None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    enr = None
    if course_id is None:
        enr = db.scalar(select(Enrollment).where(Enrollment.student_id == student_id, Enrollment.status != "completed")
                        .order_by(Enrollment.last_activity_at.desc().nullslast()).limit(1)) or \
              db.scalar(select(Enrollment).where(Enrollment.student_id == student_id).limit(1))
        course_id = enr.course_id if enr else None
    start = now - timedelta(weeks=WEEKS)
    seq = np.zeros((WEEKS, 6), dtype=np.float32)
    q = select(LearningEvent.event_type, LearningEvent.occurred_at, LearningEvent.duration_seconds).where(
        LearningEvent.student_id == student_id, LearningEvent.occurred_at >= start)
    if course_id:
        q = q.where(LearningEvent.course_id == course_id)
    days = [set() for _ in range(WEEKS)]
    for et, at, dur in db.execute(q):
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        w = min(WEEKS - 1, max(0, int((at - start).days // 7)))
        days[w].add(at.date())
        if et == "session_started":
            seq[w, 1] += 1
        if et == "activity_completed":
            seq[w, 2] += 1
        seq[w, 5] += (dur or 0) / 3600
    for w in range(WEEKS):
        seq[w, 0] = len(days[w])
    aq = select(AssessmentAttempt.score, Assessment.max_score, AssessmentAttempt.submitted_at, AssessmentAttempt.late).join(Assessment) \
        .where(AssessmentAttempt.student_id == student_id, AssessmentAttempt.submitted_at >= start, AssessmentAttempt.score.is_not(None))
    if course_id:
        aq = aq.where(Assessment.course_id == course_id)
    sc_sum, sc_n = np.zeros(WEEKS), np.zeros(WEEKS)
    for score, mx, at, late in db.execute(aq):
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        w = min(WEEKS - 1, max(0, int((at - start).days // 7)))
        sc_sum[w] += score / mx
        sc_n[w] += 1
        seq[w, 4] += 1 if late else 0
    seq[:, 3] = np.where(sc_n > 0, sc_sum / np.maximum(sc_n, 1), 0)
    has = sc_n > 0
    level = 0
    skill_idx = 0
    required = 18
    if course_id:
        c = db.get(Course, course_id)
        level = LEVEL_IDX.get(c.level, 0)
        required = 18 + 4 * level
        sk = db.scalar(select(Skill.code).join(CourseSkill, CourseSkill.skill_id == Skill.id).where(CourseSkill.course_id == course_id).limit(1))
        if sk and sk.split("-")[0] in SKILL_ORDER:
            skill_idx = SKILL_ORDER.index(sk.split("-")[0])
    comp_ratio = float(np.clip(seq[:, 2].sum() / required, 0, 1))
    mean_score = float((seq[:, 3] * has).sum() / max(1, has.sum()))
    idx = np.arange(WEEKS)
    trend = float(np.polyfit(idx[has], seq[has, 3], 1)[0]) if has.sum() >= 2 else 0.0
    active = np.where(seq[:, 1] > 0)[0]
    tab = {
        "active_days_14d": float(seq[-2:, 0].sum()),
        "sessions_14d": float(seq[-2:, 1].sum()),
        "completion_ratio": comp_ratio,
        "assessment_mean": mean_score,
        "assessment_trend": trend,
        "late_submissions_30d": float(seq[-4:, 4].sum()),
        "content_engagement": float(seq[:, 5].sum()),
        "skill_evidence_score": float(np.clip(mean_score * (0.6 + 0.4 * comp_ratio), 0, 1)),
        "days_since_last_activity": float((WEEKS - 1 - active.max()) * 7 if len(active) else WEEKS * 7),
    }
    return {"tab": {k: round(v, 4) for k, v in tab.items()}, "seq": np.round(seq, 4).tolist(), "course_level": level,
            "skill_idx": skill_idx, "course_id": str(course_id) if course_id else None,
            "feature_schema_version": FEATURE_SCHEMA_VERSION, "window": {"from": start.isoformat(), "to": now.isoformat()}}
