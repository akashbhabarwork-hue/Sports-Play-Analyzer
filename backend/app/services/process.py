"""Process one claimed job end to end: the worker's main use case (T-062, D-026, T-087).

fetch (URL) → download blob → probe →
  pass 1 "analysing": [decode → detect → track → record → sample jersey colours] per frame →
  "computing": teams + metrics →
  pass 2 "rendering": [decode again → draw boxes in team colours] streamed into the encoder →
  "saving": upload annotated.mp4 → finish.
Only one decoded frame is in memory at a time; observations are small per-frame metadata.
Pass 2 repeats only decoding and drawing (no detection), so it is cheap next to pass 1.

Failures:
- Problems with the input (corrupt, too long, YouTube blocked, undecodable, model unusable)
  are final: the job is marked failed with a readable message.
- Anything else (database, storage, encoder, bugs) is re-raised: the lease lapses, another
  attempt runs, and after max_attempts the sweep marks it WORKER_CRASHED.
- A heartbeat or finish that returns False means another worker owns the job now: stop and
  write nothing.
"""

import logging
import os
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np

from ..core.blob_keys import annotated_key, thumbnail_key
from ..core.metrics import build_stats
from ..core.models import (
    FrameObservation,
    FrameSize,
    Job,
    JobOutcome,
    MetricsParams,
    PipelineParams,
    TrackerParams,
    TrackerState,
)
from ..core.pipeline import (
    PROGRESS_COMPUTING,
    PROGRESS_FETCHING,
    PROGRESS_SAVING,
    add_team_sample,
    pipeline_config,
    progress_pct,
    render_pct,
    should_sample_team,
)
from ..core.ports import (
    BlobStore,
    Detector,
    FrameAnnotator,
    FrameReader,
    JobQueue,
    MediaDownloader,
    MediaInfoFetcher,
    VideoEncoder,
    VideoProber,
    VideoRepo,
)
from ..core.teams import assign_teams, colour_feature, torso_pixels
from ..core.tracking import pick_ball, player_detections, update
from ..core.video_frames import expected_frames, output_size
from ..errors import (
    CorruptFileError,
    DecodeError,
    DownloadFailedError,
    DurationExceededError,
    LeaseLostError,
    ModelError,
    UnsupportedFormatError,
    UrlNotAllowedError,
    YouTubeBlockedError,
)
from .fetch import fetch_url_video
from .submit import UploadLimits

logger = logging.getLogger(__name__)

# The user's input (or our model) is the problem: retrying cannot help.
FINAL_ERRORS = (
    CorruptFileError,
    UnsupportedFormatError,
    DurationExceededError,
    UrlNotAllowedError,
    YouTubeBlockedError,
    DownloadFailedError,
    DecodeError,
    ModelError,
)
LEASE_LOST_MESSAGE = "This job is now owned by another worker."
THUMBNAIL_MAX_WIDTH = 320


@dataclass(frozen=True, slots=True)
class PipelinePorts:
    queue: JobQueue
    videos: VideoRepo
    blobs: BlobStore
    prober: VideoProber
    media_info: MediaInfoFetcher | None
    downloader: MediaDownloader | None
    frames: FrameReader
    encoder: VideoEncoder
    detector: Detector
    annotator: FrameAnnotator


@dataclass(frozen=True, slots=True)
class ProcessConfig:
    pipeline: PipelineParams
    tracker: TrackerParams
    metrics: MetricsParams
    limits: UploadLimits
    lease_s: int
    extra_config: dict[str, Any]  # tracker/metrics/detector values for stats["config"]
    tmp_root: str | None = None


def process_job(job: Job, ports: PipelinePorts, cfg: ProcessConfig, worker_id: str) -> str:
    """Run one claimed job. Returns "succeeded", "failed" or "lease_lost".

    Transient errors are re-raised (see module docstring); the worker loop logs them.
    """
    log = {"job_id": str(job.id), "user_id": str(job.user_id), "attempt": job.attempts}
    try:
        _run(job, ports, cfg, worker_id)
    except LeaseLostError:
        logger.warning("lease lost; stopping without writing", extra=log)
        return "lease_lost"
    except FINAL_ERRORS as e:
        logger.info("job failed", extra={**log, "error_code": e.code})
        if not ports.queue.fail(job.id, worker_id, e.code, str(e)):
            logger.warning("lease lost before the failure was recorded", extra=log)
            return "lease_lost"
        return "failed"
    logger.info("job succeeded", extra=log)
    return "succeeded"


def _beat(
    ports: PipelinePorts, job: Job, worker_id: str, cfg: ProcessConfig, progress: int, stage: str
) -> None:
    if not ports.queue.heartbeat(job.id, worker_id, progress, stage, cfg.lease_s):
        raise LeaseLostError(LEASE_LOST_MESSAGE)


