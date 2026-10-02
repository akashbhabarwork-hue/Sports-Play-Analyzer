from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.config import Settings
from app.entrypoints.api import create_app
from app.errors import (
    AppError,
    CsrfRejectedError,
    ExternalServiceError,
    OAuthLoginError,
    ServiceUnavailableError,
    UnauthorizedError,
)
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


def make_app():
    settings = Settings(
        app_env="test", app_origin="https://app.example", database_url="x", git_sha="t"
    )
    return create_app(Container(**NO_REPOS, settings=settings, health_check=OkHealth()))


def test_every_api_route_requires_current_user():
    api_routes = [
        r for r in make_app().routes if isinstance(r, APIRoute) and r.path.startswith("/api")
    ]
    assert api_routes, "expected at least one /api route"
    for route in api_routes:
        names = {d.call.__name__ for d in route.dependant.dependencies}
        assert "current_user" in names, f"{route.path} is reachable without login"


def test_error_codes_are_stable_upper_snake():
    expected = {
        AppError: (400, "BAD_REQUEST"),
        UnauthorizedError: (401, "UNAUTHORIZED"),
        CsrfRejectedError: (403, "CSRF_REJECTED"),
        ExternalServiceError: (502, "EXTERNAL_SERVICE_ERROR"),
        ServiceUnavailableError: (503, "SERVICE_UNAVAILABLE"),
        OAuthLoginError: (400, "OAUTH_FAILED"),
    }
    for cls, (status, code) in expected.items():
        assert (cls.status_code, cls.code) == (status, code)


def test_foreign_origin_post_is_rejected_before_routing():
    client = TestClient(make_app(), base_url="https://testserver")

    response = client.post(
        "/auth/logout", headers={"Origin": "https://evil.example", "X-Requested-With": "fetch"}
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "CSRF_REJECTED", "message": "Request rejected: cross-site request"}
    }


def test_get_requests_are_not_affected_by_csrf_check():
    client = TestClient(make_app())
    assert client.get("/health", headers={"Origin": "https://evil.example"}).status_code == 200
