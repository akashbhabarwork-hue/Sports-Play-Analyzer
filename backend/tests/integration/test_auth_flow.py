import logging

import pytest
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.db import PostgresHealthCheck
from app.adapters.pg_queue import PostgresJobQueue
from app.adapters.pg_repos import (
    PostgresJobRepo,
    PostgresResultRepo,
    PostgresSessionRepo,
    PostgresUserRepo,
    PostgresVideoRepo,
)
from app.config import Settings
from app.core.models import OAuthProfile
from app.core.sessions import hash_token
from app.entrypoints.api import create_app
from app.errors import OAuthLoginError
from app.wiring import Container

pytestmark = pytest.mark.integration


class FakeGoogle:
    """Stands in for Google at the adapter boundary; Google is never called in tests."""

    def __init__(self, profile: OAuthProfile | None = None):
        self.profile = profile or OAuthProfile("google", "g-123", "a@example.com", "Ann", None)
        self.fail = False

    async def authorize_redirect(self, request, redirect_uri):
        request.session["oauth"] = "pending"
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?fake=1")

    async def fetch_profile(self, request):
        if self.fail:
            raise OAuthLoginError("Google login failed")
        return self.profile


def make_container(engine, *, secure: bool, oauth) -> Container:
    settings = Settings(
        app_env="test",
        app_origin="https://app.example" if secure else "http://localhost:8000",
        database_url="unused",
        git_sha="t",
        google_client_id="cid",
        google_client_secret="secret",
        session_secret="s" * 32,
        cookie_secure=secure,
    )
    return Container(
        settings=settings,
        health_check=PostgresHealthCheck(engine),
        users=PostgresUserRepo(engine),
        sessions=PostgresSessionRepo(engine),
        videos=PostgresVideoRepo(engine),
        jobs=PostgresJobRepo(engine),
        results=PostgresResultRepo(engine),
        queue=PostgresJobQueue(engine),
        oauth=oauth,
    )


@pytest.fixture
def google():
    return FakeGoogle()


@pytest.fixture
def make_client(engine, google):
    def make(secure: bool = True) -> TestClient:
        container = make_container(engine, secure=secure, oauth=google)
        base = "https://testserver" if secure else "http://testserver"
        return TestClient(create_app(container), base_url=base)

    yield make
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))


def session_rows(engine) -> list[tuple[bytes, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT token_hash, user_id::text FROM sessions")).all()
    return [(bytes(r[0]), r[1]) for r in rows]


def login(client: TestClient):
    return client.get("/auth/callback?code=c&state=s", follow_redirects=False)


def sid_cookie_header(response, name: str) -> str:
    return next(c for c in response.headers.get_list("set-cookie") if c.startswith(f"{name}="))


def test_callback_creates_user_and_hashed_session_with_secure_cookie(engine, make_client):
    client = make_client(secure=True)

    response = login(client)

    assert response.status_code == 303 and response.headers["location"] == "/"
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


def test_dev_cookie_is_sid_without_secure(make_client):
    response = login(make_client(secure=False))

    header = sid_cookie_header(response, "sid").lower()
    assert "httponly" in header and "samesite=lax" in header and "secure" not in header


def test_second_login_rotates_the_session(engine, make_client):
    client = make_client()
    login(client)
    first = client.cookies.get("__Host-sid")

    login(client)  # browser still sends the first cookie
    second = client.cookies.get("__Host-sid")

    assert first != second
    assert [r[0] for r in session_rows(engine)] == [hash_token(second)]  # old row deleted


def test_logout_deletes_session_row_and_expires_cookie(engine, make_client):
    client = make_client()
    login(client)
    assert len(session_rows(engine)) == 1

    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert session_rows(engine) == []
    header = sid_cookie_header(response, "__Host-sid").lower()
    assert "max-age=0" in header or "expires=thu, 01 jan 1970" in header


def test_logout_is_post_only(make_client):
    client = make_client()
    login(client)
    assert client.get("/auth/logout").status_code in (404, 405)


def test_provider_failure_redirects_without_session(engine, make_client, google):
    google.fail = True
    client = make_client()

    response = login(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=oauth_failed"
    assert not any("sid=" in c for c in response.headers.get_list("set-cookie"))
    assert session_rows(engine) == []


def test_tokens_and_secrets_never_logged(make_client, caplog):
    client = make_client()
    # create_app() resets root handlers for JSON logging; re-attach pytest's capture handler.
    logging.getLogger().addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG)

    login(client)
    token = client.cookies.get("__Host-sid")
    client.post("/auth/logout")

    assert "user logged in" in caplog.text
    for secret in (token, "s" * 32, "secret"):
        assert secret not in caplog.text
