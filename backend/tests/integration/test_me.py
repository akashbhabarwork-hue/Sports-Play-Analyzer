from datetime import UTC, datetime, timedelta

import pytest
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
from app.core.sessions import hash_token
from app.entrypoints.api import create_app
from app.wiring import Container

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:8000"
SAME_ORIGIN = {"Origin": ORIGIN, "X-Requested-With": "fetch"}
UNAUTHORIZED = {"error": {"code": "UNAUTHORIZED", "message": "Please log in"}}


@pytest.fixture
def ctx(engine):
    settings = Settings(
        app_env="test", app_origin=ORIGIN, database_url="x", git_sha="t", cookie_secure=False
    )
    container = Container(
        settings=settings,
        health_check=PostgresHealthCheck(engine),
        users=PostgresUserRepo(engine),
        sessions=PostgresSessionRepo(engine),
        videos=PostgresVideoRepo(engine),
        jobs=PostgresJobRepo(engine),
        results=PostgresResultRepo(engine),
        queue=PostgresJobQueue(engine),
    )
    yield container, TestClient(create_app(container))
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))


def sign_in(container, client, token="tok-1", expires_in=timedelta(days=1)):
    user = container.users.upsert_from_oauth("google", f"sub-{token}", "a@x.io", "Ann", "pic")
    container.sessions.create(hash_token(token), user.id, datetime.now(UTC) + expires_in)
    client.cookies.set("sid", token)
    return user


def test_me_without_cookie_is_401_envelope(ctx):
    _, client = ctx
    response = client.get("/api/me")
    assert response.status_code == 401 and response.json() == UNAUTHORIZED


def test_me_with_garbage_cookie_is_401(ctx):
    _, client = ctx
    client.cookies.set("sid", "not-a-real-token")
    assert client.get("/api/me").status_code == 401


def test_me_with_expired_session_is_401(ctx):
    container, client = ctx
    sign_in(container, client, expires_in=timedelta(seconds=-1))
    assert client.get("/api/me").json() == UNAUTHORIZED


def test_me_returns_the_logged_in_user(ctx):
    container, client = ctx
    user = sign_in(container, client)

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "a@x.io",
        "name": "Ann",
        "avatar_url": "pic",
    }


def test_logout_needs_csrf_headers_then_ends_the_session(ctx):
    container, client = ctx
    sign_in(container, client)

    assert client.post("/auth/logout").status_code == 403  # no Origin / header
    assert (
        client.post(
            "/auth/logout", headers={"Origin": "https://evil.example", "X-Requested-With": "fetch"}
        ).status_code
        == 403
    )
    assert client.get("/api/me").status_code == 200  # still logged in

    assert client.post("/auth/logout", headers=SAME_ORIGIN).status_code == 204
    assert client.get("/api/me").status_code == 401
