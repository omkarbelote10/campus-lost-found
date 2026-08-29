"""Side-effect-free helpers shared by the test modules.

Kept out of conftest.py so importing them never re-runs the test database setup.
"""


def register(client, email="student@college.edu", password="password123", name="Test Student"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def report_payload(**overrides):
    payload = {
        "type": "LOST",
        "title": "Black iPhone 14",
        "description": "Cracked screen, blue case, sticker SERIAL9931",
        "category": "ELECTRONICS",
        "campus_zone": "Library Zone",
        "incident_time": "2026-08-29T14:30",
        "is_high_value": "false",
    }
    payload.update(overrides)
    return payload


# A 1x1 pixel in a couple of formats, for upload tests.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100"
    "05fe02fea7d4b3e70000000049454e44ae426082"
)
WEBP_BYTES = (
    b"RIFF$\x00\x00\x00WEBPVP8 \x18\x00\x00\x000\x01\x00\x9d\x01*\x01\x00"
    b"\x01\x00\x02\x004%\xa8\x00\x03p\x00\xfe\xfb\xfd\x00\x00"
)
