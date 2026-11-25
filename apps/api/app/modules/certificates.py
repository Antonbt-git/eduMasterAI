"""Certification: emisión con folio único, PDF + QR, verificación pública mínima, anulación y reemisión."""
from __future__ import annotations

import io
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import Principal, require
from ..core.events import activity, audit, emit, notify
from ..core.infra import store
from ..db.base import get_db
from ..db.models import Certificate, Course, Enrollment, Organization, Student
from .common import get_or_404

router = APIRouter(tags=["Certification"])
public = APIRouter(tags=["Público"])


def cert_dto(c: Certificate, db: Session) -> dict:
    st = db.get(Student, c.student_id)
    course = db.get(Course, c.course_id)
    return {"id": c.id, "folio": c.folio, "verification_code": c.verification_code, "status": c.status, "issued_at": c.issued_at,
            "expires_at": c.expires_at, "template": c.template, "final_score": c.final_score, "revoked_reason": c.revoked_reason,
            "student": {"id": st.id, "name": st.user.full_name}, "course": {"id": course.id, "code": course.code, "title": course.title},
            "verify_url": f"{settings.public_web_url}/verificar/{c.verification_code}"}


def _publish(db: Session, org_id, c: Certificate) -> None:
    """Efectos de negocio al pasar un certificado a estado emitido: evento, actividad y notificación."""
    st = db.get(Student, c.student_id)
    emit(db, "certificate.issued", {"id": str(c.id), "folio": c.folio, "student_id": str(st.id)}, org_id=org_id, aggregate_id=c.id,
         roles=["superadmin", "admin", "coordinator"], user_ids=[st.user_id])
    activity(db, org_id, "certificate_issued", "Certificado emitido correctamente", actor_id=c.issued_by,
             subject_user_id=st.user_id, visibility="org")
    notify(db, org_id, st.user_id, "certificate.issued", "Tu certificado está listo", f"Folio {c.folio}", "/certificados")
    store.invalidate(f"dash:{org_id}")


def issue(db: Session, org_id, enr: Enrollment, actor_id=None, status: str = "issued", template: str = "neon") -> Certificate:
    if enr.status != "completed":
        raise HTTPException(409, "No se cumplen los criterios oficiales de finalización")
    dup = db.scalar(select(Certificate).where(Certificate.student_id == enr.student_id, Certificate.course_id == enr.course_id,
                                              Certificate.status.in_(("issued", "draft"))))
    if dup:
        raise HTTPException(409, "Ya existe un certificado vigente o en borrador para este logro")
    org = db.get(Organization, org_id)
    year = datetime.now(timezone.utc).year
    seq = (db.scalar(select(func.count(Certificate.id)).where(Certificate.organization_id == org_id)) or 0) + 1
    now = datetime.now(timezone.utc)
    c = Certificate(organization_id=org_id, student_id=enr.student_id, course_id=enr.course_id, folio=f"{org.code}-{year}-{seq:06d}",
                    verification_code=secrets.token_urlsafe(9).replace("-", "x").replace("_", "y").upper()[:12], status=status,
                    template=template or "neon",
                    issued_at=now if status == "issued" else None,
                    expires_at=now + timedelta(days=365 * 3) if status == "issued" else None,
                    issued_by=actor_id, final_score=round(enr.progress * 100, 1))
    db.add(c)
    db.flush()
    if status == "issued":
        _publish(db, org_id, c)
    return c


@router.get("/certificates")
def list_certs(status: str | None = None, p: Principal = Depends(require("certificates:read")), db: Session = Depends(get_db)):
    q = select(Certificate).where(Certificate.organization_id == p.org_id)
    if p.is_student_only:
        q = q.where(Certificate.student_id == p.student_id)
    if status:
        q = q.where(Certificate.status == status)
    items = [cert_dto(c, db) for c in db.scalars(q.order_by(Certificate.issued_at.desc().nullslast()).limit(300))]
    eligible = []
    if p.student_id:
        for e in db.scalars(select(Enrollment).where(Enrollment.student_id == p.student_id, Enrollment.status == "completed")):
            if not db.scalar(select(Certificate.id).where(Certificate.student_id == p.student_id, Certificate.course_id == e.course_id,
                                                         Certificate.status.in_(("issued", "draft")))):
                eligible.append({"enrollment_id": e.id, "course_title": db.get(Course, e.course_id).title})
    return {"items": items, "eligible": eligible}


class IssueIn(BaseModel):
    enrollment_id: uuid.UUID


