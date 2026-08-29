"""Test harness.

Runs the real FastAPI app against SQLite. The models use two Postgres-only
column types (ARRAY and pgvector's Vector); both are swapped for JSON before the
tables are created, which keeps the list columns working without a Postgres server.
"""
import os
import tempfile
from pathlib import Path

# Must be set before app.core.database builds its engine at import time.
TEST_DIR = Path(tempfile.mkdtemp(prefix="clfis_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DIR / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_DIR / "uploads")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["CAMPUS_EMAIL_DOMAIN"] = "college.edu"

import pytest
from sqlalchemy import JSON
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine, get_db

# Import the models so their tables register on Base.metadata...
from app.models import user as user_model  # noqa: F401
from app.models import item as item_model  # noqa: F401
from app.models import match as match_model  # noqa: F401

# ...then make the Postgres-specific column types portable before create_all runs.
for _table in Base.metadata.tables.values():
    for _column in _table.columns:
        if type(_column.type).__name__ in ("ARRAY", "Vector"):
            _column.type = JSON()

from app.main import app  # noqa: E402  (imported after the type swap)
from app.models.user import User, UserRole  # noqa: E402
from tests.helpers import register  # noqa: E402


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def upload_dir():
    return Path(os.environ["UPLOAD_DIR"])


@pytest.fixture
def student(client):
    return register(client)


@pytest.fixture
def other_student(client):
    return register(client, email="other@college.edu", name="Other Student")


@pytest.fixture
def admin(client, db_session):
    """A registered user promoted to SECURITY_ADMIN, re-issued a token carrying that role."""
    register(client, email="security@college.edu", name="Campus Security")

    user = db_session.query(User).filter(User.email == "security@college.edu").first()
    user.role = UserRole.SECURITY_ADMIN
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "security@college.edu", "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()
