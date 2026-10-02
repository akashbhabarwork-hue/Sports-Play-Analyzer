"""Small pure rules used by services/process.py: progress, team sampling, config snapshot."""

from dataclasses import asdict
from typing import Any

import numpy as np

from .models import PipelineParams

# Worker stages in the order the UI's stepper shows them (T-087). "queued" is the job status
# before any worker touches it; "fetching" only happens for YouTube links.
STAGES = ("fetching", "analysing", "computing", "rendering", "saving")

# Progress bands per stage. 100 is only reached when the job row says "succeeded".
PROGRESS_FETCHING = 2
PROGRESS_ANALYSE_START = 5  # pass 1: detect + track (the slow part)
PROGRESS_ANALYSE_END = 70
PROGRESS_COMPUTING = 72  # teams + metrics
PROGRESS_RENDER_START = 75  # pass 2: decode again, draw by team, encode
PROGRESS_RENDER_END = 95
PROGRESS_SAVING = 97


def band_pct(done: int, expected: int, start: int, end: int) -> int:
    """Progress inside one band; capped, because ffprobe's duration is only an estimate."""
    if expected <= 0:
        return end
    return min(end, start + (end - start) * done // expected)


def progress_pct(done: int, expected: int) -> int:
    return band_pct(done, expected, PROGRESS_ANALYSE_START, PROGRESS_ANALYSE_END)


def render_pct(done: int, expected: int) -> int:
    return band_pct(done, expected, PROGRESS_RENDER_START, PROGRESS_RENDER_END)


def should_sample_team(frame_idx: int, every: int) -> bool:
    return frame_idx % every == 0


def add_team_sample(
    samples: dict[int, list[np.ndarray]], player_id: int, feature: np.ndarray | None, cap: int
) -> None:
    """Keep up to `cap` colour features per player (memory stays bounded on long clips)."""
    if feature is None:
        return
    bucket = samples.setdefault(player_id, [])
    if len(bucket) < cap:
        bucket.append(feature)


def poll_delay(base_s: float, jitter: float, u: float) -> float:
    """Idle wait before the next claim: base ± jitter·base, `u` uniform in [0, 1].

    Jitter keeps several workers from hitting the jobs table in lockstep.
    """
    return max(0.0, base_s * (1 + jitter * (2 * u - 1)))


def pipeline_config(params: PipelineParams, extra: dict[str, Any]) -> dict[str, Any]:
    """Effective settings stored in stats["config"], so a result can be reproduced."""
    return {**asdict(params), **extra}
