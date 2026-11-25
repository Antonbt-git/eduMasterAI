"""Servicio de inferencia separado (documento maestro §6.1 y §9.7).

Escala de forma independiente a la API. No entrena: solo sirve artefactos versionados.
"""
from __future__ import annotations

import json
import os

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..datasets.pipeline import load_dataset
from ..features.schema import FEATURE_SCHEMA_VERSION, TAB_FEATURES
from ..models.networks import NETWORKS
from ..monitoring.drift import drift_report
from .predictor import ArtifactNotFound, get_predictor, latest_version, list_versions, untrained_graph

app = FastAPI(title="EduMaster ML Inference", version="1.0.0", docs_url="/docs")


def internal_auth(x_internal_token: str = Header(default="")) -> None:
    if x_internal_token != settings.internal_token:
        raise HTTPException(401, "token interno inválido")


class PredictIn(BaseModel):
    version: str | None = Field(None, description="Versión publicada; por defecto la última registrada")
    features: dict
    feature_schema_version: str | None = Field(None, description="Esquema de features declarado por el cliente")


@app.get("/health")
def health():
    return {"status": "ok", "networks": list(NETWORKS)}


@app.get("/networks", dependencies=[Depends(internal_auth)])
def networks():
    out = []
    for k, cls in NETWORKS.items():
        out.append({"key": k, "title": cls.title, "description": cls.description, "task": cls.task,
                    "primary_metric": cls.primary_metric, "versions": list_versions(k)})
    return out


@app.get("/networks/{key}/graph", dependencies=[Depends(internal_auth)])
def graph(key: str, version: str | None = None, weights: bool = True):
    if key not in NETWORKS:
        raise HTTPException(404, "red desconocida")
    v = version or latest_version(key)
    if not v:
        return untrained_graph(key)
    try:
        return get_predictor(key, v).graph(with_weights=weights)
    except ArtifactNotFound:
        raise HTTPException(404, f"artefacto {key}@{v} no encontrado")


@app.get("/networks/{key}/versions/{version}/meta", dependencies=[Depends(internal_auth)])
def meta(key: str, version: str):
    try:
        return get_predictor(key, version).meta
    except ArtifactNotFound:
        raise HTTPException(404, "artefacto no encontrado")


@app.get("/networks/{key}/versions/{version}/model-card", dependencies=[Depends(internal_auth)])
def card(key: str, version: str):
    p = settings.artifact_dir / key / version / "model_card.md"
    if not p.exists():
        raise HTTPException(404, "model card no encontrada")
    return {"markdown": p.read_text(encoding="utf-8")}


@app.post("/predict/{key}", dependencies=[Depends(internal_auth)])
def predict(key: str, body: PredictIn):
    if key not in NETWORKS:
        raise HTTPException(404, "red desconocida")
    if body.feature_schema_version and body.feature_schema_version != FEATURE_SCHEMA_VERSION:
        raise HTTPException(422, f"feature_schema_version incompatible: esperado {FEATURE_SCHEMA_VERSION}, "
                                 f"recibido {body.feature_schema_version}")
    allowed = {"tab", "seq", "course_level", "skill_idx", "course_id", "window", "feature_schema_version"}
    extra = sorted(set(body.features) - allowed)
    if extra:
        raise HTTPException(422, f"features no autorizadas: {extra}")
    tab = body.features.get("tab", {})
    unknown = sorted(set(tab) - set(TAB_FEATURES))
    if unknown:
        raise HTTPException(422, f"features de tabla no autorizadas: {unknown}")
    missing = [f for f in TAB_FEATURES if f not in tab]
    if missing:
        raise HTTPException(422, f"faltan features: {missing}")
    v = body.version or latest_version(key)
    if not v:
        raise HTTPException(409, "la red aún no tiene una versión entrenada")
    try:
        return get_predictor(key, v).predict(body.features)
    except ArtifactNotFound:
        raise HTTPException(404, f"artefacto {key}@{v} no encontrado")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/networks/{key}/versions/{version}/drift", dependencies=[Depends(internal_auth)])
def drift(key: str, version: str):
    """Drift de features (PSI) entre la referencia de entrenamiento y la cohorte de prueba."""
    if key not in NETWORKS:
        raise HTTPException(404, "red desconocida")
    try:
        meta = get_predictor(key, version).meta
    except ArtifactNotFound:
        raise HTTPException(404, f"artefacto {key}@{version} no encontrado")
    ds_version = (meta.get("dataset") or {}).get("version", "demo-v1")
    arr, _ = load_dataset(ds_version)
    tr, te = arr["split"] == "train", arr["split"] == "test"
    report = drift_report(arr["x_tab"][tr], arr["x_tab"][te], TAB_FEATURES)
    max_psi = max((r["psi"] for r in report), default=0.0)
    return {"network_key": key, "version": version, "dataset": ds_version, "reference": "train", "current": "test",
            "max_psi": round(max_psi, 4), "status": "estable" if max_psi < 0.1 else "moderado" if max_psi < 0.25 else "drift",
            "features": report}


@app.get("/examples", dependencies=[Depends(internal_auth)])
def examples(n: int = 8, dataset_version: str = "demo-v1"):
    """Ejemplos seudonimizados del split de prueba (DEMO) para 'seleccionar ejemplo' en el visualizador."""
    arr, manifest = load_dataset(dataset_version)
    idx = np.where(arr["split"] == "test")[0]
    rng = np.random.default_rng(7)
    pick = rng.choice(idx, size=min(n, len(idx)), replace=False)
    out = []
    for i in pick:
        out.append({
            "example_id": f"demo-{int(i)}",
            "label": "DEMO",
            "features": {
                "tab": {k: round(float(v), 4) for k, v in zip(TAB_FEATURES, arr["x_tab"][i])},
                "seq": np.round(arr["x_seq"][i], 3).tolist(),
                "course_level": int(arr["x_cat"][i]),
                "skill_idx": int(arr["x_skill"][i]),
            },
            "ground_truth": {"completion": int(arr["y_completion"][i]), "risk": int(arr["y_risk"][i]), "mastery": int(arr["y_mastery"][i])},
        })
    return {"dataset": manifest["version"], "checksum": manifest["checksum"], "examples": out}


@app.get("/datasets/{version}", dependencies=[Depends(internal_auth)])
def dataset(version: str):
    _, manifest = load_dataset(version)
    return manifest
