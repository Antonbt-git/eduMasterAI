"""Pipeline DataOps (documento maestro §8.4) — 10 pasos reproducibles.

1 Ingesta → 2 Validación de esquema → 3 Deduplicación → 4 Calidad/cuarentena →
5 Seudonimización → 6 Ventanas temporales y features (sin fuga) → 7 Etiquetado →
8 Split temporal (train/val/test) + chequeo por grupos → 9 Versionado + checksum →
10 Publicación (datasheet + reporte de calidad).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import MASTERY_LEVELS, N_RESOURCES, SEQ_WEEKS_OBSERVED, SKILLS, TOTAL_WEEKS, settings
from ..features.schema import SEQ_FEATURES, TAB_FEATURES, FEATURE_SCHEMA_VERSION
from .synthetic import SyntheticConfig, generate_raw_events, resources_catalog

PIPELINE_VERSION = "1.0.0"
REQUIRED_COLS = ["event_id", "event_type", "occurred_at", "student_id", "course_code", "enrollment_id", "duration_seconds"]
VALID_TYPES = {"session_started", "lesson_viewed", "activity_completed", "assessment_submitted", "course_completed"}
MAX_DURATION = 6 * 3600


@dataclass
class QualityReport:
    rows_ingested: int
    rows_after_dedup: int
    duplicates_removed: int
    quarantined_rows: int
    completeness_critical: float
    duplicates_after: int
    range_ok_ratio: float
    quarantine_rate: float
    temporal_violations: int
    class_balance: dict
    split_sizes: dict
    group_overlap_students_train_test: int
    passed: bool
    notes: list


def _pseudo(value: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]


def build_dataset(version: str = "demo-v1", seed: int | None = None, out_dir: Path | None = None, progress=None) -> dict:
    """Construye (o reconstruye) el dataset versionado. Determinista ⇒ mismo checksum."""
    seed = settings.seed if seed is None else seed
    out_dir = (out_dir or settings.data_dir / "datasets") / version
    out_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    step = (lambda i, msg: progress(i, msg)) if progress else (lambda i, msg: None)

    # 1. Ingesta -----------------------------------------------------------
    step(1, "Ingesta de eventos crudos (DEMO)")
    raw, enroll = generate_raw_events(SyntheticConfig(seed=seed))
    rows_ingested = len(raw)

    # 2. Validación de esquema -------------------------------------------
    step(2, "Validación de esquema y tipos")
    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f"Esquema inválido, faltan columnas: {missing}")
    raw["occurred_at"] = pd.to_datetime(raw["occurred_at"], utc=True)
    completeness = float(raw[REQUIRED_COLS].notna().all(axis=1).mean())

    # 3. Deduplicación ----------------------------------------------------
    step(3, "Deduplicación por event_id (idempotencia)")
    before = len(raw)
    events = raw.drop_duplicates(subset=["event_id"], keep="first").copy()
    duplicates_removed = before - len(events)

    # 4. Calidad / cuarentena --------------------------------------------
    step(4, "Controles de rango y cuarentena")
    pre_quarantine = len(events)
    bad = (~events["event_type"].isin(VALID_TYPES)) | (events["duration_seconds"] < 0) | (events["duration_seconds"] > MAX_DURATION)
    quarantine = events[bad]
    events = events[~bad]
    quarantine.to_csv(out_dir / "quarantine.csv", index=False)
    quarantine_rate = len(quarantine) / max(1, pre_quarantine)
    range_ok = 1.0 - quarantine_rate

    # 5. Seudonimización --------------------------------------------------
    step(5, "Seudonimización de identificadores")
    salt = f"edumaster-{version}"
    events["student_key"] = events["student_id"].map(lambda v: _pseudo(v, salt))
    enroll["student_key"] = enroll["student_id"].map(lambda v: _pseudo(v, salt))
    events = events.drop(columns=["student_id"])
    enroll = enroll.drop(columns=["student_id"])

    # 6/7. Ventanas temporales, features y etiquetas ------------------------
    step(6, "Ventanas temporales y features sin fuga")
    events = events.merge(enroll[["enrollment_id", "cohort_start"]], on="enrollment_id", how="inner")
    # Consistencia temporal: nada antes de la cohorte, nada fuera de la ventana ni en el futuro.
    events["week_raw"] = (events["occurred_at"] - pd.to_datetime(events["cohort_start"], utc=True)).dt.days // 7
    now_ts = pd.Timestamp.now(tz="UTC")
    bad_time = ((events["week_raw"] < 0) | (events["week_raw"] >= TOTAL_WEEKS)
                | (events["occurred_at"] > now_ts + pd.Timedelta(minutes=5)))
    temporal_violations = int(bad_time.sum())
    if temporal_violations:
        events[bad_time].to_csv(out_dir / "quarantine_temporal.csv", index=False)
    events = events[~bad_time].copy()
    events["week"] = events["week_raw"].clip(0, TOTAL_WEEKS - 1)
    scores = events["payload"].map(lambda p: p.get("score") if isinstance(p, dict) else np.nan)
    lates = events["payload"].map(lambda p: bool(p.get("late")) if isinstance(p, dict) else False)
    events = events.assign(score=scores, late=lates, day=events["occurred_at"].dt.floor("D"))

    E = len(enroll)
    eidx = {e: i for i, e in enumerate(enroll["enrollment_id"])}
    seq = np.zeros((E, TOTAL_WEEKS, len(SEQ_FEATURES)), dtype=np.float32)
    ev = events.assign(i=events["enrollment_id"].map(eidx))
    g = ev.groupby(["i", "week"])
    agg = pd.DataFrame(
        {
            "active_days": g["day"].nunique(),
            "sessions": g["event_type"].apply(lambda s: (s == "session_started").sum()),
            "activities": g["event_type"].apply(lambda s: (s == "activity_completed").sum()),
            "score": g["score"].mean(),
            "late": g["late"].sum(),
            "engagement": g["duration_seconds"].sum() / 3600.0,
        }
    ).fillna({"score": 0.0}).reset_index()
    for col_i, col in enumerate(["active_days", "sessions", "activities", "score", "late", "engagement"]):
        val = agg[col].to_numpy(dtype=np.float32)
        if col == "score":
            val = val / 100.0
        seq[agg["i"].to_numpy(), agg["week"].to_numpy(), col_i] = val

    obs = seq[:, :SEQ_WEEKS_OBSERVED, :]  # SOLO semanas ≤ corte => sin fuga
    fut = seq[:, SEQ_WEEKS_OBSERVED:, :]
    required = 18 + 4 * enroll["course_level"].to_numpy()

    def last_active(x):
        active = np.where(x[:, 1] > 0)[0]
        return (SEQ_WEEKS_OBSERVED - 1 - active.max()) * 7 if len(active) else SEQ_WEEKS_OBSERVED * 7

    sc = obs[:, :, 3]
    has = sc > 0
    w_idx = np.arange(SEQ_WEEKS_OBSERVED)
    trend = np.array(
        [np.polyfit(w_idx[h], s[h], 1)[0] if h.sum() >= 2 else 0.0 for s, h in zip(sc, has)], dtype=np.float32
    )
    tab = pd.DataFrame(
        {
            "active_days_14d": obs[:, -2:, 0].sum(1),
            "sessions_14d": obs[:, -2:, 1].sum(1),
            "completion_ratio": np.clip(obs[:, :, 2].sum(1) / required, 0, 1),
            "assessment_mean": np.where(has.sum(1) > 0, (sc * has).sum(1) / np.maximum(1, has.sum(1)), 0.0),
            "assessment_trend": trend,
            "late_submissions_30d": obs[:, -4:, 4].sum(1),
            "content_engagement": obs[:, :, 5].sum(1),
            "skill_evidence_score": np.clip((sc * has).sum(1) / np.maximum(1, has.sum(1)) * (0.6 + 0.4 * np.clip(obs[:, :, 2].sum(1) / required, 0, 1)), 0, 1),
            "days_since_last_activity": [last_active(x) for x in obs],
        }
    ).astype(np.float32)
    assert list(tab.columns) == TAB_FEATURES

    step(7, "Etiquetado con reglas documentadas")
    completed_ids = set(events.loc[events["event_type"] == "course_completed", "enrollment_id"])
    y_completion = enroll["enrollment_id"].isin(completed_ids).to_numpy().astype(np.float32)
    fut_active = fut[:, -3:, 1].sum(1)
    # Riesgo: sin actividad en las últimas 3 semanas de la ventana futura Y no completó (no ausencia aislada)
    y_risk = ((fut_active == 0) & (y_completion == 0) & (fut[:, :, 1].sum(1) <= 1)).astype(np.float32)
    fsc = fut[:, :, 3]
    fhas = fsc > 0
    fut_score = np.where(fhas.sum(1) > 0, (fsc * fhas).sum(1) / np.maximum(1, fhas.sum(1)), np.nan)
    evidence = np.where(np.isnan(fut_score), tab["assessment_mean"].to_numpy(), fut_score)
    y_mastery = np.digitize(evidence, [0.35, 0.5, 0.65, 0.8]).astype(np.int64)  # rúbrica 0..4
    y_mastery_mask = (~np.isnan(fut_score)).astype(np.float32)  # sin evidencia ⇒ pérdida enmascarada

    # Relevancia de recursos (para ranking): competencia del curso + dificultad cercana al nivel
    res = resources_catalog()
    rel = np.zeros((E, N_RESOURCES), dtype=np.float32)
    for r in res.itertuples():
        same_skill = (enroll["skill_idx"].to_numpy() == r.skill_idx).astype(np.float32)
        closeness = 1.0 - np.abs(r.difficulty - (y_mastery + 0.5)) / 5.0
        rel[:, r.resource_idx] = np.clip(same_skill * (1.5 + 1.5 * closeness) + 0.3 * closeness - 0.2, 0, 3)

    # 8. Split temporal ------------------------------------------------------
    step(8, "Split temporal train/val/test y chequeo por grupos")
    cohort = enroll["cohort"].to_numpy()
    n_c = cohort.max() + 1
    split = np.where(cohort < n_c - 2, "train", np.where(cohort == n_c - 2, "validation", "test"))
    train_students = set(enroll.loc[split == "train", "student_key"])
    test_students = set(enroll.loc[split == "test", "student_key"])
    overlap = len(train_students & test_students)
    notes.append(
        f"{overlap} estudiantes aparecen en train y test (periodos distintos). El split es temporal; "
        "se reporta además métrica en estudiantes no vistos (group holdout)."
    )
    unseen = ~enroll["student_key"].isin(train_students).to_numpy()

    # 9. Versionado ------------------------------------------------------------
    step(9, "Versionado y checksum")
    arrays = dict(
        x_tab=tab.to_numpy(np.float32),
        x_cat=enroll["course_level"].to_numpy(np.int64),
        x_skill=enroll["skill_idx"].to_numpy(np.int64),
        x_seq=obs.astype(np.float32),
        y_completion=y_completion,
        y_risk=y_risk,
        y_mastery=y_mastery,
        y_mastery_mask=y_mastery_mask,
        y_rank=rel,
        split=split.astype("U10"),
        unseen=unseen,
    )
    np.savez_compressed(out_dir / "features.npz", **arrays)
    meta_cols = ["enrollment_id", "student_key", "course_code", "course_level", "skill_idx", "cohort", "region", "label"]
    enroll[meta_cols].to_csv(out_dir / "enrollments.csv", index=False)
    h = hashlib.sha256()
    for k in sorted(arrays):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrays[k]).tobytes())
    checksum = h.hexdigest()

    balance = {
        s: {
            "n": int((split == s).sum()),
            "completion_rate": float(y_completion[split == s].mean()),
            "risk_rate": float(y_risk[split == s].mean()),
            "mastery_dist": np.bincount(y_mastery[split == s], minlength=5).tolist(),
        }
        for s in ["train", "validation", "test"]
    }
    split_ok = all(v["n"] > 0 for v in balance.values())
    balance_ok = all(0.0 < v["completion_rate"] < 1.0 and 0.0 <= v["risk_rate"] < 1.0 for v in balance.values())
    temporal_rate = temporal_violations / max(1, pre_quarantine)
    passed = (completeness >= 0.98 and int(events["event_id"].duplicated().sum()) == 0
              and quarantine_rate <= 0.05 and temporal_rate <= 0.05 and split_ok and balance_ok)
    if temporal_violations:
        notes.append(f"{temporal_violations} eventos fuera de la ventana temporal se enviaron a cuarentena "
                     "(quarantine_temporal.csv); no participan en features ni etiquetas.")
    if not passed:
        notes.append("Puertas de calidad NO superadas: no publicar ni entrenar con este dataset.")
    report = QualityReport(
        rows_ingested=rows_ingested,
        rows_after_dedup=rows_ingested - duplicates_removed,
        duplicates_removed=duplicates_removed,
        quarantined_rows=len(quarantine),
        completeness_critical=round(completeness, 4),
        duplicates_after=int(events["event_id"].duplicated().sum()),
        range_ok_ratio=round(range_ok, 4),
        quarantine_rate=round(quarantine_rate, 4),
        temporal_violations=temporal_violations,
        class_balance=balance,
        split_sizes={k: v["n"] for k, v in balance.items()},
        group_overlap_students_train_test=overlap,
        passed=passed,
        notes=notes,
    )

    # 10. Publicación ----------------------------------------------------------
    step(10, "Publicación: datasheet + reporte de calidad")
    manifest = {
        "name": "edumaster-learning-demo",
        "version": version,
        "label": "DEMO",
        "seed": seed,
        "pipeline_version": PIPELINE_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "schema": {"tab": TAB_FEATURES, "seq": SEQ_FEATURES, "seq_weeks": SEQ_WEEKS_OBSERVED},
        "targets": ["target_completion_30d", "target_mastery_level", "target_dropout_risk", "resource_relevance"],
        "checksum": checksum,
        "storage_uri": str(out_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "quality": asdict(report),
        "skills": SKILLS,
        "mastery_levels": MASTERY_LEVELS,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    (out_dir / "DATASHEET.md").write_text(_datasheet(manifest), encoding="utf-8")
    return manifest


def load_dataset(version: str = "demo-v1") -> tuple[dict, dict]:
    d = settings.data_dir / "datasets" / version
    if not (d / "manifest.json").exists():
        build_dataset(version)
    arrays = dict(np.load(d / "features.npz"))
    manifest = json.loads((d / "manifest.json").read_text())
    return arrays, manifest


def _datasheet(m: dict) -> str:
    q = m["quality"]
    return f"""# Datasheet — {m['name']} ({m['version']})