@router.post("/certificates", status_code=201)
def issue_cert(body: IssueIn, p: Principal = Depends(require("certificates:read")), db: Session = Depends(get_db)):
    enr = get_or_404(db, Enrollment, body.enrollment_id, p.org_id, "Matrícula no encontrada")
    if not (p.has("certificates:issue") or p.student_id == enr.student_id):
        raise HTTPException(403, "No autorizado")
    c = issue(db, p.org_id, enr, p.id)
    audit(db, p, "certificate.issued", "certificate", c.id, {"folio": c.folio})
    db.commit()
    return cert_dto(c, db)


class DraftIn(BaseModel):
    enrollment_id: uuid.UUID
    template: str = Field("neon", max_length=40)


@router.post("/certificates/drafts", status_code=201)
def draft_cert(body: DraftIn, p: Principal = Depends(require("certificates:read")), db: Session = Depends(get_db)):
    """Crea un certificado en estado borrador (sin emitir ni notificar)."""
    enr = get_or_404(db, Enrollment, body.enrollment_id, p.org_id, "Matrícula no encontrada")
    if not (p.has("certificates:issue") or p.student_id == enr.student_id):
        raise HTTPException(403, "No autorizado")
    c = issue(db, p.org_id, enr, p.id, status="draft", template=body.template)
    audit(db, p, "certificate.drafted", "certificate", c.id, {"folio": c.folio, "template": c.template})
    db.commit()
    return cert_dto(c, db)


@router.post("/certificates/{cert_id}/issue")
def issue_draft(cert_id: uuid.UUID, p: Principal = Depends(require("certificates:issue")), db: Session = Depends(get_db)):
    c = get_or_404(db, Certificate, cert_id, p.org_id, "Certificado no encontrado")
    if c.status != "draft":
        raise HTTPException(409, "Solo los borradores pueden emitirse")
    now = datetime.now(timezone.utc)
    c.status, c.issued_at, c.expires_at = "issued", now, now + timedelta(days=365 * 3)
    _publish(db, p.org_id, c)
    audit(db, p, "certificate.issued", "certificate", c.id, {"folio": c.folio, "from": "draft"})
    db.commit()
    return cert_dto(c, db)


@router.post("/certificates/{cert_id}/expire")
def expire_cert(cert_id: uuid.UUID, p: Principal = Depends(require("certificates:issue")), db: Session = Depends(get_db)):
    c = get_or_404(db, Certificate, cert_id, p.org_id, "Certificado no encontrado")
    if c.status not in ("issued", "draft"):
        raise HTTPException(409, "Solo certificados emitidos o en borrador pueden expirar")
    c.status = "expired"
    audit(db, p, "certificate.expired", "certificate", c.id, {"folio": c.folio})
    db.commit()
    return cert_dto(c, db)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.post("/certificates/{cert_id}/revoke")
def revoke(cert_id: uuid.UUID, body: RevokeIn, p: Principal = Depends(require("certificates:issue")), db: Session = Depends(get_db)):
    c = get_or_404(db, Certificate, cert_id, p.org_id, "Certificado no encontrado")
    if c.status != "issued":
        raise HTTPException(409, "Solo certificados emitidos pueden anularse")
    c.status, c.revoked_reason = "revoked", body.reason
    audit(db, p, "certificate.revoked", "certificate", c.id, {"reason": body.reason, "folio": c.folio})
    db.commit()
    return cert_dto(c, db)


@router.post("/certificates/{cert_id}/reissue", status_code=201)
def reissue(cert_id: uuid.UUID, p: Principal = Depends(require("certificates:issue")), db: Session = Depends(get_db)):
    c = get_or_404(db, Certificate, cert_id, p.org_id, "Certificado no encontrado")
    if c.status == "issued":
        raise HTTPException(409, "Anule el certificado vigente antes de reemitir")
    enr = db.scalar(select(Enrollment).where(Enrollment.student_id == c.student_id, Enrollment.course_id == c.course_id))
    n = issue(db, p.org_id, enr, p.id)
    audit(db, p, "certificate.reissued", "certificate", n.id, {"previous": c.folio, "new": n.folio})
    db.commit()
    return cert_dto(n, db)


