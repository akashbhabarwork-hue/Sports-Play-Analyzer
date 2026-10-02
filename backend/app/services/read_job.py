"""Read use cases for the job API (T-070). Every function is scoped to `user_id`.

Order is always: find the job *as this user* (missing or someone else's → NotFoundError, so a
stranger can't even learn the id exists) → check it has succeeded (JobNotReadyError) → read.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ..core.blob_keys import PRESIGNED_URL_MAX_TTL_S
from ..core.models import Job, JobResult, PlayerTrack, Video
from ..core.ports import BlobStore, JobRepo, ResultRepo, VideoRepo
from ..errors import JobNotReadyError, NotFoundError

JOB_LIST_LIMIT = 50
NOT_FOUND_MESSAGE = "Job not found"
SUCCEEDED = "succeeded"


@dataclass(frozen=True, slots=True)
class JobView:
    job: Job
    video: Video | None


@dataclass(frozen=True, slots=True)
class PlayerView:
    track: PlayerTrack
    possession_pct: float


@dataclass(frozen=True, slots=True)
class VideoAccess:
    """Either a short-lived URL to redirect to, or a blob the API streams itself."""

    url: str | None = None
    key: str | None = None
    size: int = 0


def list_jobs(jobs: JobRepo, user_id: UUID) -> list[Job]:
    return jobs.list_for_user(user_id, JOB_LIST_LIMIT)


def _own_job(jobs: JobRepo, user_id: UUID, job_id: UUID) -> Job:
    job = jobs.get(user_id, job_id)
    if job is None:
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return job


def get_job(jobs: JobRepo, videos: VideoRepo, user_id: UUID, job_id: UUID) -> JobView:
    job = _own_job(jobs, user_id, job_id)
    return JobView(job=job, video=videos.get(user_id, job.video_id))


def _result(jobs: JobRepo, results: ResultRepo, user_id: UUID, job_id: UUID) -> JobResult:
    job = _own_job(jobs, user_id, job_id)
    if job.status != SUCCEEDED:
        raise JobNotReadyError(f"Results are not ready yet (job is {job.status}).")
    result = results.get(user_id, job_id)
    if result is None:  # succeeded rows always have results; treat a gap as not found
        raise NotFoundError(NOT_FOUND_MESSAGE)
    return result


def get_stats(jobs: JobRepo, results: ResultRepo, user_id: UUID, job_id: UUID) -> dict[str, Any]:
    return _result(jobs, results, user_id, job_id).stats


def get_player(
    jobs: JobRepo, results: ResultRepo, user_id: UUID, job_id: UUID, player_id: int
) -> PlayerView:
    stats = _result(jobs, results, user_id, job_id).stats
    track = results.get_track(user_id, job_id, player_id)
    if track is None:
        raise NotFoundError("Player not found in this job")
    pct = next(
        (p["possession_pct"] for p in stats.get("players", []) if p["player_id"] == player_id),
        0.0,
    )
    return PlayerView(track=track, possession_pct=pct)


def get_heatmap(
    jobs: JobRepo, results: ResultRepo, user_id: UUID, job_id: UUID, team: str
) -> dict[str, Any]:
    heatmaps = _result(jobs, results, user_id, job_id).stats.get("heatmaps", {})
    if team not in heatmaps:
        raise NotFoundError("No heatmap for that team")
    return heatmaps[team]


def get_video(
    jobs: JobRepo, results: ResultRepo, blobs: BlobStore, user_id: UUID, job_id: UUID
) -> VideoAccess:
    key = _result(jobs, results, user_id, job_id).annotated_key
    url = blobs.presigned_get_url(key, PRESIGNED_URL_MAX_TTL_S)
    if url is not None:
        return VideoAccess(url=url)
    return VideoAccess(key=key, size=blobs.size(key))
