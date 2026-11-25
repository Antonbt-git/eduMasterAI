"""IA Tutor: contexto autorizado del estudiante + LLM externo opcional (Anthropic / OpenAI-compatible).

Sin API key configurada responde con un tutor basado en reglas y recomendaciones del modelo propio.
El contexto enviado al LLM está minimizado (sin email, sin identificadores directos).
"""
from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import Principal, get_principal
from ..core.events import audit
from ..core.infra import store
from ..db.base import get_db
from ..db.models import Course, Enrollment, Recommendation, Student
from .tracking import student_progress

router = APIRouter(tags=["IA Tutor"])

SYSTEM = (
    "Eres EduMaster Tutor, un tutor académico en español, cálido y preciso. Explicas con ejemplos breves, propones el siguiente "
    "paso concreto y nunca inventas calificaciones. Las estimaciones de IA son orientativas, no diagnósticos. "
    "No pidas datos personales. Responde en máximo 180 palabras con viñetas cuando ayude."
)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    course_id: uuid.UUID | None = None
    history: list[dict] = Field(default_factory=list, max_length=10)


def _context(db: Session, p: Principal, course_id) -> dict:
    if not p.student_id:
        return {"rol": sorted(p.roles)}
    prog = student_progress(p.student_id, p, db)
    recs = db.scalars(select(Recommendation).where(Recommendation.student_id == p.student_id, Recommendation.status == "new")
                      .order_by(Recommendation.priority.desc()).limit(3)).all()
    courses = [{"curso": c["course_title"], "avance": f"{c['progress']:.0%}", "estado": c["status"],
                "ultimas_notas": [round(a["score"] or 0) for a in c["attempts"][-3:]]} for c in prog["courses"] if not course_id or c["course_id"] == course_id]
    return {"cursos": courses[:5], "competencias": prog["skills"][:6], "recomendaciones_vigentes": [r.title for r in recs]}


def _llm(question: str, ctx: dict, history: list[dict]) -> tuple[str, str]:
    msgs = [{"role": h["role"], "content": str(h["content"])[:2000]} for h in history if h.get("role") in ("user", "assistant")]
    user = f"Contexto autorizado del estudiante (JSON): {ctx}\n\nPregunta: {question}"
    if settings.ai_tutor_provider == "anthropic" and settings.anthropic_api_key:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=40,
                       headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": settings.anthropic_model, "max_tokens": 600, "system": SYSTEM, "messages": msgs + [{"role": "user", "content": user}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]), f"anthropic:{settings.anthropic_model}"
    if settings.ai_tutor_provider == "openai" and settings.openai_api_key:
        r = httpx.post(f"{settings.openai_base_url.rstrip('/')}/chat/completions", timeout=40,
                       headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                       json={"model": settings.openai_model, "max_tokens": 600,
                             "messages": [{"role": "system", "content": SYSTEM}] + msgs + [{"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"], f"openai:{settings.openai_model}"
    raise RuntimeError("sin proveedor")


def _rules(question: str, ctx: dict) -> str:
    lines = ["Aquí va una guía basada en tu progreso registrado:"]
    for c in ctx.get("cursos", [])[:3]:
        estado = {"in_progress": "en progreso", "completed": "completado", "not_started": "sin iniciar", "dropped": "retirado"}.get(c["estado"], c["estado"])
        lines.append(f"• **{c['curso']}** — avance {c['avance']} ({estado}).")
    if ctx.get("recomendaciones_vigentes"):
        lines.append(f"• Siguiente paso sugerido: **{ctx['recomendaciones_vigentes'][0]}**.")
    q = question.lower()
    if any(w in q for w in ("red neuronal", "neuron", "backprop", "gradiente")):
        lines.append("• Concepto clave: una red ajusta sus pesos con retropropagación — calcula el error en la salida y lo "
                     "propaga hacia atrás capa por capa usando la regla de la cadena. Mira el visualizador de redes para verlo.")
    elif any(w in q for w in ("examen", "evaluaci", "nota")):
        lines.append("• Para tu próxima evaluación: repasa las lecciones con menor avance y practica 20–30 min diarios.")
    else:
        lines.append("• Divide el objetivo en bloques de 25 minutos y registra una actividad práctica al terminar cada bloque.")
    lines.append("_Modo reglas activo. Configura un proveedor generativo (Anthropic u OpenAI) en el archivo .env para respuestas generativas._")
    return "\n".join(lines)


@router.post("/ai-tutor/ask")
def ask(body: AskIn, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if store.hit(f"rl:tutor:{p.id}", 60) > 12:
        raise HTTPException(429, "Límite de preguntas por minuto alcanzado")
    if body.course_id:
        c = db.get(Course, body.course_id)
        if not c or c.organization_id != p.org_id:
            raise HTTPException(404, "Curso no encontrado")
    ctx = _context(db, p, body.course_id)
    try:
        answer, provider = _llm(body.question, ctx, body.history)
    except Exception:
        answer, provider = _rules(body.question, ctx), "rules"
    audit(db, p, "ai_tutor.asked", "ai_tutor", details={"provider": provider, "chars": len(body.question)})
    db.commit()
    return {"answer": answer, "provider": provider, "model": provider.split(":")[0],
            "model_version": provider.split(":")[-1] if ":" in provider else provider,
            "confidence": None, "context_used": list(ctx.keys()),
            "disclaimer": "Respuesta de apoyo generada por IA; verifica con tu docente."}
