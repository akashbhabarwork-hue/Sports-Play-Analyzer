"""HTTP response/request models. Pydantic lives only here (the boundary)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MeResponse(BaseModel):
    id: UUID
    email: str | None
    name: str | None
    avatar_url: str | None


class JobAccepted(BaseModel):
    job_id: UUID
    status: str


class UrlSubmit(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class JobError(BaseModel):
    code: str
    message: str | None


class JobSummary(BaseModel):
    id: UUID
    status: str  # queued | processing | succeeded | failed
    progress: int  # 0-100; 100 only once succeeded
    stage: str | None  # fetching | analysing | saving while processing
    error: JobError | None
    created_at: datetime
    finished_at: datetime | None


class JobList(BaseModel):
    jobs: list[JobSummary]


class VideoInfo(BaseModel):
    source_type: str  # upload | url
    original_filename: str | None
    source_url: str | None
    duration_s: float | None


class JobDetail(BaseModel):
    """JobSummary's fields plus run details (spelled out: schemas don't inherit, rule 10)."""

    id: UUID
    status: str
    progress: int
    stage: str | None
    error: JobError | None
    created_at: datetime
    finished_at: datetime | None
    started_at: datetime | None
    attempts: int
    video: VideoInfo | None


class Heatmap(BaseModel):
    w: int
    h: int
    counts: list[int]  # row-major, h rows of w cells
    max: int


class PlayerDetail(BaseModel):
    player_id: int
    team: str | None
    distance_px: float
    distance_rel: float
    frames_visible: int
    possession_pct: float
    track: list[list[float]]  # [t_s, nx, ny] feet positions, normalised to the frame
    heatmap: Heatmap


# Stats are returned exactly as stored (sports-metrics contract); documented, not re-modelled.
StatsResponse = dict[str, Any]
