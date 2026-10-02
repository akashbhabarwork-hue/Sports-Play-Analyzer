"""Shared fixtures for process_job tests (unit with fakes, integration with Postgres)."""

import subprocess
from pathlib import Path

from app.adapters.fake_detector import FakeDetector
from app.core.models import Box, Detection


def make_clip(path: Path, faststart: bool = False) -> str:
    """2 s 160x120 testsrc clip (10 sampled frames at SAMPLE_FPS=5)."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
           "-i", "testsrc=size=160x120:rate=25:duration=2", "-pix_fmt", "yuv420p"]  # fmt: skip
    if faststart:
        cmd += ["-movflags", "+faststart"]
    subprocess.run([*cmd, str(path)], check=True, timeout=60)
    return str(path)


def make_undecodable_clip(directory: Path) -> str:
    """Header intact (sniffs as MP4, ffprobe reads 160x120 / 2 s) but no media data:
    passes upload validation, then decodes to zero frames → DECODE_ERROR."""
    data = Path(make_clip(directory / "fs.mp4", faststart=True)).read_bytes()
    path = directory / "truncated.mp4"
    path.write_bytes(data[: data.find(b"mdat") + 8])
    return str(path)


def two_players() -> FakeDetector:
    """Two players walking right for the whole clip, the ball at player 1's feet."""
    frames = {}
    for i in range(20):
        frames[i] = [
            Detection(Box(10 + 2 * i, 40, 30 + 2 * i, 100), 0.9, "player"),
            Detection(Box(100 + i, 30, 120 + i, 90), 0.8, "player"),
            Detection(Box(22 + 2 * i, 96, 28 + 2 * i, 102), 0.4, "ball"),
        ]
    return FakeDetector(frames)
