"""Test harness.

Runs the real FastAPI app against SQLite. The models use two Postgres-only
column types (ARRAY and pgvector's Vector); both are swapped for JSON before the
tables are created, which keeps the list columns working without a Postgres server.
"""
import os
import tempfile
import zlib
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


class _StubEmbedder:
    """Deterministic stand-in for SigLIP, used only by the test suite.

    Downloading ~400MB of weights on every test run is not viable, but stubbing
    the embedder out entirely would leave the storage and scoring paths untested.
    This hashes tokens into a 768-d vector, so texts that share words land near
    each other and unrelated texts do not -- enough to exercise both the match
    and no-match branches.

    Deliberately not shipped in app code: a fabricated embedding in production
    produces a confident-looking similarity that means nothing.
    """

    is_available = True

    @staticmethod
    def _hash_tokens(tokens):
        vec = [0.0] * 768
        for token in tokens:
            # crc32, not hash(): PYTHONHASHSEED randomises str hashing per
            # process, which would make scores differ between runs.
            slot = zlib.crc32(token.encode("utf-8")) % 768
            vec[slot] += 1.0
        norm = sum(value * value for value in vec) ** 0.5
        return [value / norm for value in vec] if norm else None

    def embed_text(self, text):
        if not text or not text.strip():
            return None
        return self._hash_tokens(text.lower().split())

    def embed_image(self, image):
        return self._hash_tokens([str(image)])


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch):
    stub = _StubEmbedder()
    monkeypatch.setattr("app.services.embeddings._embedder", stub)
    monkeypatch.setattr("app.services.embeddings.get_embedder", lambda: stub)
    monkeypatch.setattr("app.api.items.get_embedder", lambda: stub)
    return stub
