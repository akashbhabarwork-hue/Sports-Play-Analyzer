import logging
import os
import secrets
import tempfile
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, FastAPI, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger
from starlette.middleware.sessions import SessionMiddleware

from ..config import Settings, load_settings
from ..core.models import User
from ..errors import (
    AppError,
    CsrfRejectedError,
    OAuthLoginError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from ..services.auth import login_user, logout, user_for_token
from ..services.submit import UploadLimits, submit_upload_job
from ..wiring import Container, build_container
from .csrf import is_request_trusted
from .limits import BodySizeLimitMiddleware, copy_capped
from .schemas import JobAccepted, MeResponse

access_logger = logging.getLogger("app.access")

UPLOAD_PATH = "/api/jobs/upload"

OAUTH_TX_COOKIE = "oauth_tx"
OAUTH_TX_MAX_AGE = 600  # state/nonce/PKCE verifier only live for the login round trip
LOGIN_FAILED_URL = "/login?error=oauth_failed"


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # HTTP client libraries log full request URLs at INFO; keep them quiet so URLs with
    # tokens or OAuth parameters never reach the logs.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


def create_app(container: Container | None = None) -> FastAPI:
    setup_logging()

    if container is None:
        container = build_container(load_settings())

    app = FastAPI(title="Sports Play Analyzer")
    settings = container.settings
    # Transient, signed cookie used ONLY to carry Authlib's OAuth transaction (state, nonce,
    # PKCE verifier) across the Google redirect. Our login session is the separate sid cookie.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret or secrets.token_urlsafe(32),
        session_cookie=OAUTH_TX_COOKIE,
        max_age=OAUTH_TX_MAX_AGE,
        same_site="lax",
        https_only=settings.cookie_secure,
    )

    # CSRF defence in depth on top of SameSite=Lax: unsafe methods must send
    # X-Requested-With: fetch and come from a trusted Origin (entrypoints/csrf.py).
    # Exceptions raised in middleware skip the exception handlers, so the envelope is
    # returned directly.
    trusted_origins = settings.csrf_trusted_origins

    @app.middleware("http")
    async def reject_cross_site_writes(request: Request, call_next):
        headers = request.headers
        if not is_request_trusted(
            request.method,
            headers.get("origin"),
            headers.get("referer"),
            headers.get("x-requested-with"),
            trusted_origins,
        ):
            access_logger.warning(
                "csrf rejected", extra={"method": request.method, "path": request.url.path}
            )
            return error_response(CsrfRejectedError("Request rejected: cross-site request"))
        return await call_next(request)

    # Our access log replaces uvicorn's (run with --no-access-log): uvicorn logs full query
    # strings, which would leak OAuth `code`/`state` from /auth/callback. Path only here.
    # Middleware must be async in FastAPI (documented exception, rule 10).
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(exc)

    @app.get("/health")
    def health():
        db_ok = container.health_check.check_db()
        status_code = 200 if db_ok else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if db_ok else "error",
                "db": "ok" if db_ok else "error",
                "version": container.settings.git_sha,
            },
        )

    register_auth_routes(app, container)
    register_api_routes(app, container)
    # Added last = outermost user middleware: it sees the raw body before any parsing.
    app.add_middleware(
        BodySizeLimitMiddleware,
        paths=frozenset({UPLOAD_PATH}),
        max_file_bytes=settings.max_upload_bytes,
    )

    frontend_dir = container.settings.static_dir
    if frontend_dir and os.path.exists(frontend_dir):
        assets_dir = os.path.join(frontend_dir, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path.startswith(("api/", "auth/")) or full_path == "health":
                return JSONResponse(status_code=404, content={"detail": "Not Found"})

            # Serve specific files in dist root (like vite.svg, etc) if they exist
            requested_file = os.path.join(frontend_dir, full_path)
            if os.path.isfile(requested_file):
                return FileResponse(requested_file)

            return FileResponse(os.path.join(frontend_dir, "index.html"))

    return app


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 24 * 3600,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # Strict would drop the cookie on the redirect back from Google
    )


def register_auth_routes(app: FastAPI, container: Container) -> None:
    settings = container.settings

    # The two OAuth routes are async because Authlib's Starlette client is async (D-015).
    # They stay thin: Authlib call, then the sync service via run_in_threadpool.
    @app.get("/auth/login", include_in_schema=False)
    async def auth_login(request: Request):
        if container.oauth is None:
            raise ServiceUnavailableError("Google login is not configured on this server")
        return await container.oauth.authorize_redirect(request, settings.oauth_redirect_uri)

    @app.get("/auth/callback", include_in_schema=False)
    async def auth_callback(request: Request):
        if container.oauth is None:
            raise ServiceUnavailableError("Google login is not configured on this server")
        try:
            profile = await container.oauth.fetch_profile(request)
        except OAuthLoginError:
            return RedirectResponse(LOGIN_FAILED_URL, status_code=303)
        finally:
            request.session.clear()  # the OAuth transaction is single-use

        _, token = await run_in_threadpool(
            login_user,
            container.users,
            container.sessions,
            profile,
            datetime.now(UTC),
            settings.session_ttl_days,
            request.cookies.get(settings.session_cookie_name),
        )
        response = RedirectResponse("/", status_code=303)
        set_session_cookie(response, settings, token)
        return response

    # POST, not GET: a cross-site <img> must not be able to log users out.
    @app.post("/auth/logout", status_code=204, include_in_schema=False)
    def auth_logout(request: Request):
        logout(container.sessions, request.cookies.get(settings.session_cookie_name))
        response = Response(status_code=204)
        response.delete_cookie(
            settings.session_cookie_name,
            path="/",
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
        )
        return response


def make_current_user(container: Container):
    """FastAPI dependency: the logged-in User, or 401 for a missing/unknown/expired session."""
    cookie_name = container.settings.session_cookie_name

    def current_user(request: Request) -> User:
        user = user_for_token(container.sessions, request.cookies.get(cookie_name))
        if user is None:
            raise UnauthorizedError("Please log in")
        return user

    return current_user


def register_api_routes(app: FastAPI, container: Container) -> None:
    current_user = make_current_user(container)
    # Every /api route hangs off this router, so none can skip authentication;
    # tests/unit/test_api_routes.py fails if an /api route lacks the dependency.
    api = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

    @api.get("/me", response_model=MeResponse)
    def me(user: User = Depends(current_user)) -> MeResponse:
        return MeResponse(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url)

    limits = UploadLimits(
        max_bytes=container.settings.max_upload_bytes,
        max_duration_s=container.settings.max_video_seconds,
    )
    tmp_root = container.settings.upload_tmp_dir or None

    @api.post("/jobs/upload", status_code=202, response_model=JobAccepted)
    def upload_video(file: UploadFile, user: User = Depends(current_user)) -> JobAccepted:
        # Per-request temp dir, removed in every outcome (success, 4xx, crash).
        with tempfile.TemporaryDirectory(dir=tmp_root, prefix="upload-") as tmp:
            path = os.path.join(tmp, "source")
            copy_capped(file.file, path, limits.max_bytes)
            job = submit_upload_job(
                container.jobs,
                container.blobs,
                container.prober,
                user.id,
                path,
                file.filename,
                limits,
                {"max_video_seconds": limits.max_duration_s},
            )
        return JobAccepted(job_id=job.id, status=job.status)

    app.include_router(api)
