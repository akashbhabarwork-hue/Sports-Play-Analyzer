"""Small pure rules used by services/process.py: progress, team sampling, config snapshot."""

from dataclasses import asdict
from typing import Any

import numpy as np

from .models import PipelineParams

# Progress bands shown to the user: fetching 0-5, analysing 5-95, saving 95-99.
# 100 is only reached when the job row says "succeeded".
PROGRESS_FETCHING = 2
PROGRESS_ANALYSE_START = 5
PROGRESS_ANALYSE_END = 95
PROGRESS_SAVING = 97


def progress_pct(done: int, expected: int) -> int:
    """Analysis progress; capped, because ffprobe's duration is only an estimate."""
    if expected <= 0:
        return PROGRESS_ANALYSE_END
    span = PROGRESS_ANALYSE_END - PROGRESS_ANALYSE_START
    return min(PROGRESS_ANALYSE_END, PROGRESS_ANALYSE_START + span * done // expected)


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


def pipeline_config(params: PipelineParams, extra: dict[str, Any]) -> dict[str, Any]:
    """Effective settings stored in stats["config"], so a result can be reproduced."""
    return {**asdict(params), **extra}
