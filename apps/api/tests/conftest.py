import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{_db}", REDIS_URL="", DEMO_SIMULATOR="false", BOOTSTRAP_TRAINING="false",
                  ML_SERVICE_URL="http://127.0.0.1:9", RATE_LIMIT_PER_MINUTE="100000", LOGIN_RATE_LIMIT_PER_MINUTE="1000")

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.seed import seed

Base.metadata.create_all(engine)
with SessionLocal() as _s:
    seed(_s)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "EduMaster#2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def H(client):
    emails = {"admin": "admin@edumaster.ai", "student": "estudiante@edumaster.ai", "instructor": "docente@edumaster.ai",
              "analyst": "analista@edumaster.ai", "ml": "ml@edumaster.ai", "auditor": "auditor@edumaster.ai", "other_admin": "admin@andino.edu",
              "other_student": "estudiante@andino.edu"}
    return {k: _login(client, v) for k, v in emails.items()}
