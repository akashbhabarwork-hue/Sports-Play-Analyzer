"""Frame geometry for the decode/encode pipes. Pure: no ffmpeg here."""

import math

from .models import FrameSize


def _even(value: float) -> int:
    # Round down so the output is never bigger than the source (and avoid banker's rounding).
    return max(2, int(value) // 2 * 2)


def output_size(width: int, height: int, rotation: int, max_side: int) -> FrameSize:
    """Frame size we ask ffmpeg to scale to: aspect kept, long side <= max_side, both even.

    ffmpeg auto-rotates on decode, so a ±90° rotation tag swaps width and height. We compute
    the size ourselves (instead of `scale=-2:720`) so every frame is exactly W*H*3 bytes.
    """
    if width <= 0 or height <= 0:
        raise ValueError("video has no width or height")
    if rotation % 180 == 90:
        width, height = height, width
    scale = min(1.0, max_side / max(width, height))
    return FrameSize(_even(width * scale), _even(height * scale))


def expected_frames(duration_s: float, max_seconds: int, sample_fps: float) -> int:
    """How many sampled frames to expect; the denominator for job progress."""
    return max(1, math.ceil(min(duration_s, max_seconds) * sample_fps))
