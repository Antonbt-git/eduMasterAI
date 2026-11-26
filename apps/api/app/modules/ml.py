"""AI Platform: datasets, entrenamientos asíncronos, registro/aprobación/promoción/rollback, inferencia y topología."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import Principal, get_principal, internal_only, require
from ..core.events import activity, audit, emit
from ..core.infra import get_queue, store
from ..db.base import get_db
from ..db.models import Dataset, ModelRun, ModelVersion, Organization, Prediction, Skill, SkillEvidence, Student
from .common import get_or_404
from .ml_features import FEATURE_SCHEMA_VERSION, build_features

router = APIRouter(tags=["AI Platform"])
internal = APIRouter(prefix="/internal/ml", tags=["Internal"], dependencies=[Depends(internal_only)], include_in_schema=False)

NETWORK_KEYS = ["edumaster_mtl", "completion_mlp", "mastery_ordinal", "risk_transformer", "reco_ranker"]
ML_AUDIENCE = ["superadmin", "admin", "ml_engineer", "analyst", "coordinator", "instructor", "auditor", "*"]
PRIMARY_NAMES = {"edumaster_mtl": "composite", "completion_mlp": "roc_auc", "mastery_ordinal": "macro_f1",
                 "risk_transformer": "pr_auc", "reco_ranker": "ndcg@5"}


def ml_client() -> httpx.Client:
    return httpx.Client(base_url=settings.ml_service_url, headers={"X-Internal-Token": settings.internal_service_token}, timeout=30)


def ml_get(path: str, **params):
    try:
        with ml_client() as c:
            r = c.get(path, params=params)
    except httpx.HTTPError:
        raise HTTPException(503, "Servicio de inferencia no disponible")
    try:
        payload = r.json() if r.content else {}
    except ValueError:
        payload = {}
    if r.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if r.status_code == 429:
            detail = detail or "El servicio de inferencia está saturado; reintenta en unos segundos."
        raise HTTPException(r.status_code, detail or "Error del servicio ML")
    return payload if payload else (r.json() if r.content else {})


def ml_post(path: str, json: dict):
    try:
        with ml_client() as c:
            r = c.post(path, json=json)
    except httpx.HTTPError:
        raise HTTPException(503, "Servicio de inferencia no disponible")
    try:
        payload = r.json() if r.content else {}
    except ValueError:
        payload = {}
    if r.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if r.status_code == 429:
            detail = detail or "El servicio de inferencia está saturado; reintenta en unos segundos."
        raise HTTPException(r.status_code, detail or "Error del servicio ML")
    return payload if payload else (r.json() if r.content else {})


def _all_orgs(db: Session) -> list:
    return list(db.scalars(select(Organization.id)))


def _scoped(stmt, p: Principal, model):
    """Superadmin ve todo; el resto ve su institución y los artefactos de plataforma (organization_id NULL)."""
    if "superadmin" in p.roles:
        return stmt
    return stmt.where(or_(model.organization_id == p.org_id, model.organization_id.is_(None)))


def emit_all(db: Session, event_type: str, payload: dict, aggregate_id=None):
    """Eventos de plataforma ML: se publican a cada institución (metadatos, sin datos personales)."""
    for org in _all_orgs(db):
        emit(db, event_type, payload, org_id=org, aggregate_id=aggregate_id, roles=ML_AUDIENCE)


def run_dto(r: ModelRun) -> dict:
    return {"id": r.id, "network_key": r.network_key, "status": r.status, "dataset_version": r.dataset_version, "params": r.params,
            "progress": r.progress, "history": r.history, "metrics": r.metrics, "error": r.error, "created_at": r.created_at,
            "started_at": r.started_at, "finished_at": r.finished_at}


def version_dto(v: ModelVersion) -> dict:
    return {"id": v.id, "organization_id": v.organization_id, "network_key": v.network_key, "name": v.name, "version": v.version, "stage": v.stage,
            "approval_status": v.approval_status, "approval_note": v.approval_note, "approved_at": v.approved_at, "promoted_at": v.promoted_at,
            "beats_baseline": v.beats_baseline, "primary_metric": v.primary_metric, "baseline_metric": v.baseline_metric,
            "primary_metric_name": PRIMARY_NAMES.get(v.network_key), "dataset_version": v.dataset_version, "checksum": v.checksum,
            "run_id": v.run_id, "created_at": v.created_at, "metrics": v.metrics, "label": "DEMO"}


def production(db: Session, key: str) -> ModelVersion | None:
    return db.scalar(select(ModelVersion).where(ModelVersion.network_key == key, ModelVersion.stage == "production"))


def enqueue_training(db: Session, key: str, params: dict, requested_by=None, org_id=None) -> ModelRun:
    run = ModelRun(organization_id=org_id, network_key=key, experiment=f"edumaster/{key}",
                   dataset_version=params.get("dataset_version", settings.default_dataset_version),
                   params=params, status="queued", requested_by=requested_by, progress={"phase": "queued"})
    db.add(run)
    db.flush()
    emit_all(db, "model.training.started", {"run_id": str(run.id), "network_key": key, "status": "queued"}, run.id)
    db.commit()
    q = get_queue()
    if q is None:
        run.status, run.error = "failed", "Sin Redis/worker configurado: no se puede entrenar fuera del hilo HTTP"
        db.commit()
        raise HTTPException(503, run.error)
    q.enqueue("edumaster_ml.jobs.train_job", str(run.id), key, params, job_id=f"train-{run.id}", job_timeout=3600)
    return run


# ----------------------------------------------------------------- Redes y topología
@router.get("/ml/networks")
def networks(p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    try:
        meta = {n["key"]: n for n in ml_get("/networks")}
    except HTTPException:
        meta = {}
    out = []
    for k in NETWORK_KEYS:
        last = db.scalar(_scoped(select(ModelRun).where(ModelRun.network_key == k), p, ModelRun)
                         .order_by(ModelRun.created_at.desc()).limit(1))
        prod = production(db, k)
        versions = db.scalars(_scoped(select(ModelVersion).where(ModelVersion.network_key == k), p, ModelVersion)
                              .order_by(ModelVersion.created_at.desc())).all()
        out.append({
            "key": k, "title": meta.get(k, {}).get("title", k), "description": meta.get(k, {}).get("description", ""),
            "task": meta.get(k, {}).get("task"), "primary_metric": PRIMARY_NAMES[k],
            "production": version_dto(prod) if prod else None, "versions": [version_dto(v) for v in versions],
            "last_run": run_dto(last) if last else None,
            "state": _state(last, prod),
        })
    return out


def _state(last: ModelRun | None, prod: ModelVersion | None) -> str:
    if last and last.status in ("queued", "loading_data", "training", "validating"):
        return {"queued": "cargando datos", "loading_data": "cargando datos", "training": "entrenando", "validating": "validando"}[last.status]
    if last and last.status == "failed":
        return "error"
    return "publicado" if prod else "detenido"


@router.get("/ml/networks/topologies")
def topologies(p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    """Topologías ligeras (sin pesos) de todas las redes en una sola petición.

    Evita la ráfaga de N llamadas que dispara el visualizador y que los proxies
    con rate limit (p. ej. Render) rechazan con 429.
    """
    out: dict[str, dict | None] = {}
    for k in NETWORK_KEYS:
        try:
            prod = production(db, k)
            v = prod.version if prod else None
            out[k] = ml_get(f"/networks/{k}/graph", **({"version": v} if v else {}), weights=False)
        except HTTPException:
            out[k] = None
    return out


@router.get("/ml/networks/{key}/graph")
def graph(key: str, version: str | None = None, weights: bool = True, p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    if key not in NETWORK_KEYS:
        raise HTTPException(404, "Red desconocida")
    prod = production(db, key)
    v = version or (prod.version if prod else None)
    if v is None:
        latest = db.scalar(_scoped(select(ModelVersion).where(ModelVersion.network_key == key), p, ModelVersion)
                           .order_by(ModelVersion.created_at.desc()).limit(1))
        v = latest.version if latest else None
    g = ml_get(f"/networks/{key}/graph", **({"version": v} if v else {}), weights=weights)
    last = db.scalar(_scoped(select(ModelRun).where(ModelRun.network_key == key), p, ModelRun)
                     .order_by(ModelRun.created_at.desc()).limit(1))
    g["state"] = _state(last, prod)
    g["production_version"] = prod.version if prod else None
    g["last_run"] = run_dto(last) if last else None
    g["label"] = "DEMO"
    return g


@router.get("/ml/networks/{key}/drift")
def network_drift(key: str, version: str | None = None, p: Principal = Depends(require("ml:read")),
                  db: Session = Depends(get_db)):
    """Drift de features (PSI) de la versión indicada o de la versión en producción."""
    if key not in NETWORK_KEYS:
        raise HTTPException(404, "Red desconocida")
    prod = production(db, key)
    v = version or (prod.version if prod else None)
    if not v:
        raise HTTPException(409, "No hay versión publicada para calcular drift")
    return {**ml_get(f"/networks/{key}/versions/{v}/drift"), "network_key": key, "version": v}


@router.get("/ml/examples")
def examples(n: int = Query(8, le=20), p: Principal = Depends(require("ml:read"))):
    return ml_get("/examples", n=n)


# ----------------------------------------------------------------- Datasets
class DatasetIn(BaseModel):
    version: str = Field(pattern=r"^[a-z0-9\-\.]{3,40}$")
    seed: int = 42


@router.get("/ml/datasets")
def list_datasets(p: Principal = Depends(require("datasets:read")), db: Session = Depends(get_db)):
    return [{"id": d.id, "name": d.name, "version": d.version, "label": d.label, "checksum": d.checksum, "status": d.status,
             "quality": d.quality, "progress": d.progress, "storage_uri": d.storage_uri, "created_at": d.created_at, "schema_version": d.schema_version}
            for d in db.scalars(select(Dataset).order_by(Dataset.created_at.desc()))]


@router.post("/ml/datasets", status_code=202)
def build_dataset(body: DatasetIn, p: Principal = Depends(require("datasets:build")), db: Session = Depends(get_db)):
    if db.scalar(select(Dataset.id).where(Dataset.name == "edumaster-learning-demo", Dataset.version == body.version)):
        raise HTTPException(409, "Esa versión de dataset ya existe (versionado inmutable)")
    d = Dataset(name="edumaster-learning-demo", version=body.version, label="DEMO", status="building", created_by=p.id, progress={"step": 0})
    db.add(d)
    db.flush()
    audit(db, p, "dataset.build_requested", "dataset", d.id, body.model_dump())
    db.commit()
    q = get_queue()
    if q is None:
        raise HTTPException(503, "Worker no disponible")
    q.enqueue("edumaster_ml.jobs.build_dataset_job", str(d.id), body.version, body.seed, job_timeout=1800)
    return {"id": d.id, "status": d.status}


@router.post("/ml/datasets/{dataset_id}/approve")
def approve_dataset(dataset_id: uuid.UUID, p: Principal = Depends(require("datasets:approve")), db: Session = Depends(get_db)):
    d = get_or_404(db, Dataset, dataset_id)
    if d.status != "ready" or not (d.quality or {}).get("passed"):
        raise HTTPException(409, "El dataset no superó las puertas de calidad")
    d.status, d.approved_by = "approved", p.id
    audit(db, p, "dataset.approved", "dataset", d.id, {"version": d.version, "checksum": d.checksum})
    db.commit()
    return {"id": d.id, "status": d.status}


# ----------------------------------------------------------------- Entrenamiento
class TrainIn(BaseModel):
    network_key: str
    epochs: int = Field(40, ge=1, le=300)
    lr: float = Field(3e-3, gt=0, le=1)
    batch_size: int = Field(128, ge=8, le=2048)
    patience: int = Field(7, ge=1, le=100)
    seed: int = 42
    dataset_version: str = "demo-v1"


@router.post("/ml/training-runs", status_code=202)
def create_run(body: TrainIn, p: Principal = Depends(require("ml:train")), db: Session = Depends(get_db)):
    if body.network_key not in NETWORK_KEYS:
        raise HTTPException(422, "Red desconocida")
    ds = db.scalar(select(Dataset).where(Dataset.version == body.dataset_version).order_by(Dataset.created_at.desc()).limit(1))
    if not ds:
        raise HTTPException(409, "Dataset no encontrado: construya y apruebe un dataset antes de entrenar")
    if ds.status != "approved" or not (ds.quality or {}).get("passed"):
        raise HTTPException(409, "El dataset debe superar las puertas de calidad y estar aprobado antes de entrenar")
    busy = db.scalar(select(ModelRun.id).where(ModelRun.network_key == body.network_key, ModelRun.status.in_(["queued", "loading_data", "training", "validating"])))
    if busy:
        raise HTTPException(409, "Ya hay un entrenamiento en curso para esta red")
    params = body.model_dump(exclude={"network_key"})
    run = enqueue_training(db, body.network_key, params, p.id, p.org_id)
    audit(db, p, "model.training_requested", "model_run", run.id, {"network": body.network_key, **params})
    db.commit()
    return run_dto(run)


@router.get("/ml/training-runs")
def list_runs(network_key: str | None = None, limit: int = Query(30, le=100), p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    q = _scoped(select(ModelRun), p, ModelRun).order_by(ModelRun.created_at.desc()).limit(limit)
    if network_key:
        q = q.where(ModelRun.network_key == network_key)
    return [run_dto(r) for r in db.scalars(q)]


@router.get("/ml/training-runs/{run_id}")
def get_run(run_id: uuid.UUID, p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    r = db.scalar(_scoped(select(ModelRun).where(ModelRun.id == run_id), p, ModelRun))
    if not r:
        raise HTTPException(404, "Ejecución no encontrada")
    return run_dto(r)


# ----------------------------------------------------------------- Registro de modelos
@router.get("/ml/models")
def list_models(network_key: str | None = None, p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    q = _scoped(select(ModelVersion), p, ModelVersion).order_by(ModelVersion.created_at.desc())
    if network_key:
        q = q.where(ModelVersion.network_key == network_key)
    return [version_dto(v) for v in db.scalars(q)]


@router.get("/ml/models/{model_id}")
def get_model(model_id: uuid.UUID, p: Principal = Depends(require("ml:read")), db: Session = Depends(get_db)):
    v = db.scalar(_scoped(select(ModelVersion).where(ModelVersion.id == model_id), p, ModelVersion))
    if not v:
        raise HTTPException(404, "Modelo no encontrado")
    card = None
    try:
        card = ml_get(f"/networks/{v.network_key}/versions/{v.version}/model-card")["markdown"]
    except HTTPException:
        pass
    return {**version_dto(v), "model_card": card}


class ApprovalIn(BaseModel):
    note: str = Field(min_length=5, max_length=1000)
    force: bool = False


def _approve(db: Session, v: ModelVersion, actor: Principal | None, note: str, force: bool):
    if not v.beats_baseline and not force:
        raise HTTPException(409, "El modelo no supera el baseline. Para aprobar, use force=true con justificación (queda auditado).")
    v.approval_status, v.approval_note, v.approved_at = "approved", note, datetime.now(timezone.utc)
    v.approved_by = actor.id if actor else None
    v.stage = "staging"


def _promote(db: Session, v: ModelVersion, actor_id=None):
    if v.approval_status != "approved":
        raise HTTPException(409, "Solo modelos aprobados pueden promoverse a producción")
    cur = production(db, v.network_key)
    if cur and cur.id != v.id:
        cur.stage = "archived"
    v.stage, v.promoted_at = "production", datetime.now(timezone.utc)
    emit_all(db, "model.deployed", {"network_key": v.network_key, "version": v.version, "previous": cur.version if cur else None,
                                    "primary_metric": v.primary_metric}, v.id)
    for org in _all_orgs(db):
        activity(db, org, "model_deployed", f"Modelo {v.network_key} v{v.version} publicado", actor_id=actor_id, visibility="staff")
    store.invalidate("dash:")


@router.post("/ml/models/{model_id}/approve")
def approve(model_id: uuid.UUID, body: ApprovalIn, p: Principal = Depends(require("ml:approve")), db: Session = Depends(get_db)):
    v = get_or_404(db, ModelVersion, model_id)
    _approve(db, v, p, body.note, body.force)
    audit(db, p, "model.approved" + (".forced" if body.force and not v.beats_baseline else ""), "model_version", v.id,
          {"network": v.network_key, "version": v.version, "note": body.note})
    db.commit()
    return version_dto(v)


@router.post("/ml/models/{model_id}/reject")
def reject(model_id: uuid.UUID, body: ApprovalIn, p: Principal = Depends(require("ml:approve")), db: Session = Depends(get_db)):
    v = get_or_404(db, ModelVersion, model_id)
    if v.stage == "production":
        raise HTTPException(409, "Haga rollback antes de rechazar el modelo en producción")
    v.approval_status, v.approval_note, v.stage = "rejected", body.note, "archived"
    audit(db, p, "model.rejected", "model_version", v.id, {"note": body.note})
    db.commit()
    return version_dto(v)


@router.post("/ml/models/{model_id}/promote")
def promote(model_id: uuid.UUID, p: Principal = Depends(require("ml:approve")), db: Session = Depends(get_db)):
    v = get_or_404(db, ModelVersion, model_id)
    _promote(db, v, p.id)
    audit(db, p, "model.deployed", "model_version", v.id, {"network": v.network_key, "version": v.version})
    db.commit()
    return version_dto(v)


@router.post("/ml/networks/{key}/rollback")
def rollback(key: str, p: Principal = Depends(require("ml:approve")), db: Session = Depends(get_db)):
    cur = production(db, key)
    prev = db.scalar(select(ModelVersion).where(ModelVersion.network_key == key, ModelVersion.approval_status == "approved",
                                                ModelVersion.stage == "archived", ModelVersion.promoted_at.is_not(None))
                     .order_by(ModelVersion.promoted_at.desc()).limit(1))
    if not prev:
        raise HTTPException(409, "No hay versión anterior aprobada para rollback")
    _promote(db, prev, p.id)
    audit(db, p, "model.rollback", "model_version", prev.id, {"network": key, "from": cur.version if cur else None, "to": prev.version})
    db.commit()
    return version_dto(prev)


# ----------------------------------------------------------------- Inferencia
class PredictIn(BaseModel):
    network_key: str
    student_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    features: dict | None = None
    example_id: str | None = None
    feature_schema_version: str | None = Field(None, description="Versión del esquema de features (se valida contra el servicio ML)")
    version: str | None = Field(None, description="Solo ML/admin: probar versión no productiva (shadow)")


def run_prediction(db: Session, p: Principal | None, body: PredictIn, org_id) -> dict:
    if body.network_key not in NETWORK_KEYS:
        raise HTTPException(422, "Red desconocida")
    prod = production(db, body.network_key)
    version = body.version if (body.version and p and (p.has("ml:train") or p.has("ml:approve"))) else (prod.version if prod else None)
    if not version:
        raise HTTPException(409, "No hay modelo publicado para esta red. Apruebe y promueva una versión.")
    student = None
    if body.student_id:
        student = get_or_404(db, Student, body.student_id, org_id, "Estudiante no encontrado")
        if p and not p.can_see_student(db, student):
            raise HTTPException(403, "No autorizado para este estudiante")
        features = build_features(db, student.id, body.course_id)
    elif body.features:
        features = body.features
    else:
        raise HTTPException(422, "Indique student_id o features (p. ej. un ejemplo DEMO)")
    fsv = body.feature_schema_version or features.get("feature_schema_version") if isinstance(features, dict) else None
    if fsv and fsv != FEATURE_SCHEMA_VERSION:
        raise HTTPException(422, f"feature_schema_version incompatible: esperado {FEATURE_SCHEMA_VERSION}, recibido {fsv}")
    res = ml_post(f"/predict/{body.network_key}",
                  {"version": version, "features": features, "feature_schema_version": fsv or FEATURE_SCHEMA_VERSION})
    mv = db.scalar(select(ModelVersion).where(ModelVersion.network_key == body.network_key, ModelVersion.version == version))
    pred = Prediction(organization_id=org_id, student_id=student.id if student else None, model_version_id=mv.id if mv else None,
                      network_key=body.network_key, model_version=version, task=body.network_key, scores=res["scores"],
                      explanation=res["explanation"], latency_ms=res["latency_ms"], requested_by=p.id if p else None)
    db.add(pred)
    db.flush()
    if student and "mastery_level" in res["scores"] and features.get("course_id"):
        from ..db.models import CourseSkill
        sk = db.scalar(select(CourseSkill.skill_id).where(CourseSkill.course_id == uuid.UUID(features["course_id"])).limit(1))
        if sk:
            lvl = ["Principiante", "Elemental", "Intermedio", "Avanzado", "Experto"].index(res["scores"]["mastery_level"])
            db.add(SkillEvidence(student_id=student.id, skill_id=sk, source_type="ai_estimate", score=res["scores"].get("mastery_confidence", 0.5),
                                 level=lvl, model_version=f"{body.network_key}@{version}"))
    emit(db, "model.inference", {"prediction_id": str(pred.id), "network_key": body.network_key, "version": version,
                                 "activations": res["activations"], "latency_ms": res["latency_ms"]},
         org_id=org_id, actor_id=p.id if p else None, aggregate_id=pred.id, roles=ML_AUDIENCE[:-1], user_ids=[p.id] if p else [])
    return {**res, "id": pred.id, "student_id": student.id if student else None, "features_used": features}


@router.post("/ml/predictions")
def predict(body: PredictIn, p: Principal = Depends(require("ml:predict")), db: Session = Depends(get_db)):
    res = run_prediction(db, p, body, p.org_id)
    audit(db, p, "model.inference", "prediction", res["id"], {"network": body.network_key, "student_id": str(body.student_id) if body.student_id else None})
    db.commit()
    return res


@router.get("/ml/predictions")
def list_predictions(student_id: uuid.UUID | None = None, limit: int = Query(20, le=100), p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    q = select(Prediction).where(Prediction.organization_id == p.org_id).order_by(Prediction.created_at.desc()).limit(limit)
    if p.is_student_only:
        q = q.where(Prediction.student_id == p.student_id)
    elif not p.has("ml:read"):
        raise HTTPException(403, "Sin permiso")
    if student_id:
        q = q.where(Prediction.student_id == student_id)
    return [{"id": x.id, "network_key": x.network_key, "model_version": x.model_version, "scores": x.scores, "explanation": x.explanation,
             "latency_ms": x.latency_ms, "student_id": x.student_id, "created_at": x.created_at, "label": "Estimación (no oficial)"} for x in db.scalars(q)]


# ----------------------------------------------------------------- Callbacks internos del worker
class WorkerEvent(BaseModel):
    type: str
    model_config = {"extra": "allow"}


@internal.post("/training-runs/{run_id}/events")
def run_event(run_id: uuid.UUID, ev: WorkerEvent, db: Session = Depends(get_db)):
    run = db.get(ModelRun, run_id)
    if not run:
        raise HTTPException(404, "run no encontrado")
    data = ev.model_dump()
    now = datetime.now(timezone.utc)
    if ev.type == "progress":
        phase = data.get("phase", run.status)
        run.status = phase if phase in ("loading_data", "training", "validating") else run.status
        run.started_at = run.started_at or now
        run.progress = {k: v for k, v in data.items() if k not in ("type",)}
        if "epoch" in data and "train_loss" in data:
            run.history = [*(run.history or []), {k: data[k] for k in ("epoch", "train_loss", "val_loss", "val_metric", "lr") if k in data}]
        emit_all(db, "model.training.progress", {"run_id": str(run.id), "network_key": run.network_key, "status": run.status, **run.progress}, run.id)
    elif ev.type == "completed":
        run.status, run.finished_at = "completed", now
        run.metrics = {"primary": data.get("primary"), "baseline_primary": data.get("baseline_primary"), "beats_baseline": data.get("beats_baseline"),
                       "test": data.get("metrics", {}).get("test"), "segments": data.get("metrics", {}).get("segments"),
                       "unseen": data.get("metrics", {}).get("test_unseen_students"), "baseline": data.get("baseline")}
        v = ModelVersion(organization_id=run.organization_id, network_key=run.network_key, name=run.network_key, version=data["version"],
                         artifact_uri=f"artifacts/{run.network_key}/{data['version']}", checksum=data.get("checksum"),
                         beats_baseline=bool(data.get("beats_baseline")), primary_metric=data.get("primary"), baseline_metric=data.get("baseline_primary"),
                         metrics={**run.metrics, "primary_metric_name": PRIMARY_NAMES[run.network_key], "params_total": data.get("params_total"),
                                  "temperature": data.get("temperature"), "duration_s": data.get("duration_s")},
                         dataset_version=(data.get("dataset") or {}).get("version"), run_id=run.id)
        db.add(v)
        db.flush()
        emit_all(db, "model.training.completed", {"run_id": str(run.id), "network_key": run.network_key, "version": v.version,
                                                  "primary": v.primary_metric, "baseline": v.baseline_metric, "beats_baseline": v.beats_baseline}, run.id)
        audit(db, None, "model.registered", "model_version", v.id, {"network": v.network_key, "version": v.version, "beats_baseline": v.beats_baseline},
              actor_email="worker@system")
        if (run.requested_by is None and settings.bootstrap_training and settings.environment not in ("staging", "production")
                and v.beats_baseline and not production(db, v.network_key)):
            _approve(db, v, None, "Aprobación automática de arranque DEMO (solo entorno demo; deshabilitar en producción)", False)
            _promote(db, v)
            audit(db, None, "model.auto_promoted_demo", "model_version", v.id, {"network": v.network_key}, actor_email="system@bootstrap")
    elif ev.type == "failed":
        run.status, run.error, run.finished_at = "failed", data.get("error"), now
        emit_all(db, "model.training.failed", {"run_id": str(run.id), "network_key": run.network_key, "error": data.get("error")}, run.id)
    db.commit()
    return {"ok": True}


@internal.post("/datasets/{dataset_id}/events")
def dataset_event(dataset_id: uuid.UUID, ev: WorkerEvent, db: Session = Depends(get_db)):
    d = db.get(Dataset, dataset_id)
    if not d:
        raise HTTPException(404, "dataset no encontrado")
    data = ev.model_dump()
    if ev.type == "progress":
        d.progress = {"step": data.get("step"), "message": data.get("message")}
    elif ev.type == "completed":
        m = data["manifest"]
        quality = m.get("quality") or {}
        d.checksum, d.storage_uri, d.quality, d.schema_version = m["checksum"], m["storage_uri"], quality, m["feature_schema_version"]
        passed = bool(quality.get("passed"))
        demo_auto = d.label == "DEMO" and settings.environment not in ("staging", "production") and passed
        d.status = "approved" if demo_auto else ("ready" if passed else "failed")
        d.progress = {"step": 10, "message": "Publicado" if passed else "Rechazado por puertas de calidad"}
        if demo_auto:
            audit(db, None, "dataset.auto_approved_demo", "dataset", d.id, {"version": d.version, "checksum": d.checksum},
                  actor_email="system@bootstrap")
    else:
        d.status, d.progress = "failed", {"error": data.get("error")}
    emit_all(db, "dataset.updated", {"id": str(d.id), "version": d.version, "status": d.status, "progress": d.progress}, d.id)
    db.commit()
    return {"ok": True}


def bootstrap_if_needed(db: Session) -> None:
    """Primer arranque: dataset DEMO + entrenamiento de las 5 redes (visible en vivo en el visualizador)."""
    if not settings.bootstrap_training or get_queue() is None:
        return
    if db.scalar(select(func.count(ModelVersion.id))) or db.scalar(select(func.count(ModelRun.id))):
        return
    if not db.scalar(select(Dataset.id).where(Dataset.version == settings.default_dataset_version)):
        d = Dataset(name="edumaster-learning-demo", version=settings.default_dataset_version, label="DEMO", status="building")
        db.add(d)
        db.commit()
        get_queue().enqueue("edumaster_ml.jobs.build_dataset_job", str(d.id), settings.default_dataset_version, 42, job_timeout=1800)
    for k in NETWORK_KEYS:
        enqueue_training(db, k, {"dataset_version": settings.default_dataset_version})
