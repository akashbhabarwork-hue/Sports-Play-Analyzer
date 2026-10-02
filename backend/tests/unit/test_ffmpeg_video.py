import io
import subprocess

import numpy as np
import pytest

from app.adapters.ffmpeg_video import FfmpegFrameReader, FfmpegVideoEncoder, read_exact
from app.adapters.ffprobe import FfprobeVideoProber
from app.core.models import FrameSize
from app.core.video_frames import expected_frames, output_size
from app.errors import DecodeError, ExternalServiceError

SIZE = FrameSize(160, 120)


class ShortReads(io.BytesIO):
    """A pipe that hands back at most 3 bytes per read, like a busy ffmpeg stdout."""

    def read(self, n=-1):
        return super().read(min(n, 3))


# ---- read_exact (pure, no ffmpeg) ----


def test_read_exact_loops_over_short_reads():
    assert read_exact(ShortReads(b"abcdefghij"), 10) == b"abcdefghij"


def test_read_exact_returns_frames_back_to_back():
    stream = ShortReads(b"aaaabbbb")
    assert read_exact(stream, 4) == b"aaaa"
    assert read_exact(stream, 4) == b"bbbb"
    assert read_exact(stream, 4) is None


def test_read_exact_drops_partial_tail_frame():
    assert read_exact(ShortReads(b"abcde"), 8) is None


def test_read_exact_none_on_empty_stream():
    assert read_exact(io.BytesIO(b""), 4) is None


# ---- real ffmpeg (marker `ffmpeg`; CI installs it) ----


def make_clip(path, seconds=2, size="160x120", rate=25, extra=()):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"testsrc=size={size}:rate={rate}:duration={seconds}",
         *extra, "-pix_fmt", "yuv420p", str(path)],
        check=True, timeout=60,
    )  # fmt: skip
    return str(path)


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return make_clip(tmp_path_factory.mktemp("clip") / "testsrc.mp4")


@pytest.mark.ffmpeg
def test_reader_samples_two_seconds_at_5_fps_into_10_frames(clip):
    frames = list(FfmpegFrameReader().frames(clip, SIZE, 5.0, 60))

    assert len(frames) == 10 == expected_frames(2.0, 60, 5.0)
    assert all(f.shape == (120, 160, 3) and f.dtype == np.uint8 for f in frames)
    assert frames[0].any()  # testsrc is colourful, not black


@pytest.mark.ffmpeg
def test_reader_scales_to_requested_size(clip):
    small = FrameSize(80, 60)
    frame = next(iter(FfmpegFrameReader().frames(clip, small, 5.0, 60)))
    assert frame.shape == (60, 80, 3)


@pytest.mark.ffmpeg
def test_reader_stops_at_max_seconds(clip):
    assert len(list(FfmpegFrameReader().frames(clip, SIZE, 5.0, 1))) == 5


@pytest.mark.ffmpeg
def test_reader_frames_are_read_only_views(clip):
    frame = next(iter(FfmpegFrameReader().frames(clip, SIZE, 5.0, 60)))
    with pytest.raises(ValueError):
        frame[0, 0, 0] = 1


@pytest.mark.ffmpeg
def test_reader_closed_early_kills_ffmpeg(clip, monkeypatch):
    procs = []
    real_popen = subprocess.Popen

    def spy(*args, **kwargs):
        procs.append(real_popen(*args, **kwargs))
        return procs[-1]

    monkeypatch.setattr(subprocess, "Popen", spy)
    gen = FfmpegFrameReader().frames(clip, SIZE, 5.0, 60)
    next(gen)
    gen.close()  # what happens when detection raises mid-video

    assert procs and procs[0].returncode is not None


@pytest.mark.ffmpeg
def test_reader_garbage_file_raises_decode_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4000)
    with pytest.raises(DecodeError) as e:
        list(FfmpegFrameReader().frames(str(bad), SIZE, 5.0, 60))
    assert e.value.code == "DECODE_ERROR"


@pytest.mark.ffmpeg
def test_encoder_output_is_probeable_h264(clip, tmp_path):
    out = str(tmp_path / "annotated.mp4")
    frames = FfmpegFrameReader().frames(clip, SIZE, 5.0, 60)

    written = FfmpegVideoEncoder().encode((f.copy() for f in frames), out, SIZE, 5.0)

    probe = FfprobeVideoProber().probe(out)
    assert written == 10
    assert (probe.width, probe.height) == (160, 120)
    assert probe.fps == pytest.approx(5.0)
    assert probe.duration_s == pytest.approx(2.0, abs=0.3)


@pytest.mark.ffmpeg
def test_encoder_rejects_wrong_frame_shape(tmp_path):
    wrong = [np.zeros((10, 10, 3), np.uint8)]
    with pytest.raises(ValueError):
        FfmpegVideoEncoder().encode(wrong, str(tmp_path / "x.mp4"), SIZE, 5.0)


@pytest.mark.ffmpeg
def test_encoder_reports_ffmpeg_dying_mid_stream(tmp_path):
    # Unwritable output path: ffmpeg exits at once, so our writes hit a dead pipe.
    out = str(tmp_path / "missing-dir" / "x.mp4")
    frames = (np.zeros((120, 160, 3), np.uint8) for _ in range(500))
    with pytest.raises(ExternalServiceError):
        FfmpegVideoEncoder().encode(frames, out, SIZE, 5.0)


@pytest.mark.ffmpeg
def test_encoder_with_no_frames_fails_cleanly(tmp_path):
    with pytest.raises(ExternalServiceError):
        FfmpegVideoEncoder().encode([], str(tmp_path / "x.mp4"), SIZE, 5.0)


@pytest.mark.ffmpeg
def test_rotated_phone_clip_decodes_as_portrait(tmp_path):
    src = make_clip(tmp_path / "landscape.mp4", seconds=1, size="320x180")
    rotated = str(tmp_path / "rotated.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", src,
         "-c", "copy", rotated],
        check=True, timeout=60,
    )  # fmt: skip
    probe = FfprobeVideoProber().probe(rotated)
    size = output_size(probe.width, probe.height, probe.rotation, 1280)

    frame = next(iter(FfmpegFrameReader().frames(rotated, size, 5.0, 60)))

    assert probe.rotation in (90, 270)
    assert size == FrameSize(180, 320)
    assert frame.shape == (320, 180, 3)
