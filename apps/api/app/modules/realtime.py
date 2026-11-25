"""Tiempo real: publicador Outbox → broker (Redis pub/sub) → SSE autorizado por institución/rol/usuario.

- El cliente obtiene un ticket de un solo uso (60 s) para abrir EventSource sin exponer el JWT en la URL.
- Reconexión: el navegador envía Last-Event-ID (= seq del outbox) y el servidor re-envía lo pendiente.
- Nunca hay canal global: cada conexión se suscribe al canal de SU institución y se filtra por audiencia.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sse_starlette.sse import EventSourceResponse

from ..core.deps import Principal, build_principal, get_principal
from ..core.infra import broker, store
from ..core.observability import log
from ..db.base import SessionLocal
from ..db.models import OutboxEvent, User

router = APIRouter(tags=["Realtime"])


def event_wire(e: OutboxEvent) -> dict:
    return {"seq": e.seq, "event_id": str(e.event_id), "event_type": e.event_type, "occurred_at": e.occurred_at.isoformat(),
            "organization_id": str(e.organization_id) if e.organization_id else None, "actor_id": str(e.actor_id) if e.actor_id else None,
            "aggregate_id": e.aggregate_id, "schema_version": e.schema_version, "correlation_id": e.correlation_id,
            "payload": e.payload, "audience": e.audience}


def allowed(msg: dict, user_id: str, roles: set[str]) -> bool:
    aud = msg.get("audience") or {}
    if user_id in (aud.get("user_ids") or []):
        return True
    r = set(aud.get("roles") or [])
    return "*" in r or bool(r & roles)


@router.post("/realtime/ticket")
def ticket(p: Principal = Depends(get_principal)):
    t = secrets.token_urlsafe(24)
    store.set(f"sse:ticket:{t}", str(p.id), ex=60)
    return {"ticket": t, "expires_in": 60}


@router.get("/realtime/stream")
async def stream(request: Request, ticket: str, last_event_id: int | None = None):
    uid = store.pop(f"sse:ticket:{ticket}")
    if not uid:
        raise HTTPException(401, "Ticket inválido o expirado")
    with SessionLocal() as db:
        user = db.get(User, uuid.UUID(uid))
        p = build_principal(db, user)
        org_id, roles, user_id = str(p.org_id), p.roles, str(p.id)
        hdr = request.headers.get("Last-Event-ID")
        since = int(hdr) if hdr and hdr.isdigit() else last_event_id
        backlog = []
        if since:
            backlog = [event_wire(e) for e in db.scalars(select(OutboxEvent).where(
                OutboxEvent.organization_id == p.org_id, OutboxEvent.seq > since, OutboxEvent.published_at.is_not(None))
                .order_by(OutboxEvent.seq).limit(500))]

    async def gen():
        yield {"event": "hello", "data": json.dumps({"connected_at": datetime.now(timezone.utc).isoformat(), "replayed": len(backlog)})}
        for m in backlog:
            if allowed(m, user_id, roles):
                m.pop("audience", None)
                yield {"id": str(m["seq"]), "event": m["event_type"], "data": json.dumps(m)}
        async for raw in broker.subscribe(f"org:{org_id}"):
            if await request.is_disconnected():
                break
            if raw is None:
                yield {"event": "heartbeat", "data": json.dumps({"at": datetime.now(timezone.utc).isoformat()})}
                continue
            m = json.loads(raw)
            if allowed(m, user_id, roles):
                m.pop("audience", None)
                yield {"id": str(m["seq"]), "event": m["event_type"], "data": json.dumps(m)}

    return EventSourceResponse(gen(), ping=20, headers={"X-Accel-Buffering": "no"})


async def outbox_publisher(stop: asyncio.Event, interval: float = 0.4):
    """Publica eventos confirmados. Con varias réplicas usa FOR UPDATE SKIP LOCKED (PostgreSQL)."""
    while not stop.is_set():
        try:
            with SessionLocal() as db:
                q = select(OutboxEvent).where(OutboxEvent.published_at.is_(None)).order_by(OutboxEvent.seq).limit(200)
                if db.bind.dialect.name == "postgresql":
                    q = q.with_for_update(skip_locked=True)
                rows = db.scalars(q).all()
                for e in rows:
                    await broker.publish(f"org:{e.organization_id}", event_wire(e))
                if rows:
                    db.execute(update(OutboxEvent).where(OutboxEvent.seq.in_([e.seq for e in rows])).values(published_at=datetime.now(timezone.utc)))
                    db.commit()
        except Exception as exc:  # degradación elegante
            log.warning("outbox_publisher_error", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
