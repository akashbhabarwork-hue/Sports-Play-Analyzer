import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

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
from app.core.models import OAuthProfile, User
from app.entrypoints.api import create_app
from app.errors import OAuthLoginError
from app.services.auth import login_user
from app.wiring import Container

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    return cfg


@pytest.fixture(scope="session")
def engine(alembic_cfg):
    """A freshly migrated database shared by the integration session."""
    eng = create_engine(TEST_DATABASE_URL)
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    yield eng
    eng.dispose()


# ---- app-level fixtures (T-032): real Postgres repos, fake Google, one cookie jar per client


APP_ORIGIN = "http://localhost:8000"
SECURE_ORIGIN = "https://app.example"


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


def make_settings(secure: bool = False) -> Settings:
    """Dev-style settings (cookie `sid`, http) unless `secure` (cookie `__Host-sid`, https)."""
    return Settings(
        app_env="test",
        app_origin=SECURE_ORIGIN if secure else APP_ORIGIN,
        database_url="unused",
        git_sha="test",
        google_client_id="cid",
        google_client_secret="secret",
        session_secret="s" * 32,
        cookie_secure=secure,
    )


def make_container(engine, settings: Settings, oauth=None) -> Container:
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


@pytest.fixture(autouse=True)
def clean_db(engine):
    """Every integration test starts from empty tables (schema stays migrated)."""
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def container(engine, settings, google) -> Container:
    return make_container(engine, settings, google)


@pytest.fixture
def make_client(container):
    """Factory: each call is a separate browser (own cookie jar) on the same app."""
    app = create_app(container)
    base_url = "https://testserver" if container.settings.cookie_secure else "http://testserver"

    def make() -> TestClient:
        return TestClient(app, base_url=base_url)

    return make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def csrf_headers(settings) -> dict[str, str]:
    """What our SPA sends on unsafe requests (T-031 CSRF check)."""
    return {"Origin": settings.app_origin, "X-Requested-With": "fetch"}


@pytest.fixture
def login_as(container):
    """Log `client` in as `name` through the real session-issuing service (no OAuth round trip)."""

    def login(client: TestClient, name: str) -> User:
        profile = OAuthProfile("google", f"sub-{name}", f"{name}@example.com", name.title(), None)
        user, token = login_user(
            container.users,
            container.sessions,
            profile,
            datetime.now(UTC),
            container.settings.session_ttl_days,
        )
        client.cookies.set(container.settings.session_cookie_name, token)
        return user

    return login


@pytest.fixture
def settings_factory():
    """`settings_factory(secure=True)` → https settings with the `__Host-sid` cookie."""
    return make_settings


@pytest.fixture
def container_factory(engine, google):
    def make(settings: Settings) -> Container:
        return make_container(engine, settings, google)

    return make
