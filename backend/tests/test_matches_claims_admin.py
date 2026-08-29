"""Matches, claims and admin routes: JSON bodies and access control."""
from app.models.match import Claim
from tests.helpers import auth_header, report_payload


def make_item(client, token, **overrides):
    response = client.post(
        "/api/items/report",
        data=report_payload(**overrides),
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------------------------------------------- matches

def test_find_matches_accepts_a_json_body(client, student, other_student):
    """These params used to be bare scalars, which FastAPI read as query
    params, so the frontend's JSON body produced a 422 every time."""
    lost = make_item(client, student["access_token"], type="LOST", title="Lost calculator")
    make_item(
        client,
        other_student["access_token"],
        type="FOUND",
        title="Found calculator",
        description="Casio calculator found near the desk SERIAL9931",
    )

    response = client.post(
        "/api/matches/find",
        json={"lost_item_id": lost["id"]},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["lost_item_id"] == lost["id"]
    assert "matches_found" in response.json()


def test_find_matches_requires_auth_and_ownership(client, student, other_student):
    lost = make_item(client, student["access_token"], type="LOST")

    assert client.post("/api/matches/find", json={"lost_item_id": lost["id"]}).status_code == 401

    forbidden = client.post(
        "/api/matches/find",
        json={"lost_item_id": lost["id"]},
        headers=auth_header(other_student["access_token"]),
    )
    assert forbidden.status_code == 403


def test_item_matches_requires_ownership(client, student, other_student):
    lost = make_item(client, student["access_token"], type="LOST")

    assert client.get(f"/api/matches/item/{lost['id']}").status_code == 401

    mine = client.get(
        f"/api/matches/item/{lost['id']}", headers=auth_header(student["access_token"])
    )
    assert mine.status_code == 200

    theirs = client.get(
        f"/api/matches/item/{lost['id']}", headers=auth_header(other_student["access_token"])
    )
    assert theirs.status_code == 403


# ------------------------------------------------------------------ claims

def _match_between(client, student, other_student):
    lost = make_item(client, student["access_token"], type="LOST", title="Lost umbrella")
    make_item(
        client,
        other_student["access_token"],
        type="FOUND",
        title="Found umbrella",
        description="Black umbrella left in the library SERIAL9931",
    )
    result = client.post(
        "/api/matches/find",
        json={"lost_item_id": lost["id"]},
        headers=auth_header(student["access_token"]),
    ).json()
    return result["matches"][0] if result["matches_found"] else None


def test_claim_records_the_authenticated_user_not_the_match_id(
    client, student, other_student, db_session
):
    """Regression: claimant_id was set to claim.match_id."""
    match = _match_between(client, student, other_student)
    assert match is not None, "expected the scoring engine to produce a match"

    response = client.post(
        "/api/claims/challenge/create",
        json={
            "match_id": match["id"],
            "challenge_question": "What is the handle colour?",
            "claimant_answer": "Wooden",
        },
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["claimant_id"] == student["user"]["id"]

    stored = db_session.query(Claim).first()
    assert stored.claimant_id == student["user"]["id"]


def test_claim_creation_requires_auth(client, student, other_student):
    match = _match_between(client, student, other_student)
    response = client.post(
        "/api/claims/challenge/create",
        json={"match_id": match["id"], "challenge_question": "q", "claimant_answer": "a"},
    )
    assert response.status_code == 401


def test_challenge_respond_accepts_json_body_and_checks_owner(
    client, student, other_student
):
    match = _match_between(client, student, other_student)
    claim = client.post(
        "/api/claims/challenge/create",
        json={"match_id": match["id"], "challenge_question": "q", "claimant_answer": "a"},
        headers=auth_header(student["access_token"]),
    ).json()

    ok = client.post(
        "/api/claims/challenge/respond",
        json={"claim_id": claim["id"], "answer": "Wooden handle"},
        headers=auth_header(student["access_token"]),
    )
    assert ok.status_code == 200, ok.text

    intruder = client.post(
        "/api/claims/challenge/respond",
        json={"claim_id": claim["id"], "answer": "Guessing"},
        headers=auth_header(other_student["access_token"]),
    )
    assert intruder.status_code == 403


def test_only_the_finder_can_approve_a_claim(client, student, other_student):
    match = _match_between(client, student, other_student)
    claim = client.post(
        "/api/claims/challenge/create",
        json={"match_id": match["id"], "challenge_question": "q", "claimant_answer": "a"},
        headers=auth_header(student["access_token"]),
    ).json()

    # The claimant is not the finder, so they may not approve their own claim
    self_approve = client.post(
        "/api/claims/challenge/approve",
        json={"claim_id": claim["id"]},
        headers=auth_header(student["access_token"]),
    )
    assert self_approve.status_code == 403

    approved = client.post(
        "/api/claims/challenge/approve",
        json={"claim_id": claim["id"]},
        headers=auth_header(other_student["access_token"]),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["qr_token"]


def test_handshake_verify_requires_an_admin(client, student, other_student, admin):
    match = _match_between(client, student, other_student)
    claim = client.post(
        "/api/claims/challenge/create",
        json={"match_id": match["id"], "challenge_question": "q", "claimant_answer": "a"},
        headers=auth_header(student["access_token"]),
    ).json()
    qr = client.post(
        "/api/claims/challenge/approve",
        json={"claim_id": claim["id"]},
        headers=auth_header(other_student["access_token"]),
    ).json()["qr_token"]

    assert client.post("/api/claims/handshake/verify", json={"qr_token": qr}).status_code == 401

    as_student = client.post(
        "/api/claims/handshake/verify",
        json={"qr_token": qr},
        headers=auth_header(student["access_token"]),
    )
    assert as_student.status_code == 403

    as_admin = client.post(
        "/api/claims/handshake/verify",
        json={"qr_token": qr},
        headers=auth_header(admin["access_token"]),
    )
    assert as_admin.status_code == 200, as_admin.text
    assert as_admin.json()["status"] == "success"

    # Replaying the same QR code must not resolve the handover twice
    replay = client.post(
        "/api/claims/handshake/verify",
        json={"qr_token": qr},
        headers=auth_header(admin["access_token"]),
    )
    assert replay.status_code == 400


def test_handshake_rejects_a_bogus_token(client, admin):
    response = client.post(
        "/api/claims/handshake/verify",
        json={"qr_token": "clearly-not-a-jwt"},
        headers=auth_header(admin["access_token"]),
    )
    assert response.status_code == 400


# ------------------------------------------------------------------ admin

def test_stats_are_public(client, student):
    make_item(client, student["access_token"], type="LOST")
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
    assert response.json()["total_items"] == 1
    assert response.json()["lost_items"] == 1


def test_vault_endpoints_require_admin(client, student, admin):
    assert client.get("/api/admin/vault/unclaimed").status_code == 401
    assert client.get(
        "/api/admin/vault/unclaimed", headers=auth_header(student["access_token"])
    ).status_code == 403
    assert client.get(
        "/api/admin/vault/unclaimed", headers=auth_header(admin["access_token"])
    ).status_code == 200

    assert client.get("/api/admin/qr-scans").status_code == 401
    assert client.get(
        "/api/admin/qr-scans", headers=auth_header(admin["access_token"])
    ).status_code == 200


def test_vault_process_accepts_json_body(client, admin):
    response = client.post(
        "/api/admin/vault/process",
        json={"action": "donation"},
        headers=auth_header(admin["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["action"] == "donation"

    bad = client.post(
        "/api/admin/vault/process",
        json={"action": "incinerate"},
        headers=auth_header(admin["access_token"]),
    )
    assert bad.status_code == 400
