"""Authentication: registration, login, and the /auth/me endpoint."""
from datetime import timedelta

from app.core.security import create_access_token
from tests.helpers import auth_header, register


def test_register_returns_token_and_user(client):
    data = register(client)
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "student@college.edu"
    assert data["user"]["karma_score"] == 100
    assert data["user"]["role"] == "STUDENT"


def test_register_rejects_non_campus_email(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "someone@gmail.com", "password": "password123", "full_name": "Nope"},
    )
    assert response.status_code == 400
    assert "college.edu" in response.json()["detail"]


def test_register_rejects_duplicate_email(client, student):
    response = client.post(
        "/api/auth/register",
        json={"email": "student@college.edu", "password": "password123", "full_name": "Dup"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_succeeds_and_rejects_bad_password(client, student):
    ok = client.post(
        "/api/auth/login",
        json={"email": "student@college.edu", "password": "password123"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post(
        "/api/auth/login",
        json={"email": "student@college.edu", "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_me_returns_profile_for_valid_token(client, student):
    """Regression: /auth/me read a query param that was never sent, so it always 401'd."""
    response = client.get("/api/auth/me", headers=auth_header(student["access_token"]))
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "student@college.edu"
    assert response.json()["id"] == student["user"]["id"]


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth_header("not-a-jwt")).status_code == 401


def test_expired_token_is_rejected(client, student):
    expired = create_access_token(
        data={"sub": str(student["user"]["id"]), "role": "STUDENT"},
        expires_delta=timedelta(minutes=-5),
    )
    assert client.get("/api/auth/me", headers=auth_header(expired)).status_code == 401


def test_token_lifetime_is_long_enough_to_finish_a_report(client, student):
    """The 30-minute lifetime was expiring mid-session and bouncing users to /login."""
    import jose.jwt as jwt
    from app.core.config import get_settings
    from datetime import datetime, timezone

    settings = get_settings()
    payload = jwt.decode(
        student["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    remaining = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) - datetime.now(timezone.utc)
    assert remaining > timedelta(hours=24)
