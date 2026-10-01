from dataclasses import dataclass

from .adapters.db import PostgresHealthCheck, create_db_engine
from .adapters.oauth_google import GoogleOAuthClient
from .adapters.pg_queue import PostgresJobQueue
from .adapters.pg_repos import (
    PostgresJobRepo,
    PostgresResultRepo,
    PostgresSessionRepo,
    PostgresUserRepo,
    PostgresVideoRepo,
)
from .config import Settings
from .core.ports import (
    HealthCheck,
    JobQueue,
    JobRepo,
    OAuthProvider,
    ResultRepo,
    SessionRepo,
    UserRepo,
    VideoRepo,
)


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    health_check: HealthCheck
    users: UserRepo
    sessions: SessionRepo
    videos: VideoRepo
    jobs: JobRepo
    results: ResultRepo
    queue: JobQueue
    # None when Google login is not configured (local dev without credentials).
    oauth: OAuthProvider | None = None


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings.database_url)
    return Container(
        settings=settings,
        health_check=PostgresHealthCheck(engine),
        users=PostgresUserRepo(engine),
        sessions=PostgresSessionRepo(engine),
        videos=PostgresVideoRepo(engine),
        jobs=PostgresJobRepo(engine),
        results=PostgresResultRepo(engine),
        queue=PostgresJobQueue(engine),
        oauth=(
            GoogleOAuthClient(settings.google_client_id, settings.google_client_secret)
            if settings.oauth_configured
            else None
        ),
    )
