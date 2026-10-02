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
    # Uploads know these up front: the id names the blob before the row exists, and the
    # probe fields come from ffprobe. URL sources leave them None (DB generates the id).
    id: UUID | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sport: str = "football"  # T-085: validated by core.submit_rules
    title: str | None = None


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
    sport: str = "football"
    title: str | None = None
    thumbnail_key: str | None = None  # set by the worker (T-086)


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
class JobWithVideo:
    """A job and its video, read together (one JOIN) for the job list and detail (T-086)."""

    job: Job
    video: Video


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


@dataclass(frozen=True, slots=True)
class VideoProbe:
    """What ffprobe reports about a file's first video stream."""

    format_name: str
    duration_s: float
    width: int
    height: int
    fps: float | None
    rotation: int = 0  # display rotation in degrees; ffmpeg applies it when decoding


@dataclass(frozen=True, slots=True)
class FrameSize:
    """Size of the decoded BGR frames we stream (always even, so H.264 yuv420p accepts it)."""

    width: int
    height: int

    @property
    def frame_bytes(self) -> int:
        return self.width * self.height * 3


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """What yt-dlp reports about a remote video (no bytes downloaded yet)."""

    duration_s: float | None
    is_live: bool
    media_url: str | None  # single-stream URL; None if the format needs merging
    http_headers: dict[str, str]
    title: str | None = None


@dataclass(frozen=True, slots=True)
class Box:
    """Pixel box, top-left (x1, y1) to bottom-right (x2, y2)."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class Detection:
    box: Box
    score: float
    cls: str  # "player" | "ball"


@dataclass(frozen=True, slots=True)
class DetectorParams:
    input_size: int  # square model input, multiple of 32
    player_min_score: float  # = TRACKER_LOW_THRESH: weak boxes feed tracker stage 2 (D-021)
    ball_min_score: float
    nms_iou: float
    max_candidates: int = 300  # top-K player boxes kept before NMS (bounds CPU per frame)


@dataclass(frozen=True, slots=True)
class PipelineParams:
    """Worker knobs for one processing pass (from Settings via wiring.pipeline_params)."""

    sample_fps: float
    max_seconds: int
    max_frame_side: int
    heartbeat_every_frames: int  # lease heartbeat + progress update cadence
    team_sample_every: int  # take jersey-colour samples every N sampled frames
    team_max_samples: int  # per player; colour is a median, so a few are enough
    team_min_separation: float


@dataclass(frozen=True, slots=True)
class Track:
    """One tracked player. `public_id` is set on confirmation, so shown ids are 1..N."""

    internal_id: int
    public_id: int | None
    box: Box  # last matched box
    vx: float  # centre velocity, pixels per sampled frame
    vy: float
    hits: int
    misses: int  # sampled frames since the last match
    state: str  # "tentative" | "confirmed" | "lost"


@dataclass(frozen=True, slots=True)
class TrackerParams:
    high_thresh: float
    low_thresh: float
    match_iou: float
    low_match_iou: float
    max_age: int
    min_hits: int
    min_box_area_rel: float = 0.0


@dataclass(frozen=True, slots=True)
class TrackerState:
    tracks: tuple[Track, ...] = ()
    next_internal: int = 1
    next_public: int = 1


@dataclass(frozen=True, slots=True)
class FrameObservation:
    """What the pipeline saw in one sampled frame: the input to every metric."""

    frame_idx: int  # sampled-frame index (0, 1, 2, …)
    t_s: float  # video time in seconds
    tracks: tuple[Track, ...]  # confirmed tracks matched in this frame
    ball: Box | None = None


@dataclass(frozen=True, slots=True)
class MetricsParams:
    jitter_px: float
    max_gap_frames: int  # don't bridge distance across longer gaps (= tracker max age)
    heatmap_w: int
    heatmap_h: int
    possession_dist_ratio: float  # ball within ratio × player box height of the feet
    possession_min_frames: int


@dataclass(frozen=True, slots=True)
class MatchMetrics:
    """Output of core.metrics.build_stats: the stats JSON and one row per player."""

    stats: dict[str, Any]
    tracks: tuple[PlayerTrack, ...]
