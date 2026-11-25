"""Endurecimiento: cabeceras de seguridad, idempotencia de solicitudes y aislamiento multi-tenant de modelos."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import ModelRun, ModelVersion, Organization, User

API = "/api/v1"


def test_security_headers(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_idempotency_key_on_learning_events(client, H):
    key = f"test-{uuid.uuid4().hex}"
    body = {
        "event_id": str(uuid.uuid4()),
        "event_type": "lesson_viewed",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 60,
    }
    first = client.post(f"{API}/learning-events", headers={**H["student"], "Idempotency-Key": key}, json=body)
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "accepted"

    # Misma Idempotency-Key con otro event_id: debe devolver la respuesta cacheada, no crear otra fila.
    replay = client.post(f"{API}/learning-events", headers={**H["student"], "Idempotency-Key": key},
                         json={**body, "event_id": str(uuid.uuid4())})
    assert replay.status_code == 202, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["event_id"] == first.json()["event_id"]


def _foreign_org_for(db, email: str):
    admin = db.scalar(select(User).where(User.email == email))
    other = db.scalar(select(Organization).where(Organization.id != admin.organization_id).limit(1))
    return other.id


def test_model_runs_and_versions_scoped_by_tenant(client, H):
    with SessionLocal() as db:
        foreign = _foreign_org_for(db, "admin@edumaster.ai")
        run = ModelRun(organization_id=foreign, network_key="reco_ranker", experiment="test", dataset_version="demo-v1",
                       params={}, status="completed")
        db.add(run)
        db.flush()
        version = ModelVersion(organization_id=foreign, network_key="reco_ranker", name="reco_ranker",
                               version=f"test-{uuid.uuid4().hex[:8]}", artifact_uri="artifacts/test", stage="experimental")
        db.add(version)
        platform = ModelRun(organization_id=None, network_key="completion_mlp", experiment="platform", dataset_version="demo-v1",
                            params={}, status="completed")
        db.add(platform)
        db.commit()
        run_id, version_id, platform_id = run.id, version.id, platform.id

    # La institución propietaria sí puede leer su ejecución/versión.
    assert client.get(f"{API}/ml/training-runs/{run_id}", headers=H["other_admin"]).status_code == 200
    assert client.get(f"{API}/ml/models/{version_id}", headers=H["other_admin"]).status_code == 200
    # Otra institución recibe 404 (no revela existencia).
    assert client.get(f"{API}/ml/training-runs/{run_id}", headers=H["admin"]).status_code == 404
    assert client.get(f"{API}/ml/models/{version_id}", headers=H["admin"]).status_code == 404
    # Los artefactos de plataforma (organization_id NULL) son visibles para todas.
    assert client.get(f"{API}/ml/training-runs/{platform_id}", headers=H["admin"]).status_code == 200
