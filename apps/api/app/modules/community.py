"""Comunidad: espacios por curso, anuncios, debates, respuestas, reportes y moderación."""
from __future__ import annotations

import html
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import Principal, require
from ..core.events import audit, emit, notify
from ..db.base import get_db
from ..db.models import CommunityPost, CommunityThread, ContentReport, Course, Enrollment
from .common import get_or_404

router = APIRouter(tags=["Community"])
BLOCKLIST = re.compile(r"\b(spam|estafa|odio)\b", re.I)


def clean(text: str) -> str:
    return html.escape(text.strip())  # prevención XSS: se almacena escapado


def thread_dto(t: CommunityThread, db: Session, with_posts: bool = False) -> dict:
    d = {"id": t.id, "title": t.title, "body": t.body, "kind": t.kind, "status": t.status, "pinned": t.pinned, "created_at": t.created_at,
         "course_id": t.course_id, "course_title": db.get(Course, t.course_id).title if t.course_id else None,
         "author": {"id": t.author.id, "name": t.author.full_name, "avatar_url": t.author.avatar_url},
         "replies": db.scalar(select(func.count(CommunityPost.id)).where(CommunityPost.thread_id == t.id, CommunityPost.status == "visible"))}
    if with_posts:
        d["posts"] = [{"id": x.id, "body": x.body, "status": x.status, "created_at": x.created_at,
                       "author": {"id": x.author.id, "name": x.author.full_name, "avatar_url": x.author.avatar_url}}
                      for x in db.scalars(select(CommunityPost).where(CommunityPost.thread_id == t.id).order_by(CommunityPost.created_at))
                      if x.status == "visible"]
    return d


def _can_access_course(db: Session, p: Principal, course_id) -> bool:
    if course_id is None:
        return True
    if p.is_student_only:
        return db.scalar(select(Enrollment.id).where(Enrollment.student_id == p.student_id, Enrollment.course_id == course_id)) is not None
    if p.scoped_to_assigned_courses:
        return course_id in p.instructor_course_ids(db)
    return True


@router.get("/community/threads")
def list_threads(course_id: uuid.UUID | None = None, kind: str | None = None, limit: int = Query(30, le=100),
                 p: Principal = Depends(require("community:read")), db: Session = Depends(get_db)):
    q = select(CommunityThread).where(CommunityThread.organization_id == p.org_id)
    if not p.has("community:moderate"):
        q = q.where(CommunityThread.status == "visible")
    if course_id:
        if not _can_access_course(db, p, course_id):
            raise HTTPException(403, "Sin acceso al espacio del curso")
        q = q.where(CommunityThread.course_id == course_id)
    elif p.is_student_only:
        enrolled = select(Enrollment.course_id).where(Enrollment.student_id == p.student_id)
        q = q.where((CommunityThread.course_id.is_(None)) | (CommunityThread.course_id.in_(enrolled)))
    if kind:
        q = q.where(CommunityThread.kind == kind)
    rows = db.scalars(q.order_by(CommunityThread.pinned.desc(), CommunityThread.created_at.desc()).limit(limit)).all()
    reports = db.scalar(select(func.count(ContentReport.id)).where(ContentReport.organization_id == p.org_id, ContentReport.status == "open")) if p.has("community:moderate") else None
    return {"items": [thread_dto(t, db) for t in rows], "open_reports": reports}


