"""Job submission use cases."""

import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from ..core.blob_keys import upload_key
from ..core.file_sniff import SNIFF_BYTES, Container, sniff_video_container
from ..core.models import Job, NewVideo, VideoProbe
from ..core.ports import BlobStore, JobRepo, VideoProber
from ..core.url_rules import canonicalize_youtube_url
from ..core.video_rules import UNSUPPORTED_MESSAGE, check_video_limits
from ..errors import UnsupportedFormatError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UploadLimits:
    max_bytes: int
    max_duration_s: int


def validate_video_file(
    path: str, prober: VideoProber, max_duration_s: int
) -> tuple[Container, VideoProbe]:
    """Judge a local file by content: magic bytes, then ffprobe + limits.

    Shared by uploads and URL downloads so both inputs pass the same checks.
    """
    with open(path, "rb") as f:
        container = sniff_video_container(f.read(SNIFF_BYTES))
    if container is None:
        raise UnsupportedFormatError(UNSUPPORTED_MESSAGE)
    probe = prober.probe(path)
    check_video_limits(probe, max_duration_s)
    return container, probe


def submit_upload_job(
    jobs: JobRepo,
    blobs: BlobStore,
    prober: VideoProber,
    user_id: UUID,
    path: str,
    original_filename: str | None,
    limits: UploadLimits,
    config: dict[str, Any],
) -> Job:
    """Validate a fully received upload at `path`, store it, and queue its job.

    The file is judged by content: magic bytes first, then ffprobe. The blob is stored under
    an app-generated video id before the rows exist, so the worker can never claim a job
    whose file is missing; if the insert fails the blob is removed again.
    """
    container, probe = validate_video_file(path, prober, limits.max_duration_s)

    video_id = uuid4()
    key = upload_key(video_id, container.extension)
    blobs.put_file(key, path, container.content_type)
    new_video = NewVideo(
        source_type="upload",
        original_filename=(original_filename or "")[:255] or None,
        storage_key=key,
        size_bytes=os.path.getsize(path),
        id=video_id,
        duration_s=probe.duration_s,
        width=probe.width,
        height=probe.height,
        fps=probe.fps,
    )
    try:
        job = jobs.create_with_video(user_id, new_video, config)
    except BaseException:
        blobs.delete(key)
        raise
    logger.info(
        "upload job queued",
        extra={"user_id": str(user_id), "job_id": str(job.id), "container": container.name},
    )
    return job


def submit_url_job(jobs: JobRepo, user_id: UUID, raw_url: str, config: dict[str, Any]) -> Job:
    """Queue a job for a YouTube link. No network here: the worker fetches it (T-043).

    Only the canonical URL rebuilt from the video id is stored, never the raw input.
    """
    ref = canonicalize_youtube_url(raw_url)
    job = jobs.create_with_video(user_id, NewVideo(source_type="url", source_url=ref.url), config)
    logger.info(
        "url job queued",
        extra={"user_id": str(user_id), "job_id": str(job.id), "video_ref": ref.video_id},
    )
    return job
