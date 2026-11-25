"""Registra en la base de datos los artefactos entrenados (meta.json) como
ModelVersion en producción. Uso típico tras entrenar en el host:

    ML_ARTIFACT_DIR=../ml/artifacts python -m scripts.register_models

Es idempotente: si ya existe la versión (network_key, version), la omite.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import ModelRun, ModelVersion

NETWORKS = ["edumaster_mtl", "completion_mlp", "mastery_ordinal", "risk_transformer", "reco_ranker"]


def latest_meta(artifact_dir: Path, key: str) -> dict | None:
    base = artifact_dir / key
    if not base.exists():
        return None
    candidates = sorted(d for d in base.iterdir() if (d / "meta.json").exists())
    if not candidates:
        return None
    return json.loads((candidates[-1] / "meta.json").read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default=os.getenv("ML_ARTIFACT_DIR", "../ml/artifacts"))
    ap.add_argument("--org", default=None, help="Código de institución; vacío = artefacto de plataforma")
    args = ap.parse_args()
    artifact_dir = Path(args.artifacts).expanduser().resolve()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        org_id = None
        if args.org:
            from app.db.models import Organization
            org_id = db.scalar(select(Organization.id).where(Organization.code == args.org))

        registered = []
        for key in NETWORKS:
            meta = latest_meta(artifact_dir, key)
            if not meta:
                print(f"[register] sin artefacto para {key} — omitido")
                continue
            version = meta["version"]
            exists = db.scalar(select(ModelVersion.id).where(ModelVersion.network_key == key, ModelVersion.version == version))
            if exists:
                print(f"[register] {key}@{version} ya registrado — omitido")
                continue
            run = ModelRun(
                organization_id=org_id, network_key=key, experiment=f"edumaster/{key}",
                dataset_version=(meta.get("dataset") or {}).get("version", "demo-v1"),
                params={"epochs": (meta.get("history") or [{}])[-1].get("epoch")}, metrics=meta.get("metrics") or {},
                history=meta.get("history") or [], progress={"phase": "completed"}, status="completed",
                started_at=now, finished_at=now,
            )
            db.add(run)
            db.flush()
            v = ModelVersion(
                organization_id=org_id, network_key=key, name=key, version=version,
                artifact_uri=f"artifacts/{key}/{version}", checksum=meta.get("checksum"),
                stage="production", approval_status="approved", approved_at=now,
                approval_note="Aprobación de arranque DEMO (modelo supera baseline)",
                beats_baseline=bool(meta.get("beats_baseline")), primary_metric=meta.get("primary"),
                baseline_metric=meta.get("baseline_primary"),
                metrics={**(meta.get("metrics") or {}), "primary_metric_name": meta.get("primary_metric_name"),
                         "params_total": meta.get("params_total"), "temperature": meta.get("temperature")},
                dataset_version=(meta.get("dataset") or {}).get("version"), run_id=run.id, promoted_at=now,
            )
            db.add(v)
            registered.append(f"{key}@{version}")
        db.commit()
        print(f"[register] registrados: {', '.join(registered) or 'ninguno'}")


if __name__ == "__main__":
    main()
