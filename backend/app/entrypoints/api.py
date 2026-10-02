import logging
import os
import secrets
import tempfile
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Form, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from ..config import Settings, load_settings
from ..core.http_range import parse_range
from ..core.models import JobWithVideo, User
from ..errors import (
    AppError,
    CsrfRejectedError,
    OAuthLoginError,
    RangeNotSatisfiableError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from ..services.auth import login_user, logout, user_for_token
from ..services.read_job import (
    PlayerView,
    VideoAccess,
    get_heatmap,
    get_job,
    get_player,
    get_stats,
    get_thumbnail,
    get_video,
    list_jobs,
)
from ..services.submit import (
    UploadLimits,
    check_submit_allowed,
    submit_upload_job,
    submit_url_job,
)
from ..wiring import Container, build_container
from .csrf import is_request_trusted
from .limits import BodySizeLimitMiddleware, copy_capped
from .log_config import setup_logging
from .schemas import (
    Heatmap,
    JobAccepted,
    JobDetail,
    JobList,
    MeResponse,
    PlayerDetail,
    StatsResponse,
    UrlSubmit,
    VideoInfo,
)

access_logger = logging.getLogger("app.access")

UPLOAD_PATHS = frozenset({"/api/jobs/upload", "/jobs/upload"})  # canonical + D-004 alias

OAUTH_TX_COOKIE = "oauth_tx"
OAUTH_TX_MAX_AGE = 600  # state/nonce/PKCE verifier only live for the login round trip
LOGIN_FAILED_URL = "/login?error=oauth_failed"


def error_response(exc: AppError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )
    retry_after = getattr(exc, "retry_after", None)
    if retry_after:  # 429 RATE_LIMITED (T-090)
        response.headers["Retry-After"] = str(retry_after)
    return response


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
        paths=UPLOAD_PATHS,
        max_file_bytes=settings.max_upload_bytes,
    )

    frontend_dir = container.settings.static_dir
    if frontend_dir and os.path.exists(frontend_dir):
        assets_dir = os.path.join(frontend_dir, "assets")
        if os.path.exists(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            # /jobs… are API aliases (D-004); the SPA's own pages live under /app/… (D-028).
            if full_path.startswith(("api/", "auth/", "jobs/")) or full_path in ("health", "jobs"):
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


def job_summary(item: JobWithVideo) -> dict:
    job, v = item.job, item.video
    error = {"code": job.error_code, "message": job.error_message} if job.error_code else None
    return {
        "id": job.id,
        "title": v.title,
        "sport": v.sport,
        "source_type": v.source_type,
        "original_filename": v.original_filename,
        "source_url": v.source_url,
        "duration_s": v.duration_s,
        "size_bytes": v.size_bytes,
        "thumbnail_url": f"/api/jobs/{job.id}/thumbnail" if v.thumbnail_key else None,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "error": error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def job_detail(item: JobWithVideo) -> JobDetail:
    v = item.video
    video = VideoInfo(
        source_type=v.source_type,
        original_filename=v.original_filename,
        source_url=v.source_url,
        duration_s=v.duration_s,
    )
    return JobDetail(
        **job_summary(item),
        started_at=item.job.started_at,
        attempts=item.job.attempts,
        video=video,
    )


def blob_response(container: Container, access: VideoAccess, media_type: str):
    """Small blobs (thumbnails): 302 to a short-lived storage URL, or stream them whole."""
    if access.url is not None:
        return RedirectResponse(access.url, status_code=302, headers={"Cache-Control": "no-store"})
    body = container.blobs.open_range(access.key, 0, None)
    headers = {"Cache-Control": "private, max-age=3600", "Content-Length": str(access.size)}
    return StreamingResponse(body, media_type=media_type, headers=headers)


def player_detail(view: PlayerView) -> PlayerDetail:
    t = view.track
    return PlayerDetail(
        player_id=t.track_id,
        team=t.team,
        distance_px=t.distance_px,
        distance_rel=t.distance_rel,
        frames_visible=t.frames_visible,
        possession_pct=view.possession_pct,
        track=t.track,
        heatmap=Heatmap(**t.heatmap),
    )


def video_response(container: Container, access: VideoAccess, range_header: str | None):
    """302 to a short-lived storage URL (S3), or stream it ourselves with Range support so
    the browser's <video> can seek without downloading the whole file."""
    if access.url is not None:
        return RedirectResponse(access.url, status_code=302, headers={"Cache-Control": "no-store"})
    try:
        byte_range = parse_range(range_header, access.size)
    except RangeNotSatisfiableError as e:
        response = error_response(e)
        response.headers["Content-Range"] = f"bytes */{access.size}"
        return response
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=300"}
    if byte_range is None:
        start, end, status = 0, access.size - 1, 200
    else:
        (start, end), status = byte_range, 206
        headers["Content-Range"] = f"bytes {start}-{end}/{access.size}"
    headers["Content-Length"] = str(end - start + 1)
    body = container.blobs.open_range(access.key, start, end)
    return StreamingResponse(body, status_code=status, media_type="video/mp4", headers=headers)


def register_api_routes(app: FastAPI, container: Container) -> None:
    current_user = make_current_user(container)
    # Every /api route hangs off this router, so none can skip authentication;
    # tests/unit/test_api_routes.py fails if an /api route lacks the dependency.
    api = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
    # Job routes live on their own router, mounted at /api/jobs… (canonical) and at /jobs…
    # (aliases matching the brief's curl examples, D-004). Same handlers, same auth.
    jobs = APIRouter(dependencies=[Depends(current_user)])

    @api.get("/me", response_model=MeResponse)
    def me(user: User = Depends(current_user)) -> MeResponse:
        return MeResponse(id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url)

    limits = UploadLimits(
        max_bytes=container.settings.max_upload_bytes,
        max_duration_s=container.settings.max_video_seconds,
    )
    tmp_root = container.settings.upload_tmp_dir or None

    def allow_submit(user: User) -> None:
        # T-090: rate limit + active-job cap before any work. (For uploads FastAPI has already
        # received the ≤100 MB body by now; nothing is validated or stored when refused.)
        check_submit_allowed(
            container.rate_limiter,
            container.jobs,
            user.id,
            container.settings.max_active_jobs_per_user,
        )

    @jobs.post("/jobs/upload", status_code=202, response_model=JobAccepted)
    def upload_video(
        file: UploadFile,
        sport: str | None = Form(default=None, max_length=32),
        title: str | None = Form(default=None, max_length=1000),
        user: User = Depends(current_user),
    ) -> JobAccepted:
        allow_submit(user)
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
                sport=sport,
                title=title,
            )
        return JobAccepted(job_id=job.id, status=job.status)

    @jobs.post("/jobs/url", status_code=202, response_model=JobAccepted)
    def submit_url(body: UrlSubmit, user: User = Depends(current_user)) -> JobAccepted:
        allow_submit(user)
        job = submit_url_job(
            container.jobs,
            user.id,
            body.url,
            {"max_video_seconds": limits.max_duration_s},
            sport=body.sport,
            title=body.title,
        )
        return JobAccepted(job_id=job.id, status=job.status)

    # ---- reads (T-070): all scoped to the session user; foreign or missing ids → 404 ----

    @jobs.get("/jobs", response_model=JobList)
    def jobs_list(user: User = Depends(current_user)) -> JobList:
        return JobList(jobs=[job_summary(j) for j in list_jobs(container.jobs, user.id)])

    @jobs.get("/jobs/{job_id}", response_model=JobDetail)
    def job_get(job_id: UUID, user: User = Depends(current_user)) -> JobDetail:
        return job_detail(get_job(container.jobs, user.id, job_id))

    @jobs.get("/jobs/{job_id}/thumbnail")
    def job_thumbnail(job_id: UUID, user: User = Depends(current_user)):
        access = get_thumbnail(container.jobs, container.blobs, user.id, job_id)
        return blob_response(container, access, "image/jpeg")

    @jobs.get("/jobs/{job_id}/stats")
    def job_stats(job_id: UUID, user: User = Depends(current_user)) -> StatsResponse:
        return get_stats(container.jobs, container.results, user.id, job_id)

    @jobs.get("/jobs/{job_id}/players/{player_id}", response_model=PlayerDetail)
    def job_player(job_id: UUID, player_id: int, user: User = Depends(current_user)):
        view = get_player(container.jobs, container.results, user.id, job_id, player_id)
        return player_detail(view)

    @jobs.get("/jobs/{job_id}/heatmap", response_model=Heatmap)
    def job_heatmap(
        job_id: UUID,
        team: Literal["all", "A", "B"] = "all",
        user: User = Depends(current_user),
    ):
        return get_heatmap(container.jobs, container.results, user.id, job_id, team)

    @jobs.get("/jobs/{job_id}/video")
    def job_video(job_id: UUID, request: Request, user: User = Depends(current_user)):
        access = get_video(container.jobs, container.results, container.blobs, user.id, job_id)
        return video_response(container, access, request.headers.get("range"))

    api.include_router(jobs)
    app.include_router(api)
    app.include_router(jobs, include_in_schema=False)  # /jobs… aliases (D-004)
