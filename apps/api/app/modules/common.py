"""Utilidades compartidas: paginación por cursor, DTO base, helpers de alcance."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

T = TypeVar("T")


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None


def encode_cursor(ts: datetime, id_: Any) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{id_}".encode()).decode()


def decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        ts, id_ = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(ts), id_
    except Exception:
        raise HTTPException(400, "Cursor inválido")


def apply_cursor(stmt, ts_col, id_col, cursor: str | None, id_is_uuid: bool = True):
    """Orden estable (ts DESC, id DESC) + filtro por cursor."""
    c = decode_cursor(cursor)
    if c:
        ts, id_ = c
        idv = uuid.UUID(id_) if id_is_uuid else int(id_)
        stmt = stmt.where(or_(ts_col < ts, and_(ts_col == ts, id_col < idv)))
    return stmt.order_by(ts_col.desc(), id_col.desc())


def page_out(rows: list, limit: int, ts_attr: str, id_attr: str = "id") -> tuple[list, str | None]:
    more = len(rows) > limit
    rows = rows[:limit]
    nxt = encode_cursor(getattr(rows[-1], ts_attr), getattr(rows[-1], id_attr)) if more and rows else None
    return rows, nxt


def get_or_404(db: Session, model, id_, org_id=None, msg: str = "No encontrado"):
    obj = db.get(model, id_)
    if not obj or (org_id is not None and getattr(obj, "organization_id", org_id) != org_id):
        raise HTTPException(404, msg)  # 404 también para otro tenant: no revela existencia
    return obj
