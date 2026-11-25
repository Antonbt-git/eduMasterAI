"""Esquema de features versionado y normalizador serializable."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FEATURE_SCHEMA_VERSION = "1.0"

TAB_FEATURES = [
    "active_days_14d",
    "sessions_14d",
    "completion_ratio",
    "assessment_mean",
    "assessment_trend",
    "late_submissions_30d",
    "content_engagement",
    "skill_evidence_score",
    "days_since_last_activity",
]
TAB_LABELS_ES = {
    "active_days_14d": "Días activos (14d)",
    "sessions_14d": "Sesiones (14d)",
    "completion_ratio": "Ratio de avance",
    "assessment_mean": "Promedio evaluaciones",
    "assessment_trend": "Tendencia evaluaciones",
    "late_submissions_30d": "Entregas tardías (30d)",
    "content_engagement": "Interacción con contenido",
    "skill_evidence_score": "Evidencia de competencia",
    "days_since_last_activity": "Días sin actividad",
}
SEQ_FEATURES = ["active_days", "sessions", "activities", "score", "late", "engagement_h"]
N_COURSE_LEVELS = 3
N_SKILLS = 5
# Etiquetas objetivo del pipeline (documento maestro §8.3) y niveles curriculares.
TARGETS = ["target_completion_30d", "target_mastery_level", "target_dropout_risk", "resource_relevance"]
COURSE_LEVELS = ["basico", "intermedio", "avanzado"]  # índice 0..2 usado por x_cat


@dataclass
class Standardizer:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, x: np.ndarray) -> "Standardizer":
        axes = tuple(range(x.ndim - 1))
        return cls(x.mean(axis=axes), x.std(axis=axes) + 1e-6)

    def transform(self, x: np.ndarray) -> np.ndarray:
        return ((x - self.mean) / self.std).astype(np.float32)

    def to_dict(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> "Standardizer":
        return cls(np.array(d["mean"], dtype=np.float32), np.array(d["std"], dtype=np.float32))
