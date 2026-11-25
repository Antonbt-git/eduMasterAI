"""Seguridad: autenticación, RBAC vertical/horizontal, aislamiento multi-tenant, auditoría inmutable."""
import uuid

API = "/api/v1"


def test_login_invalid(client):
    r = client.post(f"{API}/auth/login", json={"email": "admin@edumaster.ai", "password": "incorrecta123"})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized" and r.json()["correlation_id"]


def test_requires_auth(client):
    assert client.get(f"{API}/dashboard/summary").status_code == 401


def test_refresh_rotation(client):
    t = client.post(f"{API}/auth/login", json={"email": "analista@edumaster.ai", "password": "EduMaster#2026"}).json()
    r1 = client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r1.status_code == 200
    r2 = client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r2.status_code == 401, "un refresh token no puede reutilizarse"


def test_vertical_authorization(client, H):
    assert client.post(f"{API}/courses", headers=H["student"], json={"code": "HACK", "title": "Hack course"}).status_code == 403
    assert client.get(f"{API}/students", headers=H["student"]).status_code == 403
    assert client.get(f"{API}/users", headers=H["instructor"]).status_code == 403
    assert client.post(f"{API}/ml/training-runs", headers=H["instructor"], json={"network_key": "reco_ranker"}).status_code == 403


def test_horizontal_student_isolation(client, H):
    students = client.get(f"{API}/students?limit=5", headers=H["admin"]).json()["items"]
    me = client.get(f"{API}/auth/me", headers=H["student"]).json()["student_id"]
    other = next(s for s in students if str(s["id"]) != me)
    assert client.get(f"{API}/students/{other['id']}/progress", headers=H["student"]).status_code == 403
    assert client.get(f"{API}/students/{me}/progress", headers=H["student"]).status_code == 200


def test_multi_tenant_isolation(client, H):
    course = client.get(f"{API}/courses", headers=H["admin"]).json()["items"][0]
    assert client.get(f"{API}/courses/{course['id']}", headers=H["other_admin"]).status_code == 404
    other_courses = client.get(f"{API}/courses", headers=H["other_admin"]).json()["items"]
    assert all(c["code"].startswith("AN-") for c in other_courses)
    kpis = client.get(f"{API}/dashboard/summary", headers=H["other_admin"]).json()["kpis"]
    assert kpis["certifications"]["value"] == 0
    st = client.get(f"{API}/students?limit=1", headers=H["admin"]).json()["items"][0]
    assert client.get(f"{API}/students/{st['id']}/progress", headers=H["other_admin"]).status_code == 404


def test_instructor_abac(client, H):
    items = client.get(f"{API}/courses?page_size=50", headers=H["instructor"]).json()["items"]
    all_items = client.get(f"{API}/courses?page_size=50", headers=H["admin"]).json()["items"]
    assert 0 < len(items) < len(all_items), "el docente solo ve cursos asignados"


def test_analyst_pseudonymized(client, H):
    r = client.get(f"{API}/students?limit=3", headers=H["analyst"]).json()
    assert r["pseudonymized"] and all(s["email"] is None for s in r["items"])


def test_audit_chain_and_scope(client, H):
    client.get(f"{API}/analytics/export?format=csv", headers=H["admin"])
    v = client.get(f"{API}/audit-logs/verify", headers=H["auditor"]).json()
    assert v["valid"] and v["entries"] > 0
    own = client.get(f"{API}/audit-logs", headers=H["student"]).json()["items"]
    me = client.get(f"{API}/auth/me", headers=H["student"]).json()["email"]
    assert all(a["actor_email"] == me for a in own)


def test_xss_escaped(client, H):
    r = client.post(f"{API}/community/threads", headers=H["student"], json={"title": "<script>alert(1)</script>", "body": "<img src=x onerror=1>"})
    assert r.status_code == 201
    assert "<script>" not in r.json()["title"]
