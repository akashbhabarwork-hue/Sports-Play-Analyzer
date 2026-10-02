"""T-091 at the API: security headers on every response, CORS off by default, one error
envelope (validation, unknown routes, crashes) and no path traversal through the SPA route."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.adapters.blob_local import LocalBlobStore
from app.config import Settings, validate_settings
from app.entrypoints.api import create_app
from tests.api_fakes import World, add_job, add_user, browser, make_container

CSRF = {"Origin": "http://localhost:8000", "X-Requested-With": "fetch"}


@pytest.fixture
def world(tmp_path):
    w = World()
    alice, token = add_user(w, "alice")
    blobs = LocalBlobStore(str(tmp_path / "b"))
    return w, alice, token, blobs


def app_with(world, **settings_changes):
    w, _, _, blobs = world
    container = make_container(w, blobs)
    return create_app(replace(container, settings=replace(container.settings, **settings_changes)))


def test_headers_on_health_spa_and_api(world, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<div id="root"></div>')
    client = browser(app_with(world, static_dir=str(dist)), world[2])
    for path in ("/health", "/", "/app/videos", "/api/me"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "default-src 'self'" in r.headers["content-security-policy"], path
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "strict-transport-security" not in r.headers  # not production


def test_headers_and_no_store_on_401_and_csrf_403(world):
    client = browser(app_with(world), None)
    r = client.get("/api/me")
    assert r.status_code == 401
    assert r.headers["cache-control"] == "no-store"
    assert "content-security-policy" in r.headers
    r = client.post("/api/jobs/url", json={"url": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and "content-security-policy" in r.headers


def test_headers_keep_route_cache_control_for_video(world):
    w, alice, token, blobs = world
    job = add_job(w, blobs, alice)
    r = browser(app_with(world), token).get(f"/api/jobs/{job.id}/video")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, max-age=300"  # not overwritten by no-store
    assert "content-security-policy" in r.headers


def test_headers_hsts_in_production(world):
    r = TestClient(app_with(world, app_env="production")).get("/health")
    assert r.headers["strict-transport-security"].startswith("max-age=31536000")


def test_headers_csp_allows_s3_media_origin(world):
    app = app_with(
        world, blob_backend="s3", s3_endpoint_url="https://acc.r2.example.com", s3_bucket="clips"
    )
    csp = TestClient(app).get("/health").headers["content-security-policy"]
    assert (
        "media-src 'self' blob: https://acc.r2.example.com https://clips.acc.r2.example.com" in csp
    )


def test_headers_cors_off_by_default(world):
    r = TestClient(app_with(world)).get("/health", headers={"Origin": "https://other.example"})
    assert "access-control-allow-origin" not in r.headers


def test_headers_cors_allows_only_configured_origin(world):
    client = TestClient(app_with(world, cors_origins=("https://partner.example",)))
    ok = client.get("/health", headers={"Origin": "https://partner.example"})
    assert ok.headers["access-control-allow-origin"] == "https://partner.example"
    assert ok.headers["access-control-allow-credentials"] == "true"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


@pytest.mark.parametrize("bad", ["*", "https://*.example.com", "partner.example"])
def test_headers_cors_wildcard_or_bare_host_refused_at_startup(bad):
    settings = Settings(app_env="test", app_origin="http://x", database_url="x", git_sha="t",
                        cors_origins=(bad,))  # fmt: skip
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_settings(settings)


def test_headers_validation_error_uses_envelope(world):
    client = browser(app_with(world), world[2])
    r = client.post("/api/jobs/url", headers=CSRF, json={})
    assert r.status_code == 422
    assert r.json() == {"error": {"code": "VALIDATION_ERROR", "message": "url: Field required"}}
    r = client.get("/api/jobs/not-a-uuid")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_headers_unknown_route_and_wrong_method_use_envelope(world):
    client = browser(app_with(world), world[2])
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    r = client.delete("/health", headers=CSRF)
    assert r.status_code == 405 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in r.headers["allow"]


def test_headers_crash_returns_generic_500_without_internals(world, capfd):
    w, _, token, blobs = world
    container = make_container(w, blobs)

    def boom(*_args, **_kwargs):
        raise RuntimeError("psycopg OperationalError at /srv/internal/db.py")

    container.jobs.list_with_videos = boom
    r = browser(create_app(container), token).get("/api/jobs")
    assert r.status_code == 500
    body = r.json()["error"]
    assert body["code"] == "INTERNAL" and body["message"].startswith("Something went wrong (ref ")
    assert "OperationalError" not in r.text and "/srv/" not in r.text and "Traceback" not in r.text
    assert "content-security-policy" in r.headers and r.headers["cache-control"] == "no-store"
    ref = body["message"].removeprefix("Something went wrong (ref ").removesuffix(").")
    logs = capfd.readouterr().err  # JSON logs go to stderr (app logger doesn't propagate)
    assert "unhandled error" in logs and f'"error_ref": "{ref}"' in logs  # same ref in log


def test_headers_spa_route_cannot_escape_dist_folder(world, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<div id="root"></div>')
    (dist / "vite.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")
    client = TestClient(app_with(world, static_dir=str(dist)))
    assert client.get("/vite.svg").text == "<svg/>"  # real dist files still served
    for path in ("/..%2fsecret.txt", "/%2e%2e/secret.txt", "/app/..%2f..%2fsecret.txt"):
        r = client.get(path)
        assert "TOP-SECRET" not in r.text, path
