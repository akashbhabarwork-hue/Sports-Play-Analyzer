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

    @property
    def oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers require Secure, Path=/ and no Domain.
        return "__Host-sid" if self.cookie_secure else "sid"

    @property
    def oauth_redirect_uri(self) -> str:
        # Built from config, never from request headers, so a proxy cannot spoof it.
        return f"{self.app_origin.rstrip('/')}/auth/callback"


def validate_settings(settings: Settings) -> None:
    if settings.app_env != "production":
        return
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
    )
    validate_settings(settings)
    return settings
