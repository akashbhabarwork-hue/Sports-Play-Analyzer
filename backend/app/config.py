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


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_origin: str
    database_url: str
    git_sha: str
    static_dir: str = ""
    lease_seconds: int = 60
    worker_id: str = "worker"


def load_settings() -> Settings:
    return Settings(
        app_env=APP_ENV,
        app_origin=APP_ORIGIN,
        database_url=DATABASE_URL,
        git_sha=GIT_SHA,
        static_dir=STATIC_DIR,
        lease_seconds=LEASE_SECONDS,
        worker_id=WORKER_ID,
    )
