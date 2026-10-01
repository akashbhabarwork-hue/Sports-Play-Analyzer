"""Domain dataclasses returned by the repositories. Pure data, no I/O."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    provider: str
    provider_sub: str
    email: str | None
    name: str | None
    avatar_url: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewVideo:
    """What a submit request knows about a video before the worker has probed it."""

    source_type: str  # "upload" | "url"
    source_url: str | None = None
    original_filename: str | None = None
    storage_key: str | None = None  # set for uploads; url sources get one when fetched
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class Video:
    id: UUID
    user_id: UUID
    source_type: str
    source_url: str | None
    original_filename: str | None
    storage_key: str | None
    size_bytes: int | None
    duration_s: float | None
    width: int | None
    height: int | None
    fps: float | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Job:
    id: UUID
    user_id: UUID
    video_id: UUID
    status: str
    progress: int
    stage: str | None
    error_code: str | None
    error_message: str | None
    attempts: int
    max_attempts: int
    config: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class JobResult:
    job_id: UUID
    stats: dict[str, Any]
    annotated_key: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PlayerTrack:
    job_id: UUID
    track_id: int
    team: str | None
    frames_visible: int
    distance_px: float
    distance_rel: float
    possession_frames: int
    heatmap: dict[str, Any]
    track: list[list[float]]


@dataclass(frozen=True, slots=True)
class JobOutcome:
    """Everything a successful run persists. Track rows' `job_id` is ignored on write."""

    stats: dict[str, Any]
    annotated_key: str
    tracks: tuple[PlayerTrack, ...] = ()


@dataclass(frozen=True, slots=True)
class OAuthProfile:
    """Verified identity returned by an OAuth provider after a successful login."""

    provider: str
    sub: str
    email: str | None
    name: str | None
    avatar_url: str | None
