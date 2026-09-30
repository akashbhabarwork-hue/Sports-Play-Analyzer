import os
from dataclasses import dataclass

APP_ENV = os.getenv("APP_ENV", "dev")
APP_ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app")
GIT_SHA = os.getenv("GIT_SHA", "unknown")

@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_origin: str
    database_url: str
    git_sha: str

def load_settings() -> Settings:
    return Settings(
        app_env=APP_ENV,
        app_origin=APP_ORIGIN,
        database_url=DATABASE_URL,
        git_sha=GIT_SHA,
    )
