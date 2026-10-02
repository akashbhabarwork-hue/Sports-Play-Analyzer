import pytest

from app.core.models import FrameSize
from app.core.video_frames import expected_frames, output_size


def test_output_size_keeps_small_video_as_is():
    assert output_size(640, 360, 0, 1280) == FrameSize(640, 360)


def test_output_size_caps_long_side_and_keeps_aspect():
    assert output_size(1920, 1080, 0, 1280) == FrameSize(1280, 720)


def test_output_size_caps_portrait_on_height():
    assert output_size(1080, 1920, 0, 1280) == FrameSize(720, 1280)


def test_output_size_forces_even_dimensions():
    size = output_size(641, 361, 0, 1280)
    assert size.width % 2 == 0 and size.height % 2 == 0
    assert size == FrameSize(640, 360)  # rounded down: never larger than the source


def test_output_size_swaps_for_rotated_phone_video():
    # Stored landscape with a 90° rotation tag: ffmpeg auto-rotates, so frames come out portrait.
    assert output_size(1920, 1080, 90, 1280) == FrameSize(720, 1280)
    assert output_size(1920, 1080, -90, 1280) == FrameSize(720, 1280)
    assert output_size(1920, 1080, 270, 1280) == FrameSize(720, 1280)


def test_output_size_180_rotation_does_not_swap():
    assert output_size(1920, 1080, 180, 1280) == FrameSize(1280, 720)


def test_output_size_never_below_two_pixels():
    size = output_size(4000, 1, 0, 1280)
    assert size.height >= 2 and size.width == 1280


def test_frame_size_bytes_is_bgr24():
    assert FrameSize(4, 2).frame_bytes == 4 * 2 * 3


@pytest.mark.parametrize("bad", [(0, 360), (640, 0), (-1, 10)])
def test_output_size_rejects_empty_dimensions(bad):
    with pytest.raises(ValueError):
        output_size(bad[0], bad[1], 0, 1280)


def test_expected_frames_uses_duration_times_fps():
    assert expected_frames(2.0, 60, 5.0) == 10


def test_expected_frames_capped_by_max_seconds():
    assert expected_frames(90.0, 60, 5.0) == 300


def test_expected_frames_at_least_one():
    assert expected_frames(0.0, 60, 5.0) == 1
