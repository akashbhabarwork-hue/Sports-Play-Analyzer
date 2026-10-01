from datetime import UTC, datetime, timedelta

import pytest

from app.core.sessions import hash_token

pytestmark = pytest.mark.integration

UNAUTHORIZED = {"error": {"code": "UNAUTHORIZED", "message": "Please log in"}}


def test_me_without_cookie_is_401_envelope(client):
    response = client.get("/api/me")
    assert response.status_code == 401 and response.json() == UNAUTHORIZED


def test_me_with_garbage_cookie_is_401(client):
    client.cookies.set("sid", "not-a-real-token")
    assert client.get("/api/me").status_code == 401


def test_me_with_expired_session_is_401(client, container):
    user = container.users.upsert_from_oauth("google", "sub-old", None, None, None)
    container.sessions.create(hash_token("old"), user.id, datetime.now(UTC) - timedelta(seconds=1))
    client.cookies.set("sid", "old")
    assert client.get("/api/me").json() == UNAUTHORIZED


def test_me_returns_the_logged_in_user(client, login_as):
    user = login_as(client, "ann")

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "ann@example.com",
        "name": "Ann",
        "avatar_url": None,
    }


def test_logout_needs_csrf_headers_then_ends_the_session(client, login_as, csrf_headers):
    login_as(client, "ann")
    foreign = {"Origin": "https://evil.example", "X-Requested-With": "fetch"}

    assert client.post("/auth/logout").status_code == 403  # no Origin / header
    assert client.post("/auth/logout", headers=foreign).status_code == 403
    assert client.get("/api/me").status_code == 200  # still logged in

    assert client.post("/auth/logout", headers=csrf_headers).status_code == 204
    assert client.get("/api/me").status_code == 401
