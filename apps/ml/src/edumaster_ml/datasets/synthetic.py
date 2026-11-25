"""Generador de eventos de aprendizaje SINTÉTICOS (DEMO).

Principio del documento maestro §8.1: el dataset histórico NO se inventa como real.
Este generador produce eventos *crudos* claramente rotulados DEMO para probar la
interfaz, el pipeline DataOps y el entrenamiento técnico. No permite afirmar
validez educativa. Todo es determinista dado `seed` => reproducible.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ..config import N_RESOURCES, SKILLS, TOTAL_WEEKS

DEMO_LABEL = "DEMO"

COURSES = [
    # code, title, level(0 básico,1 intermedio,2 avanzado), skill index, difficulty
    ("IA-101", "Fundamentos de Inteligencia Artificial", 0, 0, -0.3),
    ("IA-301", "Inteligencia Artificial Avanzada", 2, 0, 0.8),
    ("ML-101", "Machine Learning Básico", 0, 1, -0.1),
    ("ML-201", "Redes Neuronales con PyTorch", 1, 1, 0.5),
    ("DS-101", "Ciencia de Datos con Python", 0, 2, -0.4),
    ("DS-201", "Estadística para Analítica", 1, 2, 0.2),
    ("WEB-101", "Desarrollo Web con React", 0, 3, -0.2),
    ("WEB-201", "APIs con FastAPI", 1, 3, 0.3),
    ("OPS-101", "Docker y Contenedores", 0, 4, 0.0),
    ("OPS-201", "Kubernetes y MLOps", 2, 4, 0.9),
    ("PY-101", "Python desde Cero", 0, 2, -0.6),
    ("PY-301", "Proyecto Final de Python", 1, 1, 0.4),
]

REGIONS = ["América del Norte", "América del Sur", "Europa", "Asia", "África", "Oceanía"]
REGION_P = [0.25, 0.30, 0.20, 0.15, 0.05, 0.05]


@dataclass
class SyntheticConfig:
    seed: int = 42
    n_students: int = 1200
    n_cohorts: int = 6
    enrollments_per_cohort: int = 480
    start: datetime = datetime(2026, 1, 5, tzinfo=timezone.utc)
    duplicate_rate: float = 0.005
    invalid_rate: float = 0.002


def _uuid(rng: np.random.Generator) -> str:
    return str(uuid.UUID(bytes=rng.bytes(16), version=4))


def resources_catalog() -> pd.DataFrame:
    """24 recursos (4–5 por competencia) con dificultad ordinal."""
    kinds = ["Repasa", "Completa", "Sigue", "Realiza", "Explora"]
    rows = []
    for r in range(N_RESOURCES):
        skill = r % len(SKILLS)
        diff = (r // len(SKILLS)) % 5
        rows.append(
            {
                "resource_idx": r,
                "code": f"RES-{r:03d}",
                "skill_idx": skill,
                "difficulty": diff,
                "title": f"{kinds[diff]}: {SKILLS[skill]} · nivel {diff + 1}",
            }
        )
    return pd.DataFrame(rows)


def generate_raw_events(cfg: SyntheticConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (events, enrollments) crudos. Incluye ruido controlado (duplicados y
    rangos inválidos) para que el pipeline de calidad tenga algo que corregir."""
    cfg = cfg or SyntheticConfig()
    rng = np.random.default_rng(cfg.seed)

    students = pd.DataFrame(
        {
            "student_id": [_uuid(rng) for _ in range(cfg.n_students)],
            "ability": rng.normal(0, 1, cfg.n_students),
            "motivation": rng.normal(0, 1, cfg.n_students),
            "region": rng.choice(REGIONS, size=cfg.n_students, p=REGION_P),
        }
    )

    enroll_rows = []
    events: list[tuple] = []
    for cohort in range(cfg.n_cohorts):
        cohort_start = cfg.start + timedelta(days=30 * cohort)
        idx = rng.choice(cfg.n_students, size=cfg.enrollments_per_cohort, replace=False)
        for s_i in idx:
            st = students.iloc[s_i]
            c_i = int(rng.integers(0, len(COURSES)))
            code, _title, level, skill, diff = COURSES[c_i]
            enrollment_id = _uuid(rng)
            enroll_rows.append(
                {
                    "enrollment_id": enrollment_id,
                    "student_id": st.student_id,
                    "course_code": code,
                    "course_level": level,
                    "skill_idx": skill,
                    "cohort": cohort,
                    "cohort_start": cohort_start,
                    "region": st.region,
                    "label": DEMO_LABEL,
                }
            )
            # Patrón latente de desconexión (no lineal: interacción motivación x dificultad)
            p_disengage = 1 / (1 + np.exp(-(-0.4 - 1.1 * st.motivation + 0.7 * diff - 0.4 * st.ability * st.motivation)))
            disengage_week = int(rng.integers(3, TOTAL_WEEKS)) if rng.random() < p_disengage else TOTAL_WEEKS + 5
            base_rate = np.exp(0.9 + 0.35 * st.motivation)
            completed = 0
            for w in range(TOTAL_WEEKS):
                decay = 1.0 if w < disengage_week else max(0.0, 0.25 - 0.1 * (w - disengage_week))
                lam = base_rate * decay * (1.0 + 0.05 * np.sin(w))
                n_sessions = int(rng.poisson(lam))
                week_start = cohort_start + timedelta(days=7 * w)
                for _ in range(n_sessions):
                    t = week_start + timedelta(seconds=int(rng.integers(0, 7 * 86400)))
                    dur = int(np.clip(rng.lognormal(7.0, 0.6), 60, 4 * 3600))
                    events.append((_uuid(rng), "session_started", t, st.student_id, code, enrollment_id, dur, None))
                    n_lessons = int(rng.poisson(1.5))
                    for _ in range(n_lessons):
                        events.append((_uuid(rng), "lesson_viewed", t + timedelta(minutes=5), st.student_id, code, enrollment_id, int(rng.integers(120, 1800)), None))
                    if rng.random() < 0.55 + 0.1 * st.motivation:
                        completed += 1
                        events.append((_uuid(rng), "activity_completed", t + timedelta(minutes=30), st.student_id, code, enrollment_id, int(rng.integers(300, 3600)), None))
                # Evaluaciones en semanas pares si hubo actividad mínima
                if w % 2 == 1 and (n_sessions > 0 or rng.random() < 0.15):
                    learn = 0.25 * min(completed, 20) / 20
                    score = 100 / (1 + np.exp(-(1.2 * st.ability - diff + learn + 0.3 * st.motivation + rng.normal(0, 0.5))))
                    late = rng.random() < (0.35 - 0.12 * st.motivation)
                    t = week_start + timedelta(days=6, hours=int(rng.integers(0, 23)))
                    events.append((_uuid(rng), "assessment_submitted", t, st.student_id, code, enrollment_id, int(rng.integers(600, 3600)), {"score": round(float(score), 2), "late": bool(late)}))
            required = 18 + 4 * level
            if completed >= required and disengage_week > TOTAL_WEEKS - 1:
                t = cohort_start + timedelta(days=7 * TOTAL_WEEKS - 1)
                events.append((_uuid(rng), "course_completed", t, st.student_id, code, enrollment_id, 0, None))

    df = pd.DataFrame(
        events,
        columns=["event_id", "event_type", "occurred_at", "student_id", "course_code", "enrollment_id", "duration_seconds", "payload"],
    )
    df["source"] = "demo-generator"
    df["payload_schema_version"] = 1
    df["label"] = DEMO_LABEL

    # Ruido controlado ---------------------------------------------------
    n_dup = int(len(df) * cfg.duplicate_rate)
    dups = df.sample(n=n_dup, random_state=cfg.seed)
    n_bad = int(len(df) * cfg.invalid_rate)
    bad_idx = df.sample(n=n_bad, random_state=cfg.seed + 1).index
    df.loc[bad_idx, "duration_seconds"] = rng.choice([-30, 99_999], size=n_bad)
    df = pd.concat([df, dups], ignore_index=True)
    df = df.sample(frac=1.0, random_state=cfg.seed).reset_index(drop=True)
    return df, pd.DataFrame(enroll_rows)
