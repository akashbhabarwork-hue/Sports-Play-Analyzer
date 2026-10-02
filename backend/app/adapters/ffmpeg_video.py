"""ffmpeg pipes: decode sampled BGR frames out, encode annotated frames in.

Memory stays flat: one raw frame (W*H*3 bytes) is in flight at a time, never the whole video.
Commands are argument lists (no shell). stderr goes to a temp file, not a pipe: an unread
stderr pipe fills up (~64 KB) and ffmpeg blocks forever. Every exit path kills and reaps the
process, so a detector exception mid-video leaves no zombie ffmpeg behind.
"""

import logging
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from typing import IO

import numpy as np

from ..core.models import FrameSize
from ..errors import DecodeError, ExternalServiceError

logger = logging.getLogger(__name__)

DECODE_MESSAGE = "We couldn't decode frames from this video. Try re-exporting it as H.264 MP4."
ENCODE_MESSAGE = "We couldn't write the annotated video."
WAIT_TIMEOUT_S = 30  # after EOF ffmpeg only has to flush and exit
ENCODE_WAIT_TIMEOUT_S = 120  # libx264 may still be encoding buffered frames
STDERR_TAIL_BYTES = 2000


def read_exact(stream: IO[bytes], n: int) -> bytes | None:
    """Read exactly n bytes, looping over short pipe reads. None at EOF.

    A partial frame at EOF (truncated file) is dropped rather than returned half-filled.
    """
    chunks: list[bytes] = []
    remaining = n
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stderr_tail(err: IO[bytes]) -> str:
    err.seek(0, 2)
    err.seek(max(0, err.tell() - STDERR_TAIL_BYTES))
    return err.read().decode("utf-8", "replace").strip()


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait()


class FfmpegFrameReader:
    def __init__(self, binary: str = "ffmpeg"):
        self.binary = binary

    def frames(
        self, path: str, size: FrameSize, sample_fps: float, max_seconds: int
    ) -> Iterator[np.ndarray]:
        cmd = [
            self.binary,
            "-v", "error", "-nostdin",
            "-i", path,
            "-t", str(max_seconds),
            "-an", "-sn", "-dn",
            "-vf", f"fps={sample_fps},scale={size.width}:{size.height}",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "pipe:1",
        ]  # fmt: skip
        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, shell=False)
            count = 0
            try:
                while (buf := read_exact(proc.stdout, size.frame_bytes)) is not None:
                    count += 1
                    # Read-only view on the buffer: callers copy before drawing on it.
                    yield np.frombuffer(buf, np.uint8).reshape(size.height, size.width, 3)
                returncode = proc.wait(timeout=WAIT_TIMEOUT_S)
            except subprocess.TimeoutExpired as e:
                raise DecodeError(DECODE_MESSAGE) from e
            finally:
                _stop(proc)
                proc.stdout.close()
            if returncode != 0 or count == 0:
                logger.info(
                    "ffmpeg decode failed",
                    extra={"returncode": returncode, "frames": count, "stderr": _stderr_tail(err)},
                )
                raise DecodeError(DECODE_MESSAGE)


class FfmpegVideoEncoder:
    def __init__(self, binary: str = "ffmpeg", crf: int = 26, preset: str = "veryfast"):
        self.binary, self.crf, self.preset = binary, crf, preset

    def encode(
        self, frames: Iterable[np.ndarray], out_path: str, size: FrameSize, fps: float
    ) -> int:
        cmd = [
            self.binary,
            "-v", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{size.width}x{size.height}", "-r", str(fps),
            "-i", "pipe:0",
            "-an", "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            # yuv420p + faststart: plays in every browser and starts before fully downloaded.
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out_path,
        ]  # fmt: skip
        expected_shape = (size.height, size.width, 3)
        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err, shell=False)
            count = 0
            try:
                for frame in frames:
                    if frame.shape != expected_shape or frame.dtype != np.uint8:
                        raise ValueError(f"frame {frame.shape} {frame.dtype} != {expected_shape}")
                    proc.stdin.write(np.ascontiguousarray(frame).tobytes())
                    count += 1
                proc.stdin.close()
                returncode = proc.wait(timeout=ENCODE_WAIT_TIMEOUT_S)
            except (OSError, subprocess.TimeoutExpired) as e:
                # ffmpeg died (or hung) mid-stream; its stderr says why. A dead pipe is
                # BrokenPipeError on Linux but OSError(EINVAL) on Windows, so catch the parent.
                logger.warning("ffmpeg encode aborted", extra={"stderr": _stderr_tail(err)})
                raise ExternalServiceError(ENCODE_MESSAGE) from e
            finally:
                _stop(proc)
                if proc.stdin and not proc.stdin.closed:
                    try:
                        proc.stdin.close()
                    except OSError:
                        pass
            if returncode != 0 or count == 0:
                logger.warning(
                    "ffmpeg encode failed",
                    extra={"returncode": returncode, "frames": count, "stderr": _stderr_tail(err)},
                )
                raise ExternalServiceError(ENCODE_MESSAGE)
            return count
