"""Protocols for everything external. Adapters satisfy these structurally (no inheritance).

Authorization rule (A3): every method that reads a user's videos, jobs or results takes
`user_id` and filters on it in SQL. Methods only the worker may call end in `_for_worker`.
`tests/unit/test_ports.py` enforces this. "Not found" and "not yours" both return None.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from .models import (
    Job,
    JobOutcome,
    JobResult,
    NewVideo,
    OAuthProfile,
    PlayerTrack,
    User,
    Video,
)


class HealthCheck(Protocol):
    def check_db(self) -> bool: ...


class UserRepo(Protocol):
    def upsert_from_oauth(
        self,
        provider: str,
        provider_sub: str,
        email: str | None,
        name: str | None,
        avatar_url: str | None,
    ) -> User: ...

    def get(self, user_id: UUID) -> User | None: ...


class SessionRepo(Protocol):
    def create(self, token_hash: bytes, user_id: UUID, expires_at: datetime) -> None: ...

    def get_user_by_token(self, token_hash: bytes) -> User | None: ...

    def delete(self, token_hash: bytes) -> None: ...

    def delete_all_for_user(self, user_id: UUID) -> int: ...

    def delete_expired(self) -> int: ...


class VideoRepo(Protocol):
    def get(self, user_id: UUID, video_id: UUID) -> Video | None: ...

    def get_for_worker(self, video_id: UUID) -> Video | None: ...

    def set_media_for_worker(
        self,
        video_id: UUID,
        storage_key: str,
        size_bytes: int,
        duration_s: float,
        width: int,
        height: int,
        fps: float,
    ) -> None: ...


class JobRepo(Protocol):
    def create_with_video(
        self, user_id: UUID, new_video: NewVideo, config: dict[str, Any]
    ) -> Job: ...

    def get(self, user_id: UUID, job_id: UUID) -> Job | None: ...

    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[Job]: ...

    def get_for_worker(self, job_id: UUID) -> Job | None: ...


class ResultRepo(Protocol):
    def get(self, user_id: UUID, job_id: UUID) -> JobResult | None: ...

    def list_tracks(self, user_id: UUID, job_id: UUID) -> list[PlayerTrack]: ...

    def get_track(self, user_id: UUID, job_id: UUID, track_id: int) -> PlayerTrack | None: ...


class JobQueue(Protocol):
    """Worker-only queue operations. Never wired into an HTTP route.

    Every write after `claim` is guarded by `locked_by = worker_id AND status = 'processing'`;
    a `False` return means this worker lost its lease and must stop without writing results.
    """

    def claim(self, worker_id: str, lease_s: int) -> Job | None: ...

    def heartbeat(
        self, job_id: UUID, worker_id: str, progress: int, stage: str, lease_s: int
    ) -> bool: ...

    def finish(self, job_id: UUID, worker_id: str, outcome: JobOutcome) -> bool: ...

    def fail(self, job_id: UUID, worker_id: str, error_code: str, message: str) -> bool: ...

    def sweep_dead(self) -> int: ...


class OAuthProvider(Protocol):
    """Login provider (Authorization Code + PKCE). Async because Authlib's Starlette client is;
    only the two /auth routes call it (D-015). `request` is the framework request object."""

    async def authorize_redirect(self, request: Any, redirect_uri: str) -> Any: ...

    async def fetch_profile(self, request: Any) -> OAuthProfile: ...