> **ETIQUETA: DEMO** — dataset sintético para probar interfaz, pipeline y entrenamiento técnico.
> No permite afirmar validez educativa (documento maestro §8.1).

| Campo | Valor |
|---|---|
| Versión de pipeline | {m['pipeline_version']} |
| Esquema de features | {m['feature_schema_version']} |
| Semilla | {m['seed']} |
| Checksum (sha256) | `{m['checksum']}` |
| Filas ingestadas | {q['rows_ingested']} |
| Duplicados eliminados | {q['duplicates_removed']} |
| Filas en cuarentena | {q['quarantined_rows']} |
| Completitud campos críticos | {q['completeness_critical']:.2%} |
| Duplicados tras deduplicación | {q['duplicates_after']} |
| Split (train/val/test) | {q['split_sizes']} |

## Motivación
Probar de extremo a extremo la plataforma EduMaster.ai antes de disponer de datos institucionales autorizados.

## Composición
Eventos `session_started`, `lesson_viewed`, `activity_completed`, `assessment_submitted`, `course_completed`
por matrícula, 6 cohortes mensuales, 12 cursos y 5 competencias. Identificadores seudonimizados (sha256 con sal por versión).

## Proceso de etiquetado
- `target_completion_30d`: evento `course_completed` en la ventana futura.
- `target_mastery_level`: rúbrica sobre evaluaciones futuras (0–4). Sin evidencia ⇒ pérdida enmascarada.
- `target_dropout_risk`: sin actividad en las 3 últimas semanas de la ventana futura **y** sin completar (no ausencia aislada).

## Prevención de fuga
Features calculadas solo con semanas 0–{m['schema']['seq_weeks'] - 1}. Split temporal por cohorte; métricas adicionales en estudiantes no vistos.

## Limitaciones
Datos sintéticos; distribuciones simplificadas; no representativos de ninguna institución real.
"""


if __name__ == "__main__":  # python -m edumaster_ml.datasets.pipeline
    import sys

    m = build_dataset(sys.argv[1] if len(sys.argv) > 1 else "demo-v1", progress=lambda i, s: print(f"[{i}/10] {s}"))
    print(json.dumps({k: m[k] for k in ["version", "checksum"]}, indent=2), m["quality"]["split_sizes"])
