import os
import socket
from dataclasses import dataclass

APP_ENV = os.getenv("APP_ENV", "dev")
APP_ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app")
GIT_SHA = os.getenv("GIT_SHA", "unknown")
# Built SPA directory served by FastAPI; the Docker image sets this to /app/backend/static
STATIC_DIR = os.getenv(
    "STATIC_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist")),
)

# ---- job queue ----
# A claimed job is held for LEASE_SECONDS; the worker's heartbeat extends it. If the worker
# dies, the lease lapses and another worker reclaims the job (up to jobs.max_attempts).
LEASE_SECONDS = int(os.getenv("LEASE_SECONDS", "60"))
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")

# ---- auth ----
# Secrets have no usable default: in production load_settings() refuses to start without
# them; in dev, /auth/login answers "not configured" instead. Real values live only in .env
# or host secrets.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "7"))
# Extra origins allowed to send unsafe requests (CSRF check), comma-separated. APP_ORIGIN is
# always trusted; local dev adds the Vite server, e.g. http://localhost:5173.
TRUSTED_ORIGINS = tuple(o.strip() for o in os.getenv("TRUSTED_ORIGINS", "").split(",") if o.strip())

# ---- storage ----
# local: a directory (compose volume / dev). s3: Tigris, R2 or AWS — required in production
# because web and worker run on different machines and cannot share a disk.
BLOB_BACKEND = os.getenv("BLOB_BACKEND", "local")
BLOB_LOCAL_DIR = os.getenv(
    "BLOB_LOCAL_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../blobs"))
)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
BLOB_BACKENDS = ("local", "s3")

# ---- ingestion limits ----
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024)))
MAX_VIDEO_DURATION_SECONDS = int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "60"))
# Per-request temp dirs for uploads live here (default: the system temp dir).
UPLOAD_TMP_DIR = os.getenv("UPLOAD_TMP_DIR", "")

# ---- YouTube fetch (optional mitigations for datacenter blocking, D-010) ----
# Base64 of a Netscape cookies.txt from a throwaway account; written to a 0600 temp file
# per fetch and deleted afterwards. Proxy URL is used for both yt-dlp and the download.
# Secrets: never logged, never committed.
YTDLP_COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64", "")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

REQUIRED_IN_PRODUCTION = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET")


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_origin: str
    database_url: str
    git_sha: str
    static_dir: str = ""
    lease_seconds: int = 60
    worker_id: str = "worker"
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    cookie_secure: bool = True
    session_ttl_days: int = 7
    trusted_origins: tuple[str, ...] = ()
    blob_backend: str = "local"
    blob_local_dir: str = ""
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    max_upload_bytes: int = 100 * 1024 * 1024
    max_video_seconds: int = 60
    upload_tmp_dir: str = ""
    ytdlp_cookies_b64: str = ""
    ytdlp_proxy: str = ""

    @property
    def oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers require Secure, Path=/ and no Domain.
        return "__Host-sid" if self.cookie_secure else "sid"

    @property
    def csrf_trusted_origins(self) -> frozenset[str]:
        origins = (self.app_origin, *self.trusted_origins)
        return frozenset(o.rstrip("/").lower() for o in origins if o)

    @property
    def oauth_redirect_uri(self) -> str:
        # Built from config, never from request headers, so a proxy cannot spoof it.
        return f"{self.app_origin.rstrip('/')}/auth/callback"


def validate_settings(settings: Settings) -> None:
    """Fail fast on bad config. Messages name settings, never their values."""
    if settings.blob_backend not in BLOB_BACKENDS:
        raise RuntimeError(f"BLOB_BACKEND must be one of: {', '.join(BLOB_BACKENDS)}")
    s3_values = {
        "S3_BUCKET": settings.s3_bucket,
        "S3_ACCESS_KEY_ID": settings.s3_access_key_id,
        "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
    }
    if settings.blob_backend == "s3":
        missing_s3 = [name for name, value in s3_values.items() if not value]
        if missing_s3:
            raise RuntimeError(
                f"Missing required settings for BLOB_BACKEND=s3: {', '.join(missing_s3)}"
            )
    if settings.app_env != "production":
        return
    if settings.blob_backend != "s3":
        raise RuntimeError("BLOB_BACKEND must be s3 in production (web and worker share no disk)")
    values = {
        "GOOGLE_CLIENT_ID": settings.google_client_id,
        "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
        "SESSION_SECRET": settings.session_secret,
    }
    missing = [name for name in REQUIRED_IN_PRODUCTION if not values[name]]
    if missing:
        raise RuntimeError(f"Missing required settings in production: {', '.join(missing)}")


def load_settings() -> Settings:
    settings = Settings(
        app_env=APP_ENV,
        app_origin=APP_ORIGIN,
        database_url=DATABASE_URL,
        git_sha=GIT_SHA,
        static_dir=STATIC_DIR,
        lease_seconds=LEASE_SECONDS,
        worker_id=WORKER_ID,
        google_client_id=GOOGLE_CLIENT_ID,
        google_client_secret=GOOGLE_CLIENT_SECRET,
        session_secret=SESSION_SECRET,
        cookie_secure=COOKIE_SECURE,
        session_ttl_days=SESSION_TTL_DAYS,
        trusted_origins=TRUSTED_ORIGINS,
        blob_backend=BLOB_BACKEND,
        blob_local_dir=BLOB_LOCAL_DIR,
        s3_endpoint_url=S3_ENDPOINT_URL,
        s3_bucket=S3_BUCKET,
        s3_region=S3_REGION,
        s3_access_key_id=S3_ACCESS_KEY_ID,
        s3_secret_access_key=S3_SECRET_ACCESS_KEY,
        max_upload_bytes=MAX_UPLOAD_SIZE_BYTES,
        max_video_seconds=MAX_VIDEO_DURATION_SECONDS,
        upload_tmp_dir=UPLOAD_TMP_DIR,
        ytdlp_cookies_b64=YTDLP_COOKIES_B64,
        ytdlp_proxy=YTDLP_PROXY,
    )
    validate_settings(settings)
    return settings
