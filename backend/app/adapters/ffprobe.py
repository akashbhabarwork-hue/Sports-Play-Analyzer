"""ffprobe adapter: argument list, no shell, hard timeout; any failure is CORRUPT_FILE."""

import json
import logging
import subprocess

from ..core.models import VideoProbe
from ..core.video_rules import CORRUPT_MESSAGE
from ..errors import CorruptFileError

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 15


def _fps(rate: str | None) -> float | None:
    try:
        num, den = (rate or "").split("/")
        return float(num) / float(den) if float(den) else None
    except ValueError:
        return None


class FfprobeVideoProber:
    def __init__(self, binary: str = "ffprobe"):
        self.binary = binary

    def probe(self, path: str) -> VideoProbe:
        cmd = [
            self.binary,
            "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            "-select_streams", "v:0",
            "--", path,
        ]  # fmt: skip
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=PROBE_TIMEOUT_S, shell=False, check=False
            )
        except subprocess.TimeoutExpired as e:
            logger.warning("ffprobe timed out")
            raise CorruptFileError(CORRUPT_MESSAGE) from e
        if result.returncode != 0:
            logger.info("ffprobe rejected file", extra={"returncode": result.returncode})
            raise CorruptFileError(CORRUPT_MESSAGE)
        try:
            info = json.loads(result.stdout)
            stream = info["streams"][0]
            fmt = info["format"]
            duration = float(fmt.get("duration") or stream.get("duration") or 0)
            return VideoProbe(
                format_name=str(fmt.get("format_name", "")),
                duration_s=duration,
                width=int(stream["width"]),
                height=int(stream["height"]),
                fps=_fps(stream.get("avg_frame_rate")) or _fps(stream.get("r_frame_rate")),
            )
        except (ValueError, KeyError, IndexError, TypeError) as e:
            # No video stream, or output we cannot interpret.
            raise CorruptFileError(CORRUPT_MESSAGE) from e