class ThreadIn(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    body: str = Field(min_length=2, max_length=10000)
    course_id: uuid.UUID | None = None
    kind: str = Field("discussion", pattern="^(discussion|announcement)$")


@router.post("/community/threads", status_code=201)
def create_thread(body: ThreadIn, p: Principal = Depends(require("community:write")), db: Session = Depends(get_db)):
    if body.kind == "announcement" and not (p.has("community:moderate") or p.has("courses:write")):
        raise HTTPException(403, "Solo docentes/administración publican anuncios")
    if not _can_access_course(db, p, body.course_id):
        raise HTTPException(403, "Sin acceso al espacio del curso")
    flagged = bool(BLOCKLIST.search(body.title + " " + body.body))
    t = CommunityThread(organization_id=p.org_id, course_id=body.course_id, author_id=p.id, kind=body.kind, title=clean(body.title),
                        body=clean(body.body), status="pending" if flagged else "visible", pinned=body.kind == "announcement")
    db.add(t)
    db.flush()
    audit(db, p, "community.thread_created", "thread", t.id, {"flagged": flagged})
    if not flagged:
        emit(db, "community.posted", {"thread_id": str(t.id), "title": t.title, "kind": t.kind}, org_id=p.org_id, aggregate_id=t.id, roles=["*"])
        if body.kind == "announcement" and body.course_id:
            for e in db.scalars(select(Enrollment).where(Enrollment.course_id == body.course_id)):
                from ..db.models import Student
                notify(db, p.org_id, db.get(Student, e.student_id).user_id, "community.announcement", f"Anuncio: {t.title}", "", "/comunidad")
    db.commit()
    return {**thread_dto(t, db), "moderation": "pending" if flagged else "approved"}


@router.get("/community/threads/{thread_id}")
def get_thread(thread_id: uuid.UUID, p: Principal = Depends(require("community:read")), db: Session = Depends(get_db)):
    t = get_or_404(db, CommunityThread, thread_id, p.org_id, "Hilo no encontrado")
    if not _can_access_course(db, p, t.course_id) or (t.status != "visible" and not p.has("community:moderate")):
        raise HTTPException(404, "Hilo no encontrado")
    return thread_dto(t, db, with_posts=True)


class PostIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


@router.post("/community/threads/{thread_id}/posts", status_code=201)
def reply(thread_id: uuid.UUID, body: PostIn, p: Principal = Depends(require("community:write")), db: Session = Depends(get_db)):
    t = get_or_404(db, CommunityThread, thread_id, p.org_id, "Hilo no encontrado")
    if not _can_access_course(db, p, t.course_id):
        raise HTTPException(403, "Sin acceso")
    flagged = bool(BLOCKLIST.search(body.body))
    x = CommunityPost(thread_id=t.id, author_id=p.id, body=clean(body.body), status="pending" if flagged else "visible")
    db.add(x)
    db.flush()
    if not flagged and t.author_id != p.id:
        notify(db, p.org_id, t.author_id, "community.reply", f"Nueva respuesta en: {t.title}", body.body[:120], "/comunidad")
    audit(db, p, "community.post_created", "post", x.id, {"thread": str(t.id), "flagged": flagged})
    db.commit()
    return thread_dto(t, db, with_posts=True)


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    post_id: uuid.UUID | None = None


@router.post("/community/threads/{thread_id}/report", status_code=201)
def report(thread_id: uuid.UUID, body: ReportIn, p: Principal = Depends(require("community:read")), db: Session = Depends(get_db)):
    t = get_or_404(db, CommunityThread, thread_id, p.org_id, "Hilo no encontrado")
    r = ContentReport(organization_id=p.org_id, thread_id=t.id, post_id=body.post_id, reporter_id=p.id, reason=clean(body.reason))
    db.add(r)
    audit(db, p, "community.reported", "thread", t.id, {"reason": body.reason})
    db.commit()
    return {"id": r.id, "status": r.status}


@router.get("/community/reports")
def reports(p: Principal = Depends(require("community:moderate")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ContentReport).where(ContentReport.organization_id == p.org_id).order_by(ContentReport.created_at.desc()).limit(100))
    return [{"id": r.id, "thread_id": r.thread_id, "post_id": r.post_id, "reason": r.reason, "status": r.status, "created_at": r.created_at} for r in rows]


class ModerateIn(BaseModel):
    action: str = Field(pattern="^(hide|restore|pin|unpin|resolve_report|dismiss_report)$")
    report_id: uuid.UUID | None = None


@router.post("/community/threads/{thread_id}/moderate")
def moderate(thread_id: uuid.UUID, body: ModerateIn, p: Principal = Depends(require("community:moderate")), db: Session = Depends(get_db)):
    t = get_or_404(db, CommunityThread, thread_id, p.org_id, "Hilo no encontrado")
    if body.action == "hide":
        t.status = "hidden"
    elif body.action == "restore":
        t.status = "visible"
    elif body.action in ("pin", "unpin"):
        t.pinned = body.action == "pin"
    elif body.report_id:
        r = get_or_404(db, ContentReport, body.report_id, p.org_id)
        r.status, r.resolved_by = ("resolved" if body.action == "resolve_report" else "dismissed"), p.id
    audit(db, p, f"community.{body.action}", "thread", t.id)
    db.commit()
    return thread_dto(t, db)
