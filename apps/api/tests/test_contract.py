"""Pruebas de contrato: los endpoints exigidos por la especificación existen y aceptan el método correcto."""
from app.main import app

REQUIRED = {
    "/api/v1/dashboard/summary": {"get"},
    "/api/v1/analytics/progress": {"get"},
    "/api/v1/analytics/skill-mastery": {"get"},
    "/api/v1/courses": {"get", "post"},
    "/api/v1/learning-events": {"post"},
    "/api/v1/students/{student_id}/progress": {"get"},
    "/api/v1/recommendations": {"get"},
    "/api/v1/recommendations/{rec_id}/feedback": {"post"},
    "/api/v1/ml/training-runs": {"post", "get"},
    "/api/v1/ml/training-runs/{run_id}": {"get"},
    "/api/v1/ml/models": {"get"},
    "/api/v1/ml/predictions": {"post"},
    "/api/v1/certificates/verify/{code}": {"get"},
    "/api/v1/audit-logs": {"get"},
    "/api/v1/ml/networks/{key}/drift": {"get"},
    "/api/v1/certificates/drafts": {"post"},
}


def test_required_endpoints_exist():
    paths = app.openapi()["paths"]
    missing = []
    for path, methods in REQUIRED.items():
        if path not in paths:
            missing.append(path)
            continue
        absent = methods - set(paths[path])
        if absent:
            missing.append(f"{path} ({', '.join(sorted(absent))})")
    assert not missing, f"Endpoints exigidos ausentes: {missing}"
