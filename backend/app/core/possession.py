"""Ball possession with hysteresis. Pure.

Per frame with a visible ball, the candidate is the confirmed player whose feet are nearest the
ball centre, if within `possession_dist_ratio` × that player's box height; otherwise the ball is
loose (candidate None). The owner only changes after the same candidate (a player, or "loose")
wins `possession_min_frames` frames in a row, so a ball rolling past someone for one frame
does not hand them possession. Frames are credited to the owner at that moment.

When the ball is not seen, the owner is kept for up to BALL_GAP_FRAMES frames (a player
shielding it); after that possession resets. Percentages are of ball-visible frames only.
"""

import math
from collections import Counter
from dataclasses import dataclass

from .models import Box, FrameObservation, MetricsParams, Track

BALL_GAP_FRAMES = 2


@dataclass(frozen=True, slots=True)
class PossessionCount:
    by_player: dict[int, int]  # public id -> frames owned (ball visible)
    unassigned: int  # ball visible but nobody owned it
    ball_frames: int  # frames with the ball visible


def feet_point(box: Box) -> tuple[float, float]:
    return (box.x1 + box.x2) / 2, box.y2


def possession_candidate(ball: Box, tracks: tuple[Track, ...], ratio: float) -> int | None:
    bx, by = (ball.x1 + ball.x2) / 2, (ball.y1 + ball.y2) / 2
    best: tuple[float, int] | None = None
    for t in tracks:
        fx, fy = feet_point(t.box)
        dist = math.hypot(bx - fx, by - fy)
        if dist <= ratio * (t.box.y2 - t.box.y1) and (best is None or dist < best[0]):
            best = (dist, t.public_id)
    return None if best is None else best[1]


def possession_owners(
    observations: list[FrameObservation], params: MetricsParams
) -> list[int | None]:
    """Owner per observation (None = nobody / ball not visible), after hysteresis."""
    owner: int | None = None
    pending: int | None = None
    pending_run = 0
    unseen_run = 0
    owners: list[int | None] = []
    for obs in observations:
        if obs.ball is None:
            unseen_run += 1
            if unseen_run > BALL_GAP_FRAMES:
                owner, pending, pending_run = None, None, 0
            owners.append(None)
            continue
        unseen_run = 0
        cand = possession_candidate(obs.ball, obs.tracks, params.possession_dist_ratio)
        if cand == owner:
            pending, pending_run = None, 0
        else:
            pending_run = pending_run + 1 if cand == pending else 1
            pending = cand
            if pending_run >= params.possession_min_frames:
                owner, pending, pending_run = cand, None, 0
        owners.append(owner)
    return owners


def count_possession(
    observations: list[FrameObservation], params: MetricsParams
) -> PossessionCount:
    owners = possession_owners(observations, params)
    visible = [o for obs, o in zip(observations, owners) if obs.ball is not None]
    held = Counter(o for o in visible if o is not None)
    return PossessionCount(
        by_player=dict(held),
        unassigned=sum(1 for o in visible if o is None),
        ball_frames=len(visible),
    )
