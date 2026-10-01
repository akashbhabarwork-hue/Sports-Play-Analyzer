"""Upload limits as pure checks on what ffprobe reported."""

from ..errors import CorruptFileError, DurationExceededError
from .models import VideoProbe

DURATION_TOLERANCE_S = 0.5  # container durations are often a few frames over
MAX_DIMENSION_PX = 4096  # bounds decode cost per frame


def check_video_limits(probe: VideoProbe, max_duration_s: int) -> None:
    if probe.duration_s <= 0 or probe.width <= 0 or probe.height <= 0:
        raise CorruptFileError(CORRUPT_MESSAGE)
    if probe.duration_s > max_duration_s + DURATION_TOLERANCE_S:
        raise DurationExceededError(
            f"This video is {probe.duration_s:.0f} s long; the limit is {max_duration_s} s. "
            "Trim it and upload again."
        )
    if probe.width > MAX_DIMENSION_PX or probe.height > MAX_DIMENSION_PX:
        raise CorruptFileError(
            f"Video resolution {probe.width}x{probe.height} is too large "
            f"(max {MAX_DIMENSION_PX} px per side)."
        )


CORRUPT_MESSAGE = "We couldn't read this video — it may be corrupted. Try re-exporting it as MP4."
UNSUPPORTED_MESSAGE = "Only MP4, MOV, WebM, MKV or AVI videos are supported."
