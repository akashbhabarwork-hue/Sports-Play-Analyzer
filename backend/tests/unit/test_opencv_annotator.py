"""T-087: boxes in the annotated video are coloured by team (A blue, B red, unknown grey)."""

import numpy as np

from app.adapters.opencv_annotator import TEAM_BGR, OpenCvFrameAnnotator
from app.core.models import Box, Track


def track(pid: int, x1: int) -> Track:
    return Track(pid, pid, Box(x1, 20, x1 + 30, 80), 0, 0, 5, 0, "confirmed")


def edge_pixel(frame: np.ndarray, x1: int) -> tuple[int, int, int]:
    # Left edge of the box, below the label: drawn in the box colour.
    return tuple(int(v) for v in frame[60, x1])


def test_boxes_use_team_colours():
    frame = np.zeros((120, 200, 3), np.uint8)
    out = OpenCvFrameAnnotator().draw(
        frame,
        [track(1, 10), track(2, 80), track(3, 150)],
        None,
        0.0,
        {1: "A", 2: "B", 3: "unknown"},
    )
    assert edge_pixel(out, 10) == TEAM_BGR["A"]
    assert edge_pixel(out, 80) == TEAM_BGR["B"]
    assert edge_pixel(out, 150) == TEAM_BGR["unknown"]


def test_brand_colours_are_the_brief_hex_values_in_bgr():
    assert TEAM_BGR["A"] == (0xEB, 0x63, 0x25)  # #2563EB
    assert TEAM_BGR["B"] == (0x48, 0x1D, 0xE1)  # #E11D48


def test_players_without_a_team_label_are_grey():
    out = OpenCvFrameAnnotator().draw(
        np.zeros((120, 200, 3), np.uint8), [track(4, 10)], None, 0.0, {}
    )
    assert edge_pixel(out, 10) == TEAM_BGR["unknown"]


def test_draw_never_modifies_the_decoded_frame():
    frame = np.zeros((120, 200, 3), np.uint8)
    frame.setflags(write=False)  # decoded frames are read-only views
    OpenCvFrameAnnotator().draw(frame, [track(1, 10)], Box(5, 5, 15, 15), 1.5, {1: "A"})
    assert not frame.any()
