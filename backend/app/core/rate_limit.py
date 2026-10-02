"""Sliding-window rate limiting (pure: the caller passes the current time)."""

import math
from collections.abc import Sequence


def prune(timestamps: Sequence[float], now: float, window_s: float) -> list[float]:
    """Hits still inside the window ending at `now`."""
    return [t for t in timestamps if t > now - window_s]


def check_window(
    timestamps: Sequence[float], now: float, limit: int, window_s: float
) -> tuple[bool, int]:
    """(allowed, retry_after_s). `timestamps` = earlier hits, oldest first.

    When blocked, the wait is until the oldest hit in the window leaves it (≥ 1 s, rounded up),
    which is what the client gets in `Retry-After`.
    """
    recent = prune(timestamps, now, window_s)
    if len(recent) < limit:
        return True, 0
    oldest = recent[len(recent) - limit]
    return False, max(1, math.ceil(oldest + window_s - now))
