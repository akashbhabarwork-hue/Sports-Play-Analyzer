import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.sessions import hash_token
from app.entrypoints.api import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def settings(settings_factory):
    # This module checks production cookie flags: https + __Host-sid.
    return settings_factory(secure=True)


@pytest.fixture
def dev_client(settings_factory, container_factory) -> TestClient:
    app = create_app(container_factory(settings_factory(secure=False)))
    return TestClient(app, base_url="http://testserver")


def session_rows(engine) -> list[tuple[bytes, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT token_hash, user_id::text FROM sessions")).all()
    return [(bytes(r[0]), r[1]) for r in rows]


def login(client: TestClient):
    return client.get("/auth/callback?code=c&state=s", follow_redirects=False)


def sid_cookie_header(response, name: str) -> str:
    return next(c for c in response.headers.get_list("set-cookie") if c.startswith(f"{name}="))


def test_callback_creates_user_and_hashed_session_with_secure_cookie(engine, client):
    response = login(client)

    assert response.status_code == 303 and response.headers["location"] == "/app"
    header = sid_cookie_header(response, "__Host-sid").lower()
    for flag in ("httponly", "secure", "samesite=lax", "path=/", "max-age=604800"):
        assert flag in header
    assert "domain=" not in header  # required by the __Host- prefix
    token = client.cookies.get("__Host-sid")
    rows = session_rows(engine)
    assert len(rows) == 1
    assert rows[0][0] == hash_token(token) and token.encode() not in rows[0][0]
    with engine.connect() as conn:
        user = conn.execute(text("SELECT provider, provider_sub, email FROM users")).one()
    assert tuple(user) == ("google", "g-123", "a@example.com")


def test_dev_cookie_is_sid_without_secure(dev_client):
    response = login(dev_client)

    header = sid_cookie_header(response, "sid").lower()
    assert "httponly" in header and "samesite=lax" in header and "secure" not in header


def test_second_login_rotates_the_session(engine, client):
    login(client)
    first = client.cookies.get("__Host-sid")

    login(client)  # browser still sends the first cookie
    second = client.cookies.get("__Host-sid")

    assert first != second
    assert [r[0] for r in session_rows(engine)] == [hash_token(second)]  # old row deleted


def test_logout_deletes_session_row_and_expires_cookie(engine, client, csrf_headers):
    login(client)
    assert len(session_rows(engine)) == 1

    response = client.post("/auth/logout", headers=csrf_headers)

    assert response.status_code == 204
    assert session_rows(engine) == []
    header = sid_cookie_header(response, "__Host-sid").lower()
    assert "max-age=0" in header or "expires=thu, 01 jan 1970" in header


def test_logout_is_post_only(client):
    login(client)
    assert client.get("/auth/logout").status_code in (404, 405)


def test_provider_failure_redirects_without_session(engine, client, google):
    google.fail = True

    response = login(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=oauth_failed"
    assert not any("sid=" in c for c in response.headers.get_list("set-cookie"))
    assert session_rows(engine) == []


def test_tokens_and_secrets_never_logged(client, csrf_headers, caplog):
    # create_app() resets root handlers for JSON logging; re-attach pytest's capture handler.
    logging.getLogger().addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG)

    login(client)
    token = client.cookies.get("__Host-sid")
    client.post("/auth/logout", headers=csrf_headers)

    assert "user logged in" in caplog.text
    for secret in (token, "s" * 32, "secret"):
        assert secret not in caplog.text
