"""Auditoría encadenada por hash + patrón Outbox para eventos de dominio + feed/notificaciones."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db.models import Activity, AuditLog, Notification, NotificationPreference, OutboxEvent
from .observability import correlation_id_var

SCHEMA_VERSIONS = {
    "learning.progress.updated": 1, "assessment.submitted": 1, "course.completed": 1, "recommendation.created": 1,
    "model.training.started": 1, "model.training.progress": 1, "model.training.completed": 1, "model.training.failed": 1,
    "model.deployed": 1, "model.inference": 1, "notification.created": 1, "activity.created": 1, "dataset.updated": 1,
    "certificate.issued": 1, "community.posted": 1,
}


def audit(db: Session, principal, action: str, resource: str, resource_id=None, details: dict | None = None,
          org_id=None, actor_email: str | None = None) -> AuditLog:
    if db.bind.dialect.name == "postgresql":  # serializa la cadena hash entre transacciones concurrentes
        db.execute(text("SELECT pg_advisory_xact_lock(424242)"))
    prev = db.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1))
    now = datetime.now(timezone.utc)
    details = json.loads(json.dumps(details or {}, default=str))
    entry = {
        "org": str(org_id or (principal.org_id if principal else "")),
        "actor": str(principal.id) if principal else None,
        "action": action, "resource": resource, "resource_id": str(resource_id) if resource_id else None,
        "at": now.isoformat(), "details": details or {}, "prev": prev,
    }
    h = hashlib.sha256(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()
    log = AuditLog(
        organization_id=org_id or (principal.org_id if principal else None),
        actor_id=principal.id if principal else None,
        actor_email=actor_email or (principal.user.email if principal else None),
        action=action, resource=resource, resource_id=entry["resource_id"], occurred_at=now,
        ip=getattr(principal, "ip", None), correlation_id=correlation_id_var.get(), details=details or {},
        prev_hash=prev, hash=h,
    )
    db.add(log)
    db.flush()
    return log


def emit(db: Session, event_type: str, payload: dict, org_id=None, actor_id=None, aggregate_id=None,
         roles: list[str] | None = None, user_ids: list | None = None) -> OutboxEvent:
    """Registra el evento en la MISMA transacción del cambio de negocio (Outbox)."""
    ev = OutboxEvent(
        event_id=uuid.uuid4(), event_type=event_type, occurred_at=datetime.now(timezone.utc),
        organization_id=org_id, actor_id=actor_id, aggregate_id=str(aggregate_id) if aggregate_id else None,
        schema_version=SCHEMA_VERSIONS.get(event_type, 1), correlation_id=correlation_id_var.get(),
        payload=json.loads(json.dumps(payload, default=str)),
        audience={"roles": roles or [], "user_ids": [str(u) for u in (user_ids or [])]},
    )
    db.add(ev)
    return ev


def activity(db: Session, org_id, type_: str, title: str, actor_id=None, subject_user_id=None, visibility="staff") -> Activity:
    a = Activity(organization_id=org_id, type=type_, title=title, actor_id=actor_id, subject_user_id=subject_user_id, visibility=visibility)
    db.add(a)
    db.flush()
    users = [subject_user_id] if subject_user_id else []
    emit(db, "activity.created", {"id": str(a.id), "type": type_, "title": title, "created_at": a.created_at.isoformat(), "visibility": visibility},
         org_id=org_id, actor_id=actor_id, aggregate_id=a.id,
         roles=["superadmin", "admin", "coordinator", "instructor"] + (["*"] if visibility == "org" else []), user_ids=users)
    return a


def notify(db: Session, org_id, user_id, type_: str, title: str, body: str = "", link: str | None = None) -> Notification | None:
    pref = db.get(NotificationPreference, user_id)
    if pref and type_ in (pref.muted_types or []):
        return None
    n = Notification(organization_id=org_id, user_id=user_id, type=type_, title=title, body=body, link=link)
    db.add(n)
    db.flush()
    emit(db, "notification.created", {"id": str(n.id), "type": type_, "title": title, "body": body, "link": link,
                                      "created_at": n.created_at.isoformat()},
         org_id=org_id, aggregate_id=n.id, user_ids=[user_id])
    return n