def _run(job: Job, ports: PipelinePorts, cfg: ProcessConfig, worker_id: str) -> None:
    _beat(ports, job, worker_id, cfg, PROGRESS_FETCHING, "fetching")
    video = ports.videos.get_for_worker(job.video_id)
    if video is None:  # FK makes this impossible; treat as a bug, not as bad input
        raise RuntimeError("job has no video row")
    key = video.storage_key
    if key is None:
        if ports.media_info is None or ports.downloader is None:
            raise RuntimeError("URL fetching is not wired into this worker")
        key = fetch_url_video(
            ports.videos, ports.blobs, ports.media_info, ports.downloader, ports.prober,
            video, cfg.limits, cfg.tmp_root,
        )  # fmt: skip

    p = cfg.pipeline
    with tempfile.TemporaryDirectory(dir=cfg.tmp_root, prefix="job-") as tmp:
        src, out = os.path.join(tmp, "source"), os.path.join(tmp, "annotated.mp4")
        ports.blobs.get_to_path(key, src)
        probe = ports.prober.probe(src)
        size = output_size(probe.width, probe.height, probe.rotation, p.max_frame_side)
        expected = expected_frames(probe.duration_s, p.max_seconds, p.sample_fps)

        # Pass 1: the slow part (detection). Only metadata is kept, never pixels.
        observations, samples = _analyse(job, ports, cfg, worker_id, src, size, expected)

        _beat(ports, job, worker_id, cfg, PROGRESS_COMPUTING, "computing")
        teams = assign_teams(samples, p.team_min_separation)
        result = build_stats(job.id, observations, size.width, size.height, cfg.metrics, teams)
        stats = {
            **result.stats,
            "video": {
                "duration_s": round(probe.duration_s, 2),
                "width": size.width,
                "height": size.height,
                "sample_fps": p.sample_fps,
                "frames_analysed": len(observations),
            },
            "config": pipeline_config(p, cfg.extra_config),
        }

        # Pass 2: decode again and draw the recorded boxes in team colours, straight into the
        # encoder. No detection here, so it costs a small fraction of pass 1 (T-087).
        frames = _rendered_frames(job, ports, cfg, worker_id, src, size, observations, teams)
        ports.encoder.encode(frames, out, size, p.sample_fps)

        _beat(ports, job, worker_id, cfg, PROGRESS_SAVING, "saving")
        blob_key = annotated_key(job.id)  # deterministic: a retry overwrites, never duplicates
        ports.blobs.put_file(blob_key, out, "video/mp4")

    outcome = JobOutcome(stats=stats, annotated_key=blob_key, tracks=result.tracks)
    if not ports.queue.finish(job.id, worker_id, outcome):
        raise LeaseLostError(LEASE_LOST_MESSAGE)


def _save_thumbnail(ports: PipelinePorts, video_id: UUID, frame: np.ndarray, tmp: str) -> None:
    """First decoded frame → small JPEG for lists/processing page. Deterministic key, so a
    retry overwrites it (T-086)."""
    path = os.path.join(tmp, "thumbnail.jpg")
    with open(path, "wb") as f:
        f.write(ports.annotator.thumbnail_jpeg(frame, THUMBNAIL_MAX_WIDTH))
    key = thumbnail_key(video_id)
    ports.blobs.put_file(key, path, "image/jpeg")
    ports.videos.set_thumbnail_for_worker(video_id, key)


def _analyse(
    job: Job,
    ports: PipelinePorts,
    cfg: ProcessConfig,
    worker_id: str,
    src: str,
    size: FrameSize,
    expected: int,
) -> tuple[list[FrameObservation], dict[int, list[np.ndarray]]]:
    """Pass 1: decode → detect → track → record, one frame at a time.

    Returns per-frame observations and jersey-colour samples (small metadata, not pixels).
    """
    p = cfg.pipeline
    state = TrackerState()
    observations: list[FrameObservation] = []
    samples: dict[int, list[np.ndarray]] = {}
    for idx, frame in enumerate(ports.frames.frames(src, size, p.sample_fps, p.max_seconds)):
        if idx % p.heartbeat_every_frames == 0:
            _beat(ports, job, worker_id, cfg, progress_pct(idx, expected), "analysing")
        if idx == 0:
            _save_thumbnail(ports, job.video_id, frame, os.path.dirname(src))
        dets = ports.detector.detect(frame)
        players = player_detections(dets, size.width, size.height, cfg.tracker)
        ball = pick_ball(dets)
        state, tracks = update(state, players, cfg.tracker)
        t_s = idx / p.sample_fps
        ball_box = ball.box if ball else None
        observations.append(FrameObservation(idx, t_s, tuple(tracks), ball_box))

        if should_sample_team(idx, p.team_sample_every):
            rgb = frame[..., ::-1]  # frames are BGR; core/teams.py expects RGB
            for track in tracks:
                pixels = torso_pixels(rgb, track.box)
                feature = colour_feature(pixels) if pixels is not None else None
                add_team_sample(samples, track.public_id, feature, p.team_max_samples)
    return observations, samples


def _rendered_frames(
    job: Job,
    ports: PipelinePorts,
    cfg: ProcessConfig,
    worker_id: str,
    src: str,
    size: FrameSize,
    observations: list[FrameObservation],
    teams: Mapping[int, str],
) -> Iterator[np.ndarray]:
    """Pass 2: decode the same frames again and draw what pass 1 recorded, in team colours.

    The decoder is deterministic, so frame idx here is frame idx in pass 1; a frame beyond the
    recorded ones (should not happen) is drawn without boxes rather than failing the job.
    """
    p = cfg.pipeline
    total = len(observations)
    for idx, frame in enumerate(ports.frames.frames(src, size, p.sample_fps, p.max_seconds)):
        if idx % p.heartbeat_every_frames == 0:
            _beat(ports, job, worker_id, cfg, render_pct(idx, total), "rendering")
        obs = observations[idx] if idx < total else None
        tracks = obs.tracks if obs else ()
        ball = obs.ball if obs else None
        yield ports.annotator.draw(frame, tracks, ball, idx / p.sample_fps, teams)
