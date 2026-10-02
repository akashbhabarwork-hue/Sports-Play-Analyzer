"""Protocols for everything external. Adapters satisfy these structurally (no inheritance).

Authorization rule (A3): every method that reads a user's videos, jobs or results takes
`user_id` and filters on it in SQL. Methods only the worker may call end in `_for_worker`.
`tests/unit/test_ports.py` enforces this. "Not found" and "not yours" both return None.
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import numpy as np

from .models import (
    Box,
    Detection,
    FrameSize,
    Job,
    JobOutcome,
    JobResult,
    JobWithVideo,
    MediaInfo,
    NewVideo,
    OAuthProfile,
    PlayerTrack,
    Track,
    User,
    Video,
    VideoProbe,
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

    def set_thumbnail_for_worker(self, video_id: UUID, thumbnail_key: str) -> None: ...


class JobRepo(Protocol):
    def create_with_video(
        self, user_id: UUID, new_video: NewVideo, config: dict[str, Any]
    ) -> Job: ...

    def get(self, user_id: UUID, job_id: UUID) -> Job | None: ...

    def list_for_user(self, user_id: UUID, limit: int = 50) -> list[Job]: ...

    def get_with_video(self, user_id: UUID, job_id: UUID) -> JobWithVideo | None: ...

    def list_with_videos(self, user_id: UUID, limit: int = 50) -> list[JobWithVideo]: ...

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


class BlobStore(Protocol):
    """Object storage for uploads and annotated videos (local disk or S3-compatible).

    Keys are validated with core.blob_keys.validate_blob_key. Missing keys raise
    BlobNotFoundError; backend failures raise ExternalServiceError.
    """

    def put_file(self, key: str, src_path: str, content_type: str) -> None:
        """Store a file atomically: readers never see a partial object."""
        ...

    def get_to_path(self, key: str, dest_path: str) -> None: ...

    def size(self, key: str) -> int: ...

    def open_range(self, key: str, start: int, end: int | None) -> Iterator[bytes]:
        """Bytes start..end inclusive (end None = to the last byte), in chunks."""
        ...

    def presigned_get_url(self, key: str, ttl_s: int) -> str | None:
        """Short-lived (≤ 5 min) download URL, or None if the API must stream it itself."""
        ...

    def delete(self, key: str) -> None:
        """Idempotent: deleting a missing key is not an error."""
        ...


class VideoProber(Protocol):
    def probe(self, path: str) -> VideoProbe:
        """Read container/stream metadata; raises CorruptFileError if unreadable."""
        ...


class FrameReader(Protocol):
    def frames(
        self, path: str, size: FrameSize, sample_fps: float, max_seconds: int
    ) -> Iterator[np.ndarray]:
        """Yield read-only HxWx3 BGR frames one at a time; raises DecodeError if none decode."""
        ...


class VideoEncoder(Protocol):
    def encode(
        self, frames: Iterable[np.ndarray], out_path: str, size: FrameSize, fps: float
    ) -> int:
        """Write browser-playable H.264 MP4 from the frames as they arrive; returns the count."""
        ...


class FrameAnnotator(Protocol):
    def draw(
        self,
        frame_bgr: np.ndarray,
        tracks: Sequence[Track],
        ball: Box | None,
        t_s: float,
        teams: Mapping[int, str],
    ) -> np.ndarray:
        """Return a copy of the frame with boxes coloured by team (public id → "A"/"B"/
        "unknown"), ids, the ball, a time stamp and a legend of what is drawn."""
        ...

    def thumbnail_jpeg(self, frame_bgr: np.ndarray, max_width: int) -> bytes:
        """A small JPEG of the frame for lists and the processing page (T-086)."""
        ...


class Detector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        """Players (down to the tracker's low threshold) + at most one ball, in frame pixels.
        Raises ModelError if inference fails."""
        ...


class MediaInfoFetcher(Protocol):
    def fetch_info(self, url: str) -> MediaInfo:
        """Metadata for a canonical YouTube URL; raises YouTubeBlockedError/DownloadFailedError."""
        ...


class MediaDownloader(Protocol):
    def download(self, url: str, headers: dict[str, str], dest_path: str, max_bytes: int) -> int:
        """SSRF-guarded download to dest_path; returns bytes written."""
        ...
