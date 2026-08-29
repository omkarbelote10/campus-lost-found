"""Reporting items, uploads, and the feed's high-value masking."""
from app.models.item import Item
from tests.helpers import PNG_BYTES, WEBP_BYTES, auth_header, report_payload


def post_report(client, token, files=None, **overrides):
    return client.post(
        "/api/items/report",
        data=report_payload(**overrides),
        files=files,
        headers=auth_header(token),
    )


# --------------------------------------------------------------- reporting

def test_report_requires_authentication(client):
    assert client.post("/api/items/report", data=report_payload()).status_code == 401


def test_report_multipart_succeeds(client, student):
    response = post_report(client, student["access_token"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Black iPhone 14"
    assert body["type"] == "LOST"
    assert body["status"] == "OPEN"
    assert body["user_id"] == student["user"]["id"]
    assert "SERIAL9931" in body["ocr_tokens"]


def test_report_sent_as_json_is_rejected(client, student):
    """This is exactly what the frontend used to send when axios had a JSON
    Content-Type default: the form fields arrive as a JSON body and every
    Form(...) parameter comes back missing."""
    response = client.post(
        "/api/items/report",
        json=report_payload(),
        headers=auth_header(student["access_token"]),
    )
    assert response.status_code == 422
    missing = {tuple(err["loc"])[-1] for err in response.json()["detail"]}
    assert "title" in missing and "type" in missing


def test_report_rejects_invalid_incident_time(client, student):
    response = post_report(client, student["access_token"], incident_time="not-a-date")
    assert response.status_code == 400
    assert "incident_time" in response.json()["detail"]


def test_report_rejects_unknown_type_and_category(client, student):
    assert post_report(client, student["access_token"], type="SIDEWAYS").status_code == 400
    assert post_report(client, student["access_token"], category="SPACESHIP").status_code == 400


# ----------------------------------------------------------------- uploads

def test_report_accepts_webp_upload(client, student, upload_dir):
    """The upload UI offers WEBP; the backend used to reject it."""
    files = [("images", ("photo.webp", WEBP_BYTES, "image/webp"))]
    response = post_report(client, student["access_token"], files=files)
    assert response.status_code == 200, response.text

    urls = response.json()["image_urls"]
    assert len(urls) == 1
    assert (upload_dir / urls[0].split("/")[-1]).exists()


def test_uploaded_filename_is_generated_not_client_supplied(client, student, upload_dir):
    files = [("images", ("../../evil script.png", PNG_BYTES, "image/png"))]
    response = post_report(client, student["access_token"], files=files)
    assert response.status_code == 200, response.text

    stored = response.json()["image_urls"][0]
    assert "evil" not in stored and ".." not in stored and " " not in stored
    assert stored.endswith(".png")
    # The file landed inside the upload directory, not above it
    written = list(upload_dir.glob("*.png"))
    assert len(written) == 1
    assert written[0].parent == upload_dir


def test_report_rejects_disallowed_extension(client, student):
    files = [("images", ("payload.exe", b"MZ\x90\x00", "application/octet-stream"))]
    response = post_report(client, student["access_token"], files=files)
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_report_rejects_more_than_three_images(client, student):
    files = [("images", (f"p{i}.png", PNG_BYTES, "image/png")) for i in range(4)]
    response = post_report(client, student["access_token"], files=files)
    assert response.status_code == 400
    assert "maximum of 3" in response.json()["detail"]


def test_report_rejects_oversized_image(client, student):
    from app.core.config import get_settings

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (get_settings().MAX_UPLOAD_SIZE + 1)
    files = [("images", ("huge.png", oversized, "image/png"))]
    response = post_report(client, student["access_token"], files=files)
    assert response.status_code == 413


def test_report_without_images_succeeds(client, student):
    response = post_report(client, student["access_token"])
    assert response.status_code == 200
    assert response.json()["image_urls"] == []


# ------------------------------------------------------- feed and masking

def test_feed_lists_open_items(client, student):
    post_report(client, student["access_token"])
    response = client.get("/api/items/feed")
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Black iPhone 14"]


def test_feed_filters_by_type_and_category(client, student):
    post_report(client, student["access_token"])
    post_report(client, student["access_token"], type="FOUND", title="Found keys", category="KEYS")

    lost = client.get("/api/items/feed", params={"type": "LOST"}).json()
    assert [i["title"] for i in lost] == ["Black iPhone 14"]

    keys = client.get("/api/items/feed", params={"category": "KEYS"}).json()
    assert [i["title"] for i in keys] == ["Found keys"]


def test_high_value_images_visible_to_owner_but_masked_for_everyone_else(
    client, student, other_student
):
    """Regression: current_user_id was a dead query param, so the owner's own
    high-value item was masked from them too."""
    files = [("images", ("passport.png", PNG_BYTES, "image/png"))]
    created = post_report(
        client, student["access_token"], files=files, is_high_value="true", title="Passport"
    )
    assert created.status_code == 200, created.text

    owner_view = client.get("/api/items/feed", headers=auth_header(student["access_token"]))
    assert len(owner_view.json()[0]["image_urls"]) == 1

    stranger_view = client.get("/api/items/feed", headers=auth_header(other_student["access_token"]))
    assert stranger_view.json()[0]["image_urls"] == []

    anonymous_view = client.get("/api/items/feed")
    assert anonymous_view.json()[0]["image_urls"] == []


def test_feed_masking_does_not_erase_urls_from_the_database(client, student, db_session):
    files = [("images", ("passport.png", PNG_BYTES, "image/png"))]
    post_report(client, student["access_token"], files=files, is_high_value="true")

    client.get("/api/items/feed")  # anonymous request triggers masking

    stored = db_session.query(Item).first()
    assert len(stored.image_urls) == 1, "masking must not mutate the persisted row"


def test_single_item_endpoint_masks_high_value_for_non_owners(client, student, other_student):
    """Without this the item detail route was a way around the feed's masking."""
    files = [("images", ("passport.png", PNG_BYTES, "image/png"))]
    item_id = post_report(
        client, student["access_token"], files=files, is_high_value="true"
    ).json()["id"]

    owner = client.get(f"/api/items/{item_id}", headers=auth_header(student["access_token"]))
    assert len(owner.json()["image_urls"]) == 1

    stranger = client.get(f"/api/items/{item_id}", headers=auth_header(other_student["access_token"]))
    assert stranger.json()["image_urls"] == []

    assert client.get("/api/items/999999").status_code == 404


# ------------------------------------------------------------- my items

def test_user_items_requires_auth_and_returns_only_own_items(client, student, other_student):
    post_report(client, student["access_token"], title="Mine")
    post_report(client, other_student["access_token"], title="Theirs")

    assert client.get("/api/items/").status_code == 401

    mine = client.get("/api/items/", headers=auth_header(student["access_token"]))
    assert [item["title"] for item in mine.json()] == ["Mine"]
