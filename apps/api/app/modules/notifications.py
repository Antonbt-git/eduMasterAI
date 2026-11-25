"""Notification + actividad reciente (feed cursor-based) + auditoría."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..core.deps import Principal, get_principal, require_any
from ..db.base import get_db
from ..db.models import Activity, AuditLog, Notification, NotificationPreference, User
from .common import apply_cursor, page_out

router = APIRouter(tags=["Notification & Audit"])


@router.get("/notifications")
def list_notifications(cursor: str | None = None, limit: int = Query(20, le=100), unread_only: bool = False,
                       p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == p.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(apply_cursor(q, Notification.created_at, Notification.id, cursor).limit(limit + 1)).all()
    rows, nxt = page_out(list(rows), limit, "created_at")
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == p.id, Notification.read_at.is_(None)))
    return {"items": [{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "link": n.link, "read": n.read_at is not None,
                       "created_at": n.created_at} for n in rows], "next_cursor": nxt, "unread": unread}


@router.post("/notifications/{notif_id}/read")
def mark_read(notif_id: uuid.UUID, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    n = db.get(Notification, notif_id)
    if not n or n.user_id != p.id:
        raise HTTPException(404, "Notificación no encontrada")
    n.read_at = n.read_at or datetime.now(timezone.utc)
    db.commit()
    return {"id": n.id, "read": True}


@router.post("/notifications/read-all")
def read_all(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == p.id, Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"ok": True}


class PrefsIn(BaseModel):
    muted_types: list[str] = []
    muted_courses: list[uuid.UUID] = []


@router.get("/notifications/preferences")
def get_prefs(p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pref = db.get(NotificationPreference, p.id)
    return {"muted_types": pref.muted_types if pref else [], "muted_courses": pref.muted_courses if pref else [],
            "available_types": ["course.completed", "assessment.published", "assessment.graded", "recommendation.created", "certificate.issued",
                                "community.reply", "community.announcement", "path.assigned", "attempt.pending"]}


@router.put("/notifications/preferences")
def put_prefs(body: PrefsIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    pref = db.get(NotificationPreference, p.id) or NotificationPreference(user_id=p.id)
    pref.muted_types, pref.muted_courses = body.muted_types, [str(c) for c in body.muted_courses]
    db.add(pref)
    db.commit()
    return get_prefs(p, db)


@router.get("/activity")
def feed(cursor: str | None = None, limit: int = Query(20, le=100), type: str | None = None,
         p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    q = select(Activity).where(Activity.organization_id == p.org_id)
    if p.is_student_only:  # nunca exponer información de otros estudiantes
        q = q.where(or_(Activity.subject_user_id == p.id, Activity.actor_id == p.id, (Activity.visibility == "org") & Activity.subject_user_id.is_(None)))
    if type:
        q = q.where(Activity.type == type)
    rows = db.scalars(apply_cursor(q, Activity.created_at, Activity.id, cursor).limit(limit + 1)).all()
    rows, nxt = page_out(list(rows), limit, "created_at")
    return {"items": [{"id": a.id, "type": a.type, "title": a.title, "created_at": a.created_at} for a in rows], "next_cursor": nxt}


@router.get("/audit-logs")
def audit_logs(cursor: str | None = None, limit: int = Query(50, le=200), action: str | None = None, resource: str | None = None,
               p: Principal = Depends(require_any("audit:read", "audit:read_own")), db: Session = Depends(get_db)):
    q = select(AuditLog).where(AuditLog.organization_id == p.org_id)
    if not p.has("audit:read"):
        q = q.where(AuditLog.actor_id == p.id)
        if "ml_engineer" in p.roles:
            q = select(AuditLog).where(or_(AuditLog.actor_id == p.id, AuditLog.action.like("model.%"), AuditLog.action.like("dataset.%")))
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    if resource:
        q = q.where(AuditLog.resource == resource)
    rows = db.scalars(apply_cursor(q, AuditLog.occurred_at, AuditLog.id, cursor, id_is_uuid=False).limit(limit + 1)).all()
    rows, nxt = page_out(list(rows), limit, "occurred_at")
    return {"items": [{"id": a.id, "action": a.action, "resource": a.resource, "resource_id": a.resource_id, "actor_email": a.actor_email,
                       "occurred_at": a.occurred_at, "ip": a.ip, "correlation_id": a.correlation_id, "details": a.details, "hash": a.hash[:12]}
                      for a in rows], "next_cursor": nxt}


@router.get("/audit-logs/verify")
def verify_chain(p: Principal = Depends(require_any("audit:read")), db: Session = Depends(get_db)):
    """Recalcula la cadena hash completa: detecta alteraciones o borrados en la bitácora."""
    prev, n, broken = None, 0, []
    for a in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        entry = {"org": str(a.organization_id or ""), "actor": str(a.actor_id) if a.actor_id else None, "action": a.action, "resource": a.resource,
                 "resource_id": a.resource_id, "at": a.occurred_at.isoformat() if a.occurred_at.tzinfo else a.occurred_at.replace(tzinfo=timezone.utc).isoformat(),
                 "details": a.details or {}, "prev": prev}
        h = hashlib.sha256(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()
        if a.prev_hash != prev or h != a.hash:
            broken.append(a.id)
        prev = a.hash
        n += 1
    return {"entries": n, "valid": not broken, "broken_ids": broken[:20], "checked_at": datetime.now(timezone.utc).isoformat()}
