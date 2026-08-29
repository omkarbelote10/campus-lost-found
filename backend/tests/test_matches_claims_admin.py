"""Matches, claims and stats routes: automatic matching, JSON bodies, access control."""
from app.models.match import Claim, Match
from tests.helpers import auth_header, report_payload


def make_item(client, token, **overrides):
    response = client.post(
        "/api/items/report",
        data=report_payload(**overrides),
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_counterpart(client, token, **overrides):
    """A FOUND item written to match the default LOST payload: same category and
    zone, and the same SERIAL9931 token so the OCR bonus applies."""
    defaults = {
        "type": "FOUND",
        "title": "Found black iPhone 14",
        "description": "Black iPhone with a cracked screen and blue case, sticker SERIAL9931",
    }
    defaults.update(overrides)
    return make_item(client, token, **defaults)


# ------------------------------------------------------------------ scoring

def test_similarity_scores_are_plain_floats():
    """Regression: np.dot returns a numpy.float32 and psycopg2 cannot adapt one,
    so persisting a match died with "can't adapt type 'numpy.float32'". It only
    appeared once embeddings were real -- NULL embeddings return a Python 0.0 --
    and SQLite accepts numpy scalars, so only a type assertion catches it here.
    """
    from app.services.scoring import ScoringEngine

    left = [0.1] * 768
    right = [0.2] * 768

    assert type(ScoringEngine.calculate_text_score(left, right)) is float
    assert type(ScoringEngine.calculate_visual_score(left, right)) is float


# --------------------------------------------------------- automatic matching

def test_reporting_an_item_runs_matching_automatically(client, student, other_student, db_session):
    """A new report is scored against open counterparts without a second request."""
    lost = make_item(client, student["access_token"], type="LOST")
    assert db_session.query(Match).count() == 0, "nothing to match against yet"

    found = make_counterpart(client, other_student["access_token"])

    stored = db_session.query(Match).all()
    assert len(stored) == 1, "reporting the found item should have produced a match"
    assert stored[0].lost_item_id == lost["id"]
    assert stored[0].found_item_id == found["id"]


def test_matching_runs_in_both_directions(client, student, other_student, db_session):
    """Reporting the LOST item second must match just as reporting it first does."""
    found = make_counterpart(client, other_student["access_token"])
    lost = make_item(client, student["access_token"], type="LOST")

    stored = db_session.query(Match).all()
    assert len(stored) == 1
    assert stored[0].lost_item_id == lost["id"]
    assert stored[0].found_item_id == found["id"]


def test_embeddings_are_stored_on_report(client, student, db_session):
    from app.models.item import Item

    make_item(client, student["access_token"], type="LOST")

    item = db_session.query(Item).first()
    assert item.text_embedding is not None, "text embedding should be generated at report time"


def test_unrelated_items_do_not_match(client, student, other_student, db_session):
    """A found item in another category is never even a candidate."""
    make_item(client, student["access_token"], type="LOST", category="ELECTRONICS")
    make_item(
        client,
        other_student["access_token"],
        type="FOUND",
        category="CLOTHING",
        title="Found red scarf",
        description="A woollen scarf near the gym",
    )

    assert db_session.query(Match).count() == 0


def test_rerunning_matching_does_not_duplicate_rows(client, student, other_student, db_session):
    lost = make_item(client, student["access_token"], type="LOST")
    make_counterpart(client, other_student["access_token"])
    assert db_session.query(Match).count() == 1

    response = client.post(
        "/api/matches/find",
        json={"item_id": lost["id"]},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert db_session.query(Match).count() == 1, "re-running must update, not insert"


# ----------------------------------------------------------------- matches

def test_find_matches_accepts_a_json_body(client, student, other_student):
    """These params used to be bare scalars, which FastAPI read as query
    params, so the frontend's JSON body produced a 422 every time."""
    lost = make_item(client, student["access_token"], type="LOST")
    make_counterpart(client, other_student["access_token"])

    response = client.post(
        "/api/matches/find",
        json={"item_id": lost["id"]},
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["item_id"] == lost["id"]
    assert response.json()["matches_found"] == 1


def test_find_matches_requires_auth_and_ownership(client, student, other_student):
    lost = make_item(client, student["access_token"], type="LOST")

    assert client.post("/api/matches/find", json={"item_id": lost["id"]}).status_code == 401

    forbidden = client.post(
        "/api/matches/find",
        json={"item_id": lost["id"]},
        headers=auth_header(other_student["access_token"]),
    )
    assert forbidden.status_code == 403


def test_my_matches_returns_both_sides_of_the_pair(client, student, other_student):
    lost = make_item(client, student["access_token"], type="LOST")
    found = make_counterpart(client, other_student["access_token"])

    response = client.get(
        "/api/matches/mine", headers=auth_header(student["access_token"])
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert len(payload) == 1
    # "your_item" is whichever end the caller reported.
    assert payload[0]["your_item"]["id"] == lost["id"]
    assert payload[0]["matched_item"]["id"] == found["id"]
    assert payload[0]["matched_item"]["title"] == "Found black iPhone 14"

    # ...and it flips for the other party.
    theirs = client.get(
        "/api/matches/mine", headers=auth_header(other_student["access_token"])
    ).json()
    assert theirs[0]["your_item"]["id"] == found["id"]
    assert theirs[0]["matched_item"]["id"] == lost["id"]


def test_my_matches_requires_auth(client):
    assert client.get("/api/matches/mine").status_code == 401


def test_my_matches_is_empty_without_items(client, student):
    response = client.get("/api/matches/mine", headers=auth_header(student["access_token"]))
    assert response.status_code == 200
    assert response.json() == []


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
    make_item(client, student["access_token"], type="LOST", title="Lost umbrella")
    make_counterpart(
        client,
        other_student["access_token"],
        title="Found umbrella",
        description="Black umbrella left in the library SERIAL9931",
    )
    matches = client.get(
        "/api/matches/mine", headers=auth_header(student["access_token"])
    ).json()
    return matches[0] if matches else None


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


def _open_claim(client, student, other_student):
    match = _match_between(client, student, other_student)
    return client.post(
        "/api/claims/challenge/create",
        json={"match_id": match["id"], "challenge_question": "q", "claimant_answer": "a"},
        headers=auth_header(student["access_token"]),
    ).json()


def test_only_the_finder_can_approve_a_claim(client, student, other_student):
    claim = _open_claim(client, student, other_student)

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
    assert approved.json()["is_challenge_approved"] is True
    assert approved.json()["resolved_at"] is not None


def test_approval_resolves_both_items_and_awards_karma(
    client, student, other_student, db_session
):
    """Approval is now the whole handover: there is no separate QR step."""
    from app.models.item import Item, ItemStatus
    from app.models.user import User

    claim = _open_claim(client, student, other_student)
    finder_before = db_session.query(User).filter(
        User.id == other_student["user"]["id"]
    ).first().karma_score

    approved = client.post(
        "/api/claims/challenge/approve",
        json={"claim_id": claim["id"]},
        headers=auth_header(other_student["access_token"]),
    )
    assert approved.status_code == 200, approved.text

    db_session.expire_all()
    statuses = {item.type.value: item.status for item in db_session.query(Item).all()}
    assert statuses["LOST"] == ItemStatus.RESOLVED
    assert statuses["FOUND"] == ItemStatus.RESOLVED

    finder_after = db_session.query(User).filter(
        User.id == other_student["user"]["id"]
    ).first().karma_score
    assert finder_after == finder_before + 25


def test_approving_twice_is_rejected(client, student, other_student):
    claim = _open_claim(client, student, other_student)
    headers = auth_header(other_student["access_token"])

    first = client.post(
        "/api/claims/challenge/approve", json={"claim_id": claim["id"]}, headers=headers
    )
    assert first.status_code == 200, first.text

    replay = client.post(
        "/api/claims/challenge/approve", json={"claim_id": claim["id"]}, headers=headers
    )
    assert replay.status_code == 400


# ------------------------------------------------------------------- stats

def test_stats_are_public(client, student):
    make_item(client, student["access_token"], type="LOST")
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
    assert response.json()["total_items"] == 1
    assert response.json()["lost_items"] == 1


def test_removed_admin_routes_are_gone(client, student):
    """The vault, QR audit and handshake endpoints went with SECURITY_ADMIN."""
    headers = auth_header(student["access_token"])
    assert client.get("/api/admin/vault/unclaimed", headers=headers).status_code == 404
    assert client.get("/api/admin/qr-scans", headers=headers).status_code == 404
    assert client.post(
        "/api/claims/handshake/verify", json={"qr_token": "x"}, headers=headers
    ).status_code == 404
