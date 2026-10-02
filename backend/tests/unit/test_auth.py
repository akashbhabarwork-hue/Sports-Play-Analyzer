import logging
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.adapters.oauth_google import GoogleOAuthClient
from app.config import Settings, validate_settings
from app.core.models import OAuthProfile
from app.core.sessions import hash_token
from app.entrypoints.api import create_app
from app.wiring import Container

NO_REPOS = dict.fromkeys(
    (
        "users",
        "sessions",
        "videos",
        "jobs",
        "results",
        "queue",
        "blobs",
        "prober",
        "media_info",
        "downloader",
    )
)


class OkHealth:
    def check_db(self) -> bool:
        return True


def make_settings(**overrides) -> Settings:
    base = dict(
        app_env="test",
        app_origin="https://app.example",
        database_url="sqlite://",
        git_sha="t",
        google_client_id="cid.apps.googleusercontent.com",
        google_client_secret="client-secret-value",
        session_secret="s" * 32,
        blob_backend="s3",
        s3_bucket="media",
        s3_access_key_id="key-id",
        s3_secret_access_key="key-secret",
    )
    return Settings(**{**base, **overrides})


def client_for(settings: Settings, oauth) -> TestClient:
    container = Container(**NO_REPOS, settings=settings, health_check=OkHealth(), oauth=oauth)
    return TestClient(create_app(container), base_url="https://testserver")


def test_hash_token_is_sha256_and_never_the_token():
    digest = hash_token("abc")
    assert len(digest) == 32 and digest != b"abc"
    assert hash_token("abc") == digest and hash_token("abd") != digest


def test_auth_login_redirects_to_google_with_pkce_s256():
    settings = make_settings()
    client = client_for(settings, GoogleOAuthClient("cid", "secret"))

    response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 302
    url = urlparse(response.headers["location"])
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert (url.netloc, url.path) == ("accounts.google.com", "/o/oauth2/v2/auth")
    assert params["response_type"] == "code"
    assert params["code_challenge_method"] == "S256"
    assert len(params["code_challenge"]) >= 43  # base64url(sha256(verifier))
    assert params["state"] and params["nonce"]
    assert params["redirect_uri"] == "https://app.example/auth/callback"
    assert set(params["scope"].split()) == {"openid", "email", "profile"}
    # The verifier itself never leaves the server in the URL.
    assert "code_verifier" not in params
    oauth_cookie = next(c for c in response.headers.get_list("set-cookie") if "oauth_tx=" in c)
    assert "httponly" in oauth_cookie.lower() and "samesite=lax" in oauth_cookie.lower()


@pytest.mark.parametrize("path", ["/auth/login", "/auth/callback?code=c&state=s"])
def test_auth_not_configured_redirects_to_login_page_not_json(path):
    # Regression: a browser navigation used to get a raw 503 JSON body.
    client = client_for(make_settings(google_client_id=""), None)

    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=login_unavailable"


class FakeGoogle:
    async def fetch_profile(self, request):
        return OAuthProfile("google", "g-1", "a@example.com", "Ann", None)


class BrokenUsers:
    def upsert_from_oauth(self, *args, **kwargs):
        raise RuntimeError("database is down")


def test_auth_callback_user_cancel_redirects_with_cancelled():
    client = client_for(make_settings(), FakeGoogle())

    response = client.get("/auth/callback?error=access_denied&state=s", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=cancelled"


def test_auth_callback_server_failure_redirects_without_json_or_cookie():
    container = Container(**{**NO_REPOS, "users": BrokenUsers()}, settings=make_settings(),
                          health_check=OkHealth(), oauth=FakeGoogle())  # fmt: skip
    client = TestClient(create_app(container), base_url="https://testserver")

    response = client.get("/auth/callback?code=c&state=s", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=server_error"
    assert not any("sid=" in c for c in response.headers.get_list("set-cookie"))


def test_cookie_name_and_redirect_uri_follow_settings():
    assert make_settings(cookie_secure=True).session_cookie_name == "__Host-sid"
    assert make_settings(cookie_secure=False).session_cookie_name == "sid"
    assert make_settings(app_origin="http://x/").oauth_redirect_uri == "http://x/auth/callback"


def test_production_refuses_to_start_without_secrets():
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_SECRET, SESSION_SECRET"):
        validate_settings(
            make_settings(app_env="production", google_client_secret="", session_secret="")
        )
    # The error names the missing settings but never echoes a value.
    with pytest.raises(RuntimeError) as exc:
        validate_settings(make_settings(app_env="production", session_secret=""))
    assert "cid.apps" not in str(exc.value) and "client-secret-value" not in str(exc.value)
    validate_settings(make_settings(app_env="production"))  # all set: ok
    validate_settings(make_settings(app_env="dev", google_client_id=""))  # dev: ok


def test_access_log_has_path_but_never_the_oauth_query(caplog):
    client = client_for(make_settings(google_client_id=""), None)
    # create_app() resets root handlers for JSON logging; re-attach pytest's capture handler.
    logging.getLogger().addHandler(caplog.handler)
    caplog.set_level(logging.INFO)

    client.get("/auth/callback?code=one-time-code-xyz&state=state-abc", follow_redirects=False)

    access = [r for r in caplog.records if r.name == "app.access"]
    assert access and access[-1].path == "/auth/callback" and access[-1].status == 303
    assert "one-time-code-xyz" not in caplog.text and "state-abc" not in caplog.text
