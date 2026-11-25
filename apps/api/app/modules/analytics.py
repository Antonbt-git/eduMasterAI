"""Analytics: KPIs con fuente/fecha/variación, series, mapa, finalización, heatmap y exportación auditada.

Las series y KPIs se leen de agregados (`daily_metrics`) + caché con TTL e invalidación por eventos.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import Principal, require
from ..core.events import audit
from ..core.infra import store
from ..db.base import get_db
from ..db.models import (
    AssessmentAttempt, Assessment, Certificate, Cohort, Course, CourseOffering, DailyMetric, Enrollment, LearningEvent,
    ModelVersion, Skill, SkillEvidence, Student,
)

router = APIRouter(tags=["Analytics"])
LEVEL_LABELS = ["Aprender", "Practicar", "Aplicar", "Avanzado", "Experto"]
REGIONS = ["América del Norte", "América del Sur", "Europa", "Asia", "África", "Oceanía"]
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
PERIODS = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}


class Filters:
    def __init__(self, period: str = Query("30d", pattern="^(7d|30d|90d|365d)$"), course_id: uuid.UUID | None = None,
                 cohort_id: uuid.UUID | None = None, region: str | None = None, date_from: date | None = None, date_to: date | None = None):
        self.period, self.course_id, self.cohort_id, self.region = period, course_id, cohort_id, region
        today = datetime.now(timezone.utc).date()
        self.end = date_to or today
        self.start = date_from or (self.end - timedelta(days=PERIODS[period] - 1))
        if self.start > self.end:
            raise HTTPException(422, "Rango de fechas inválido")
        span = (self.end - self.start).days + 1
        self.prev_end = self.start - timedelta(days=1)
        self.prev_start = self.prev_end - timedelta(days=span - 1)

    def key(self) -> str:
        return f"{self.start}:{self.end}:{self.course_id}:{self.cohort_id}:{self.region}"

    def as_dict(self) -> dict:
        return {"period": self.period, "from": str(self.start), "to": str(self.end), "course_id": str(self.course_id) if self.course_id else None,
                "cohort_id": str(self.cohort_id) if self.cohort_id else None, "region": self.region}


def _course_scope(db: Session, p: Principal, f: Filters) -> list[uuid.UUID] | None:
    ids = None
    if p.scoped_to_assigned_courses:
        ids = set(p.instructor_course_ids(db))
    if f.cohort_id:
        coh = set(db.scalars(select(CourseOffering.course_id).where(CourseOffering.cohort_id == f.cohort_id)))
        ids = coh if ids is None else ids & coh
    if f.course_id:
        ids = {f.course_id} if ids is None else ids & {f.course_id}
    return list(ids) if ids is not None else None


def _dm(db, p, f, start, end, scope):
    q = select(func.coalesce(func.sum(DailyMetric.learning_seconds), 0), func.coalesce(func.sum(DailyMetric.events), 0),
               func.coalesce(func.sum(DailyMetric.completions), 0), func.coalesce(func.sum(DailyMetric.assessments), 0)) \
        .where(DailyMetric.organization_id == p.org_id, DailyMetric.day >= start, DailyMetric.day <= end)
    if scope is not None:
        q = q.where(DailyMetric.course_id.in_(scope))
    if f.region:
        q = q.where(DailyMetric.region == f.region)
    return db.execute(q).one()


def _active(db, p, f, start, end, scope):
    q = select(func.count(func.distinct(LearningEvent.student_id))).where(
        LearningEvent.organization_id == p.org_id,
        LearningEvent.occurred_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
        LearningEvent.occurred_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))
    if scope is not None:
        q = q.where(LearningEvent.course_id.in_(scope))
    if f.region:
        q = q.where(LearningEvent.student_id.in_(select(Student.id).where(Student.region == f.region)))
    return db.scalar(q) or 0


def _delta(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def _enr_q(p, f, scope):
    q = select(Enrollment).where(Enrollment.organization_id == p.org_id)
    if scope is not None:
        q = q.where(Enrollment.course_id.in_(scope))
    if f.region:
        q = q.where(Enrollment.student_id.in_(select(Student.id).where(Student.region == f.region)))
    return q


@router.get("/dashboard/summary")
def dashboard_summary(f: Filters = Depends(), p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    ck = f"dash:{p.org_id}:summary:{f.key()}:{','.join(sorted(p.roles))}"
    if cached := store.get_json(ck):
        return {**cached, "cache": "hit"}
    scope = _course_scope(db, p, f)
    now = datetime.now(timezone.utc)
    cur, prev = _dm(db, p, f, f.start, f.end, scope), _dm(db, p, f, f.prev_start, f.prev_end, scope)
    act_c, act_p = _active(db, p, f, f.start, f.end, scope), _active(db, p, f, f.prev_start, f.prev_end, scope)
    courses_q = select(func.count(Course.id)).where(Course.organization_id == p.org_id, Course.status == "published")
    if scope is not None:
        courses_q = courses_q.where(Course.id.in_(scope))
    n_courses = db.scalar(courses_q)
    n_courses_prev = db.scalar(courses_q.where(Course.created_at < datetime.combine(f.start, datetime.min.time(), tzinfo=timezone.utc)))
    cert_q = select(func.count(Certificate.id)).where(Certificate.organization_id == p.org_id, Certificate.status == "issued")
    if scope is not None:
        cert_q = cert_q.where(Certificate.course_id.in_(scope))
    certs_total = db.scalar(cert_q)
    certs_c = db.scalar(cert_q.where(Certificate.issued_at >= datetime.combine(f.start, datetime.min.time(), tzinfo=timezone.utc)))
    certs_p = db.scalar(cert_q.where(Certificate.issued_at >= datetime.combine(f.prev_start, datetime.min.time(), tzinfo=timezone.utc),
                                     Certificate.issued_at < datetime.combine(f.start, datetime.min.time(), tzinfo=timezone.utc)))
    eq = _enr_q(p, f, scope).subquery()
    tot, done = db.execute(select(func.count(), func.count().filter(eq.c.status == "completed")).select_from(eq)).one()
    online = db.scalar(select(func.count(func.distinct(LearningEvent.student_id))).where(
        LearningEvent.organization_id == p.org_id, LearningEvent.occurred_at >= now - timedelta(minutes=15))) or 0
    score_q = select(func.avg(AssessmentAttempt.score / Assessment.max_score)).join(Assessment).where(Assessment.organization_id == p.org_id)
    if scope is not None:
        score_q = score_q.where(Assessment.course_id.in_(scope))
    global_score = db.scalar(score_q.where(AssessmentAttempt.submitted_at >= now - timedelta(days=PERIODS[f.period])))
    spark = [round(float(v or 0), 3) for (v,) in db.execute(
        select(func.avg(AssessmentAttempt.score / Assessment.max_score)).join(Assessment)
        .where(Assessment.organization_id == p.org_id, AssessmentAttempt.submitted_at >= now - timedelta(days=84))
        .group_by(func.date_trunc("week", AssessmentAttempt.submitted_at) if db.bind.dialect.name == "postgresql" else func.strftime("%W", AssessmentAttempt.submitted_at))
        .order_by(func.min(AssessmentAttempt.submitted_at))).all()]
    prod = db.scalar(select(ModelVersion).where(ModelVersion.stage == "production").order_by(ModelVersion.network_key == "edumaster_mtl", ModelVersion.promoted_at.desc()).limit(1))
    if prod is None:
        prod = db.scalar(select(ModelVersion).where(ModelVersion.stage == "production").order_by(ModelVersion.promoted_at.desc()).limit(1))
    src = "daily_metrics (agregado incremental)"
    res = {
        "filters": f.as_dict(), "generated_at": now.isoformat(), "label": "DEMO",
        "kpis": {
            "active_students": {"value": act_c, "delta_pct": _delta(act_c, act_p), "source": "learning_events (distinct estudiantes)", "updated_at": now.isoformat(), "unit": "estudiantes"},
            "courses": {"value": n_courses, "delta_pct": _delta(n_courses, n_courses_prev), "source": "courses (publicados)", "updated_at": now.isoformat(), "unit": "cursos"},
            "learning_hours": {"value": round(cur[0] / 3600, 1), "delta_pct": _delta(cur[0], prev[0]), "source": src, "updated_at": now.isoformat(), "unit": "h"},
            "certifications": {"value": certs_total, "period_value": certs_c, "delta_pct": _delta(certs_c, certs_p), "source": "certificates (emitidos)", "updated_at": now.isoformat(), "unit": "certificados"},
            "completion_rate": {"value": round(done / tot, 4) if tot else 0, "completed": done, "total": tot, "source": "enrollments", "updated_at": now.isoformat(), "unit": "%"},
            "global_score": {"value": round(float(global_score), 4) if global_score is not None else None, "spark": spark, "source": "assessment_attempts (promedio normalizado)", "updated_at": now.isoformat(), "unit": "%"},
            "online_now": {"value": online, "source": "eventos últimos 15 min", "updated_at": now.isoformat()},
            "model_quality": ({"value": prod.primary_metric, "baseline": prod.baseline_metric, "network": prod.network_key, "version": prod.version,
                               "metric": (prod.metrics or {}).get("primary_metric_name"), "dataset": prod.dataset_version, "label": "DEMO",
                               "source": "model_versions (producción)", "updated_at": (prod.promoted_at or prod.created_at).isoformat()}
                              if prod else {"value": None, "source": "Sin modelo en producción", "updated_at": now.isoformat()}),
        },
    }
    store.set_json(ck, res, ex=30)
    return {**res, "cache": "miss"}


@router.get("/analytics/progress")
def progress_series(f: Filters = Depends(), months: int = Query(12, ge=3, le=24), p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    scope = _course_scope(db, p, f)
    end = f.end
    start = (end.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    is_pg = db.bind.dialect.name == "postgresql"
    bucket = func.to_char(DailyMetric.day, "YYYY-MM") if is_pg else func.strftime("%Y-%m", DailyMetric.day)
    q = select(bucket, func.sum(DailyMetric.learning_seconds), func.sum(DailyMetric.active_students), func.sum(DailyMetric.completions),
               func.sum(DailyMetric.assessments), func.sum(DailyMetric.events)) \
        .where(DailyMetric.organization_id == p.org_id, DailyMetric.day >= start, DailyMetric.day <= end).group_by(bucket).order_by(bucket)
    if scope is not None:
        q = q.where(DailyMetric.course_id.in_(scope))
    if f.region:
        q = q.where(DailyMetric.region == f.region)
    rows = {r[0]: r for r in db.execute(q).all()}
    labels, hours, active, completions, assessments = [], [], [], [], []
    d = start
    while d <= end:
        k = d.strftime("%Y-%m")
        r = rows.get(k)
        labels.append(f"{MONTHS[d.month - 1]} {str(d.year)[2:]}")
        hours.append(round((r[1] or 0) / 3600, 1) if r else 0)
        active.append(int(r[2] or 0) if r else 0)
        completions.append(int(r[3] or 0) if r else 0)
        assessments.append(int(r[4] or 0) if r else 0)
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {"labels": labels, "series": [
        {"key": "learning_hours", "name": "Horas de aprendizaje", "unit": "h", "data": hours},
        {"key": "active_students", "name": "Estudiantes activos (día-estudiante)", "unit": "estudiantes", "data": active},
        {"key": "completions", "name": "Cursos completados", "unit": "cursos", "data": completions},
        {"key": "assessments", "name": "Evaluaciones entregadas", "unit": "entregas", "data": assessments},
    ], "source": "daily_metrics", "filters": f.as_dict(), "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Sin facturación en alcance: el panel de ingresos se sustituye por métricas académicas (documento maestro §4.1)."}


@router.get("/analytics/geo")
def geo(f: Filters = Depends(), p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    scope = _course_scope(db, p, f)
    out = []
    for region in REGIONS:
        rf = Filters(period=f.period, course_id=f.course_id, cohort_id=f.cohort_id, region=region, date_from=f.start, date_to=f.end)
        cur, prev = _active(db, p, rf, f.start, f.end, scope), _active(db, p, rf, f.prev_start, f.prev_end, scope)
        students = db.scalar(select(func.count(Student.id)).where(Student.organization_id == p.org_id, Student.region == region))
        prog = db.scalar(select(func.avg(Enrollment.progress)).join(Student, Student.id == Enrollment.student_id)
                         .where(Enrollment.organization_id == p.org_id, Student.region == region))
        out.append({"region": region, "students": students, "active": cur, "delta_pct": _delta(cur, prev), "avg_progress": round(float(prog or 0), 4)})
    return {"regions": out, "note": "Datos agregados por región; nunca ubicación individual.", "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/analytics/completion")
def completion(f: Filters = Depends(), p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    scope = _course_scope(db, p, f)
    eq = _enr_q(p, f, scope).subquery()
    rows = dict(db.execute(select(eq.c.status, func.count()).select_from(eq).group_by(eq.c.status)).all())
    total = sum(rows.values()) or 1
    is_pg = db.bind.dialect.name == "postgresql"
    wk = func.date_trunc("week", Enrollment.completed_at) if is_pg else func.strftime("%Y-%W", Enrollment.completed_at)
    q = select(wk, func.count()).where(Enrollment.organization_id == p.org_id, Enrollment.completed_at.is_not(None),
                                       Enrollment.completed_at >= datetime.now(timezone.utc) - timedelta(weeks=26)).group_by(wk).order_by(wk)
    if scope is not None:
        q = q.where(Enrollment.course_id.in_(scope))
    weekly = [int(r[1]) for r in db.execute(q).all()]
    return {"total": sum(rows.values()), "breakdown": [
        {"status": "completed", "label": "Completados", "count": rows.get("completed", 0), "pct": round(rows.get("completed", 0) / total, 4)},
        {"status": "in_progress", "label": "En progreso", "count": rows.get("in_progress", 0), "pct": round(rows.get("in_progress", 0) / total, 4)},
        {"status": "not_started", "label": "No iniciados", "count": rows.get("not_started", 0) + rows.get("dropped", 0),
         "pct": round((rows.get("not_started", 0) + rows.get("dropped", 0)) / total, 4)},
    ], "weekly_completions": weekly, "source": "enrollments", "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/analytics/skill-mastery")
def skill_mastery(source: str = Query("validated", pattern="^(validated|ai)$"), f: Filters = Depends(),
                  p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    types = ["assessment", "instructor"] if source == "validated" else ["ai_estimate"]
    skills = db.scalars(select(Skill).where(Skill.organization_id == p.org_id, Skill.parent_skill_id.is_(None)).order_by(Skill.code)).all()
    latest = select(SkillEvidence.student_id, SkillEvidence.skill_id, func.max(SkillEvidence.level).label("lvl")) \
        .join(Student, Student.id == SkillEvidence.student_id) \
        .where(Student.organization_id == p.org_id, SkillEvidence.source_type.in_(types))
    if f.region:
        latest = latest.where(Student.region == f.region)
    latest = latest.group_by(SkillEvidence.student_id, SkillEvidence.skill_id).subquery()
    counts = db.execute(select(latest.c.skill_id, latest.c.lvl, func.count()).group_by(latest.c.skill_id, latest.c.lvl)).all()
    by = {}
    for sid, lvl, n in counts:
        by.setdefault(sid, [0] * 5)[int(lvl)] += n
    matrix = []
    for i, s in enumerate(skills):
        row = by.get(s.id, [0] * 5)
        tot = sum(row) or 1
        for j, n in enumerate(row):
            matrix.append([j, i, round(n / tot * 100, 1)])
    return {"skills": [{"id": s.id, "name": s.name, "color": s.color} for s in skills], "levels": LEVEL_LABELS, "matrix": matrix,
            "source": "skill_evidence: " + ("evaluación/docente (validado)" if source == "validated" else "estimación IA (no certificada)"),
            "label": "Validado" if source == "validated" else "Estimación IA", "generated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/analytics/courses")
def course_table(f: Filters = Depends(), p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    scope = _course_scope(db, p, f)
    q = select(Course).where(Course.organization_id == p.org_id)
    if scope is not None:
        q = q.where(Course.id.in_(scope))
    rows = []
    since = datetime.combine(f.start, datetime.min.time(), tzinfo=timezone.utc)
    for c in db.scalars(q.order_by(Course.code)):
        e = db.execute(select(func.count(), func.avg(Enrollment.progress), func.count().filter(Enrollment.status == "completed"))
                       .where(Enrollment.course_id == c.id)).one()
        ev = db.execute(select(func.count(), func.coalesce(func.sum(LearningEvent.duration_seconds), 0), func.count(func.distinct(LearningEvent.student_id)))
                        .where(LearningEvent.course_id == c.id, LearningEvent.occurred_at >= since)).one()
        at = db.execute(select(func.count(), func.avg(AssessmentAttempt.score / Assessment.max_score), func.count().filter(AssessmentAttempt.late.is_(True)))
                        .join(Assessment).where(Assessment.course_id == c.id, AssessmentAttempt.submitted_at >= since)).one()
        rows.append({"course_id": c.id, "code": c.code, "title": c.title, "status": c.status, "enrolled": e[0],
                     "avg_progress": round(float(e[1] or 0), 4), "completion_rate": round(e[2] / e[0], 4) if e[0] else 0,
                     "participation": round(ev[2] / e[0], 4) if e[0] else 0, "active_hours": round(ev[1] / 3600, 1), "events": ev[0],
                     "submissions": at[0], "avg_score": round(float(at[1]), 4) if at[1] is not None else None, "late_submissions": at[2]})
    return {"items": rows, "filters": f.as_dict(), "definitions": {
        "participation": "Estudiantes con ≥1 evento en el periodo / matriculados",
        "active_hours": "Suma de duración acotada de eventos (no equivale a atención real)",
        "completion_rate": "Matrículas completadas / matrículas totales",
        "avg_score": "Promedio de puntaje normalizado (0–1) de intentos en el periodo"}}


@router.get("/analytics/export")
def export(report: str = Query("courses", pattern="^(courses|summary)$"), format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
           f: Filters = Depends(), p: Principal = Depends(require("analytics:export")), db: Session = Depends(get_db)):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if report == "courses":
        data = course_table(f, p, db)["items"]
        headers = ["code", "title", "status", "enrolled", "avg_progress", "completion_rate", "participation", "active_hours", "submissions", "avg_score", "late_submissions"]
        rows = [[r[h] for h in headers] for r in data]
    else:
        k = dashboard_summary(f, p, db)["kpis"]
        headers = ["kpi", "valor", "variacion_pct", "fuente", "actualizado"]
        rows = [[name, v.get("value"), v.get("delta_pct"), v.get("source"), v.get("updated_at")] for name, v in k.items()]
    meta = [f"EduMaster.ai — reporte '{report}' (DEMO)", f"Generado: {stamp} por {p.user.email}", f"Filtros: {f.as_dict()}"]
    audit(db, p, "analytics.exported", "report", report, {"format": format, "filters": f.as_dict(), "rows": len(rows)})
    db.commit()
    fname = f"edumaster_{report}_{date.today()}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        for m in meta:
            w.writerow([f"# {m}"])
        w.writerow(headers)
        w.writerows(rows)
        return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fname}.csv"})
    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        wb = Workbook()
        ws = wb.active
        ws.title = report
        for m in meta:
            ws.append([m])
        ws.append([])
        ws.append(headers)
        for c in ws[ws.max_row]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="087FE5")
        for r in rows:
            ws.append([str(x) if isinstance(x, (uuid.UUID, dict)) else x for x in r])
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18
        out = io.BytesIO()
        wb.save(out)
        return StreamingResponse(iter([out.getvalue()]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename={fname}.xlsx"})
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=f"EduMaster {report}")
    st = getSampleStyleSheet()
    table = Table([headers] + [[str(x)[:40] if x is not None else "—" for x in r] for r in rows], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#087FE5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#0D2B52")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF6FF")])]))
    doc.build([Paragraph(meta[0], st["Title"]), Paragraph(meta[1], st["Normal"]), Paragraph(meta[2], st["Normal"]), Spacer(1, 12), table])
    return StreamingResponse(iter([out.getvalue()]), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={fname}.pdf"})


@router.get("/cohorts/{cohort_id}/summary")
def cohort_summary(cohort_id: uuid.UUID, p: Principal = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    c = db.get(Cohort, cohort_id)
    if not c or c.organization_id != p.org_id:
        raise HTTPException(404, "Cohorte no encontrada")
    courses = list(db.scalars(select(CourseOffering.course_id).where(CourseOffering.cohort_id == c.id)))
    e = db.execute(select(func.count(), func.avg(Enrollment.progress)).where(Enrollment.course_id.in_(courses))).one() if courses else (0, 0)
    return {"cohort": {"id": c.id, "name": c.name}, "courses": len(courses), "enrollments": e[0], "avg_progress": round(float(e[1] or 0), 4)}
