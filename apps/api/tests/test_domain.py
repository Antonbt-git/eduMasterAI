"""Reglas de negocio, idempotencia de eventos, KPIs con fuente/fecha, exportaciones y certificados."""
import uuid
from datetime import datetime, timezone

API = "/api/v1"


def test_dashboard_kpis_have_source_and_timestamp(client, H):
    k = client.get(f"{API}/dashboard/summary", headers=H["admin"]).json()["kpis"]
    for name in ("active_students", "courses", "learning_hours", "certifications", "completion_rate"):
        assert "value" in k[name] and k[name]["source"] and k[name]["updated_at"]


def test_filters_change_results(client, H):
    a = client.get(f"{API}/analytics/progress", headers=H["admin"]).json()
    b = client.get(f"{API}/analytics/progress?region=Oceanía", headers=H["admin"]).json()
    assert sum(a["series"][0]["data"]) > sum(b["series"][0]["data"])


def test_event_idempotency_and_validation(client, H):
    prog = client.get(f"{API}/me/progress", headers=H["student"]).json()
    cid = prog["courses"][0]["course_id"]
    ev = {"event_id": str(uuid.uuid4()), "event_type": "lesson_viewed", "occurred_at": datetime.now(timezone.utc).isoformat(),
          "course_id": str(cid), "duration_seconds": 120, "activity_id": "x"}
    assert client.post(f"{API}/learning-events", headers=H["student"], json=ev).json()["status"] == "accepted"
    assert client.post(f"{API}/learning-events", headers=H["student"], json=ev).json()["status"] == "duplicate"
    bad = {**ev, "event_id": str(uuid.uuid4()), "duration_seconds": 50000}
    assert client.post(f"{API}/learning-events", headers=H["student"], json=bad).status_code == 422


def test_course_lifecycle(client, H):
    code = "T" + uuid.uuid4().hex[:5]
    c = client.post(f"{API}/courses", headers=H["admin"], json={"code": code, "title": "Curso test"}).json()
    assert client.post(f"{API}/courses/{c['id']}/publish", headers=H["admin"]).status_code == 422, "sin contenido no se publica"
    client.post(f"{API}/courses/{c['id']}/units", headers=H["admin"], json={"title": "U1", "lessons": [{"title": "L1"}]})
    p = client.post(f"{API}/courses/{c['id']}/publish", headers=H["admin"]).json()
    assert p["status"] == "published" and p["version"] >= 3
    assert client.post(f"{API}/courses", headers=H["admin"], json={"code": code, "title": "Duplicado"}).status_code == 409


def test_attempt_limits_and_grading(client, H):
    a = next(x for x in client.get(f"{API}/assessments", headers=H["student"]).json() if x["type"] == "multiple_choice")
    ok = {"0": "Aplicar conceptos a problemas reales", "1": "Retropropagación del error", "2": "Falso"}
    statuses = [client.post(f"{API}/assessments/{a['id']}/attempts", headers=H["student"], json={"answers": ok}).status_code for _ in range(a["attempts_allowed"] + 1)]
    assert 409 in statuses  # agotó intentos


def test_exports(client, H):
    for fmt, mime in (("csv", "text/csv"), ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        r = client.get(f"{API}/analytics/export?format={fmt}", headers=H["admin"])
        assert r.status_code == 200 and mime in r.headers["content-type"]
    assert client.get(f"{API}/analytics/export?format=csv", headers=H["student"]).status_code == 403


def test_certificate_verify_minimal_exposure(client, H):
    cert = client.get(f"{API}/certificates", headers=H["admin"]).json()["items"][0]
    v = client.get(f"{API}/certificates/verify/{cert['verification_code']}").json()
    assert v["valid"] and "email" not in v and v["holder"].endswith(".")
    assert client.get(f"{API}/certificates/{cert['id']}/pdf", headers=H["admin"]).headers["content-type"] == "application/pdf"


def test_prediction_degrades_without_ml(client, H):
    r = client.post(f"{API}/ml/predictions", headers=H["admin"], json={"network_key": "risk_transformer", "features": {"tab": {}}})
    assert r.status_code in (409, 503)


def test_cursor_pagination(client, H):
    p1 = client.get(f"{API}/audit-logs?limit=2", headers=H["admin"]).json()
    if p1["next_cursor"]:
        p2 = client.get(f"{API}/audit-logs?limit=2&cursor={p1['next_cursor']}", headers=H["admin"]).json()
        assert {x["id"] for x in p1["items"]}.isdisjoint({x["id"] for x in p2["items"]})
