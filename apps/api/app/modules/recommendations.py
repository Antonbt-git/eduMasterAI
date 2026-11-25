"""Recommendation: modelo → reglas de negocio → recomendación explicada → feedback registrado."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_principal, require
from ..core.events import audit, emit, notify
from ..db.base import get_db
from ..db.models import (
    Course, CourseSkill, Enrollment, Organization, Recommendation, RecommendationFeedback, Skill, Student,
)
from .common import get_or_404
from .ml import PredictIn, production, run_prediction

router = APIRouter(tags=["Recommendation"])
ACTIONS = ["Repasa", "Completa", "Sigue", "Realiza", "Explora"]
SKILL_ORDER = ["IA", "ML", "DS", "WEB", "OPS"]
LEVEL_IDX = {"basico": 0, "intermedio": 1, "avanzado": 2}


def rec_dto(r: Recommendation, db: Session, with_student: bool = False) -> dict:
    d = {"id": r.id, "type": r.type, "action": r.action, "title": r.title, "rationale": r.rationale, "impact": r.impact,
         "priority": r.priority, "confidence": r.confidence, "status": r.status, "resource_code": r.resource_code,
         "model_version": r.model_version, "created_at": r.created_at, "expires_at": r.expires_at, "review_note": r.review_note}
    if with_student:
        st = db.get(Student, r.student_id)
        d["student"] = {"id": st.id, "name": st.user.full_name, "avatar_url": st.user.avatar_url}
    return d


def generate_for_student(db: Session, p: Principal | None, student: Student, org_id) -> list[Recommendation]:
    """1) inferencia reco_ranker (+ riesgo/dominio si hay modelo) 2) reglas: catálogo publicado, no completado, prerrequisitos
    3) priorización por brecha de competencia 4) explicación."""
    org = db.get(Organization, org_id)
    threshold = (org.settings or {}).get("recommendation_threshold", 0.0)
    if not production(db, "reco_ranker"):
        raise HTTPException(409, "No hay modelo de recomendación publicado")
    res = run_prediction(db, p, PredictIn(network_key="reco_ranker", student_id=student.id), org_id)
    risk = None
    if production(db, "risk_transformer"):
        risk = run_prediction(db, p, PredictIn(network_key="risk_transformer", student_id=student.id), org_id)["scores"].get("risk_probability")
    feats = res["features_used"]["tab"]
    done = set(db.scalars(select(Enrollment.course_id).where(Enrollment.student_id == student.id, Enrollment.status == "completed")))
    mine = {e.course_id: e for e in db.scalars(select(Enrollment).where(Enrollment.student_id == student.id))}
    skills = {s.code: s for s in db.scalars(select(Skill).where(Skill.organization_id == org_id))}
    published = db.scalars(select(Course).where(Course.organization_id == org_id, Course.status == "published")).all()
    created = []
    seen_courses = set()
    scores = [r["score"] for r in res["scores"]["ranking"]]
    smin, smax = min(scores), max(scores)
    for rank, item in enumerate(res["scores"]["ranking"]):
        skill = skills.get(SKILL_ORDER[item["skill_idx"]])
        diff = int(item["code"].split("-")[1]) // 5 % 5
        cands = [c for c in published if c.id not in done and c.id not in seen_courses and skill and any(cs.skill_id == skill.id for cs in c.skills)]
        if not cands:
            continue
        cands.sort(key=lambda c: (c.id not in mine, abs(LEVEL_IDX[c.level] * 2 - diff)))
        course = cands[0]
        seen_courses.add(course.id)
        conf = round((item["score"] - smin) / (smax - smin + 1e-9) * 0.5 + 0.5, 3)
        if conf < threshold:
            continue
        enr = mine.get(course.id)
        action = "Completa" if enr and enr.progress > 0 else ("Repasa" if feats["assessment_mean"] < 0.55 else ACTIONS[min(diff, 4)])
        reasons = []
        if feats["assessment_mean"] < 0.6:
            reasons.append(f"Promedio de evaluaciones {feats['assessment_mean']:.0%}: conviene reforzar {skill.name}")
        if feats["days_since_last_activity"] > 7:
            reasons.append(f"{int(feats['days_since_last_activity'])} días sin actividad registrada")
        if enr:
            reasons.append(f"Avance actual del curso: {enr.progress:.0%}")
        if risk is not None and risk > 0.5:
            reasons.append("Señal de posible desconexión: se sugiere acompañamiento docente")
        if not reasons:
            reasons.append(f"Afinidad alta con tu perfil en {skill.name}")
        r = Recommendation(organization_id=org_id, student_id=student.id, model_version=f"reco_ranker@{res['model_version']}",
                           type="resource" if enr else "path", action=action, title=f"{action}: {course.title}",
                           rationale={"competency": skill.name, "reasons": reasons, "estimated_difficulty": ["muy baja", "baja", "media", "alta", "muy alta"][diff],
                                      "objective": f"Avanzar en {skill.name}", "top_factors": res["explanation"], "rank": rank + 1,
                                      "course_id": str(course.id), "disclaimer": "Sugerencia de apoyo; no reemplaza el criterio docente."},
                           impact="alto" if rank == 0 or (risk or 0) > 0.6 else "medio" if rank < 3 else "bajo",
                           priority=round(1 - rank * 0.15, 3), confidence=conf, status="new", resource_code=item["code"],
                           expires_at=datetime.now(timezone.utc) + timedelta(days=14))
        db.add(r)
        created.append(r)
        if len(created) >= 5:
            break
    db.flush()
    for r in created:
        emit(db, "recommendation.created", {"id": str(r.id), "title": r.title, "student_id": str(student.id), "impact": r.impact},
             org_id=org_id, aggregate_id=r.id, roles=["superadmin", "admin", "coordinator", "instructor"], user_ids=[student.user_id])
    if created:
        notify(db, org_id, student.user_id, "recommendation.created", f"{len(created)} nuevas recomendaciones de IA", created[0].title, "/recomendaciones")
    return created


@router.get("/recommendations")
def list_recs(status: str | None = None, student_id: uuid.UUID | None = None, limit: int = Query(30, le=200),
              p: Principal = Depends(require("recommendations:read")), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    db.query(Recommendation).filter(Recommendation.organization_id == p.org_id, Recommendation.status == "new",
                                    Recommendation.expires_at < now).update({"status": "expired"})
    db.commit()
    q = select(Recommendation).where(Recommendation.organization_id == p.org_id)
    if p.is_student_only or (p.student_id and not student_id and not p.has("recommendations:review")):
        q = q.where(Recommendation.student_id == p.student_id)
    elif student_id:
        st = get_or_404(db, Student, student_id, p.org_id)
        if not p.can_see_student(db, st):
            raise HTTPException(403, "No autorizado")
        q = q.where(Recommendation.student_id == student_id)
    elif p.scoped_to_assigned_courses:
        q = q.where(Recommendation.student_id.in_(select(Enrollment.student_id).where(Enrollment.course_id.in_(p.instructor_course_ids(db)))))
    if status:
        q = q.where(Recommendation.status == status)
    rows = db.scalars(q.order_by(Recommendation.status != "new", Recommendation.priority.desc(), Recommendation.created_at.desc()).limit(limit)).all()
    stats = dict(db.execute(select(Recommendation.status, func.count()).where(Recommendation.organization_id == p.org_id).group_by(Recommendation.status)).all())
    fb = db.execute(select(func.count().filter(RecommendationFeedback.useful.is_(True)), func.count().filter(RecommendationFeedback.useful.is_not(None)))
                    .join(Recommendation).where(Recommendation.organization_id == p.org_id)).one()
    decided = stats.get("accepted", 0) + stats.get("completed", 0) + stats.get("dismissed", 0)
    return {"items": [rec_dto(r, db, with_student=not p.is_student_only) for r in rows],
            "metrics": {"by_status": stats, "acceptance_rate": round((stats.get("accepted", 0) + stats.get("completed", 0)) / decided, 4) if decided else None,
                        "usefulness_rate": round(fb[0] / fb[1], 4) if fb[1] else None,
                        "note": "Se mide aceptación y utilidad, no solo clics."}}


class GenerateIn(BaseModel):
    student_id: uuid.UUID | None = None


@router.post("/recommendations/generate", status_code=201)
def generate(body: GenerateIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    sid = body.student_id or p.student_id
    if not sid:
        raise HTTPException(422, "Indique el estudiante")
    st = get_or_404(db, Student, sid, p.org_id, "Estudiante no encontrado")
    if not (p.student_id == st.id or (p.has("recommendations:review") and p.can_see_student(db, st))):
        raise HTTPException(403, "No autorizado")
    recs = generate_for_student(db, p, st, p.org_id)
    audit(db, p, "recommendation.generated", "student", st.id, {"count": len(recs)})
    db.commit()
    return {"items": [rec_dto(r, db) for r in recs]}


class FeedbackIn(BaseModel):
    action: str = Field(pattern="^(accepted|dismissed|completed|useful|not_useful)$")
    comment: str | None = Field(None, max_length=1000)


@router.post("/recommendations/{rec_id}/feedback")
def feedback(rec_id: uuid.UUID, body: FeedbackIn, p: Principal = Depends(require("recommendations:read")), db: Session = Depends(get_db)):
    r = get_or_404(db, Recommendation, rec_id, p.org_id, "Recomendación no encontrada")
    st = db.get(Student, r.student_id)
    if p.student_id != r.student_id and not (p.has("recommendations:review") and p.can_see_student(db, st)):
        raise HTTPException(403, "No autorizado")
    if body.action in ("accepted", "dismissed", "completed"):
        if r.status in ("expired",):
            raise HTTPException(409, "La recomendación expiró")
        r.status = body.action
    useful = True if body.action == "useful" else False if body.action == "not_useful" else None
    db.add(RecommendationFeedback(recommendation_id=r.id, user_id=p.id, action=body.action, useful=useful, comment=body.comment))
    audit(db, p, "recommendation.feedback", "recommendation", r.id, {"action": body.action})
    db.commit()
    return rec_dto(r, db)


class ReviewIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)
    override_status: str | None = Field(None, pattern="^(dismissed|accepted)$")


@router.post("/recommendations/{rec_id}/review")
def review(rec_id: uuid.UUID, body: ReviewIn, p: Principal = Depends(require("recommendations:review")), db: Session = Depends(get_db)):
    r = get_or_404(db, Recommendation, rec_id, p.org_id, "Recomendación no encontrada")
    if not p.can_see_student(db, db.get(Student, r.student_id)):
        raise HTTPException(403, "No autorizado")
    r.reviewed_by, r.review_note = p.id, body.note
    if body.override_status:
        r.status = body.override_status
    audit(db, p, "recommendation.reviewed", "recommendation", r.id, body.model_dump())
    db.commit()
    return rec_dto(r, db)