def render_pdf(c: Certificate, db: Session) -> bytes:
    import qrcode
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    st, course, org = db.get(Student, c.student_id), db.get(Course, c.course_id), db.get(Organization, c.organization_id)
    buf = io.BytesIO()
    W, H = landscape(A4)
    pdf = canvas.Canvas(buf, pagesize=(W, H))
    pdf.setTitle(f"Certificado {c.folio}")
    pdf.setFillColor(HexColor("#06152B")); pdf.rect(0, 0, W, H, fill=1, stroke=0)
    for i, col in enumerate(["#087FE5", "#20C8F5", "#8B4DFF"]):
        pdf.setStrokeColor(HexColor(col)); pdf.setLineWidth(1.2)
        pdf.roundRect(24 + i * 6, 24 + i * 6, W - 48 - i * 12, H - 48 - i * 12, 14, stroke=1, fill=0)
    pdf.setStrokeColor(HexColor("#0D2B52"))
    for x in range(60, int(W), 36):
        pdf.line(x, 40, x, 46)
    pdf.setFillColor(HexColor("#20C8F5")); pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(60, H - 80, "EDUMASTER.AI")
    pdf.setFillColor(HexColor("#8FA8C8")); pdf.setFont("Helvetica", 10)
    pdf.drawString(60, H - 96, f"{org.name} · Aprende • Practica • Destaca")
    pdf.setFillColor(HexColor("#FFFFFF")); pdf.setFont("Helvetica-Bold", 38)
    pdf.drawCentredString(W / 2, H - 175, "CERTIFICADO DE LOGRO")
    pdf.setFont("Helvetica", 14); pdf.setFillColor(HexColor("#8FA8C8"))
    pdf.drawCentredString(W / 2, H - 215, "Se otorga a")
    pdf.setFont("Helvetica-Bold", 30); pdf.setFillColor(HexColor("#20C8F5"))
    pdf.drawCentredString(W / 2, H - 258, st.user.full_name)
    pdf.setFont("Helvetica", 14); pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.drawCentredString(W / 2, H - 295, "por completar satisfactoriamente el curso")
    pdf.setFont("Helvetica-Bold", 20); pdf.setFillColor(HexColor("#B794FF"))
    pdf.drawCentredString(W / 2, H - 325, f"{course.title} ({course.code})")
    pdf.setFont("Helvetica", 11); pdf.setFillColor(HexColor("#8FA8C8"))
    pdf.drawString(60, 92, f"Folio: {c.folio}")
    issued_txt = f"{c.issued_at:%d/%m/%Y}" if c.issued_at else "—"
    expires_txt = f"{c.expires_at:%d/%m/%Y}" if c.expires_at else "—"
    pdf.drawString(60, 76, f"Emitido: {issued_txt}   ·   Vigente hasta: {expires_txt}")
    pdf.drawString(60, 60, f"Código de verificación: {c.verification_code}")
    url = f"{settings.public_web_url}/verificar/{c.verification_code}"
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="#06152B", back_color="white")
    ib = io.BytesIO(); img.save(ib, format="PNG"); ib.seek(0)
    pdf.drawImage(ImageReader(ib), W - 170, 52, 110, 110)
    pdf.setFont("Helvetica", 8); pdf.drawRightString(W - 60, 42, "Escanee para verificar")
    if c.status != "issued":
        pdf.setFillColor(HexColor("#FF5470")); pdf.setFont("Helvetica-Bold", 60)
        pdf.saveState(); pdf.translate(W / 2, H / 2); pdf.rotate(20); pdf.drawCentredString(0, 0, c.status.upper()); pdf.restoreState()
    pdf.showPage(); pdf.save()
    return buf.getvalue()


@router.get("/certificates/{cert_id}/pdf")
def download(cert_id: uuid.UUID, p: Principal = Depends(require("certificates:read")), db: Session = Depends(get_db)):
    c = get_or_404(db, Certificate, cert_id, p.org_id, "Certificado no encontrado")
    if p.is_student_only and c.student_id != p.student_id:
        raise HTTPException(404, "Certificado no encontrado")
    audit(db, p, "certificate.downloaded", "certificate", c.id, {"folio": c.folio})
    db.commit()
    return StreamingResponse(iter([render_pdf(c, db)]), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=certificado_{c.folio}.pdf"})


@public.get("/certificates/verify/{code}")
def verify(code: str, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "x"
    if store.hit(f"rl:verify:{ip}", 60) > 30:
        raise HTTPException(429, "Demasiadas consultas")
    c = db.scalar(select(Certificate).where(Certificate.verification_code == code.upper()[:40]))
    if not c:
        raise HTTPException(404, "Código no válido")
    st, course, org = db.get(Student, c.student_id), db.get(Course, c.course_id), db.get(Organization, c.organization_id)
    status = "expired" if c.status == "issued" and c.expires_at and c.expires_at.replace(tzinfo=c.expires_at.tzinfo or timezone.utc) < datetime.now(timezone.utc) else c.status
    parts = st.user.full_name.split()
    return {"valid": status == "issued", "status": status, "folio": c.folio,
            "holder": f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0],  # exposición mínima
            "course": course.title, "institution": org.name, "issued_at": c.issued_at.date().isoformat() if c.issued_at else None,
            "expires_at": c.expires_at.date().isoformat() if c.expires_at else None}
