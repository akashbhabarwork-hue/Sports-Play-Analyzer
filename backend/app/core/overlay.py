"""Pure inputs for the annotated-video overlay (no drawing here; that is the OpenCV adapter)."""

from collections.abc import Sequence

from .models import FrameObservation

BALL_TRAIL_FRAMES = 6  # ~1.2 s at the default 5 sampled fps


def ball_trail(
    observations: Sequence[FrameObservation], idx: int, length: int = BALL_TRAIL_FRAMES
) -> tuple[tuple[float, float], ...]:
    """Ball centres of the `length` frames before `idx` (oldest first), skipping frames
    where the ball was not seen. Empty for the first frame or when idx is out of range."""
    start = max(0, idx - length)
    centres = []
    for obs in observations[start : min(idx, len(observations))]:
        if obs.ball is not None:
            b = obs.ball
            centres.append(((b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2))
    return tuple(centres)
