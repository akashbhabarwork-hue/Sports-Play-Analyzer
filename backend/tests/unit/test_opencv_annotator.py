"""Annotated-video overlay: team colours (T-087) in the AI-tracking style, ball trail, HUD."""

import numpy as np

from app.adapters.opencv_annotator import BALL_BGR, TEAM_BGR, OpenCvFrameAnnotator
from app.core.models import Box, FrameObservation, Track
from app.core.overlay import ball_trail

H, W = 240, 400


def track(pid: int, x1: int) -> Track:
    return Track(pid, pid, Box(x1, 100, x1 + 40, 200), 0, 0, 5, 0, "confirmed")


def corner_pixel(frame: np.ndarray, x1: int) -> tuple[int, int, int]:
    # Bottom-left corner bracket of the box: drawn solid in the team colour, on top of the
    # translucent spotlight.
    return tuple(int(v) for v in frame[200, x1 + 2])  # on the bottom arm (row y2)


def blank() -> np.ndarray:
    return np.zeros((H, W, 3), np.uint8)


def test_players_are_marked_in_team_colours():
    out = OpenCvFrameAnnotator().draw(
        blank(), [track(1, 60), track(2, 170), track(3, 280)], None, 0.0,
        {1: "A", 2: "B", 3: "unknown"},
    )  # fmt: skip
    assert corner_pixel(out, 60) == TEAM_BGR["A"]
    assert corner_pixel(out, 170) == TEAM_BGR["B"]
    assert corner_pixel(out, 280) == TEAM_BGR["unknown"]


def test_brand_colours_are_the_brief_hex_values_in_bgr():
    assert TEAM_BGR["A"] == (0xEB, 0x63, 0x25)  # #2563EB
    assert TEAM_BGR["B"] == (0x48, 0x1D, 0xE1)  # #E11D48


def test_players_without_a_team_label_are_grey():
    out = OpenCvFrameAnnotator().draw(blank(), [track(4, 60)], None, 0.0, {})
    assert corner_pixel(out, 60) == TEAM_BGR["unknown"]


def test_feet_spotlight_is_translucent_team_colour():
    out = OpenCvFrameAnnotator().draw(blank(), [track(1, 60)], None, 0.0, {1: "A"})
    below_feet = out[203, 80].astype(int)  # inside the ellipse, outside the box
    assert below_feet.any() and (below_feet < np.array(TEAM_BGR["A"])).all()  # blended, not solid
    assert below_feet[0] > below_feet[2]  # blue-ish, like Team A


def test_draw_never_modifies_the_decoded_frame():
    frame = blank()
    frame.setflags(write=False)  # decoded frames are read-only views
    OpenCvFrameAnnotator().draw(frame, [track(1, 60)], Box(5, 5, 15, 15), 1.5, {1: "A"},
                                ((1.0, 1.0), (3.0, 3.0)))  # fmt: skip
    assert not frame.any()


def test_ball_trail_is_drawn_in_ball_colour_up_to_the_ball():
    ball = Box(300, 190, 310, 200)
    out = OpenCvFrameAnnotator().draw(blank(), [], ball, 0.0, {}, ((220.0, 195.0), (260.0, 195.0)))
    on_trail = tuple(int(v) for v in out[195, 240])  # halfway along the older segment
    assert on_trail != (0, 0, 0)
    assert on_trail[2] > on_trail[0]  # amber-ish (more red than blue), like BALL_BGR
    assert BALL_BGR[2] > BALL_BGR[0]


def test_ball_trail_skips_far_jumps_and_needs_a_visible_ball():
    trail = ((40.0, 195.0), (260.0, 195.0))  # 220 px jump on a 400 px frame: a false detection
    out = OpenCvFrameAnnotator().draw(blank(), [], Box(300, 190, 310, 200), 0.0, {}, trail)
    assert not out[195, 150].any()  # no line across the jump
    assert out[195, 280].any()  # the short final segment is drawn
    no_ball = OpenCvFrameAnnotator().draw(
        blank(), [], None, 0.0, {}, ((220.0, 195.0), (260.0, 195.0))
    )
    assert not no_ball[195, 240].any()  # ball not visible now: no dangling trail


def test_ball_trail_drops_fragments_cut_off_by_a_jump():
    # Older points before the jump form their own short segment; it must not be drawn.
    trail = ((20.0, 100.0), (50.0, 100.0), (260.0, 195.0))
    out = OpenCvFrameAnnotator().draw(blank(), [], Box(300, 190, 310, 200), 0.0, {}, trail)
    assert not out[100, 35].any()  # the detached fragment
    assert out[195, 280].any()  # the chain that reaches the ball


def test_legend_lists_the_clips_teams_even_when_nobody_is_in_frame():
    with_teams = OpenCvFrameAnnotator().draw(blank(), [], None, 0.0, {1: "A", 2: "B"})
    only_ball = OpenCvFrameAnnotator().draw(blank(), [], None, 0.0, {})
    assert with_teams[6:90, W - 120 : W - 6].sum() > only_ball[6:90, W - 120 : W - 6].sum()


def test_hud_panel_marks_the_frame_as_analysed():
    out = OpenCvFrameAnnotator().draw(blank(), [track(1, 60)], None, 3.0, {1: "A"})
    assert out[8:30, 8:120].any()  # top-left HUD panel + "AI TRACKING" text
    assert out[H - 20 : H - 2, 8:200].any()  # bottom-left watermark


def test_ball_trail_uses_previous_frames_only_and_skips_missing_ball():
    def obs(i: int, ball: Box | None) -> FrameObservation:
        return FrameObservation(i, i / 5, (), ball)

    observations = [
        obs(0, Box(0, 0, 2, 2)),
        obs(1, None),
        obs(2, Box(10, 10, 12, 12)),
        obs(3, None),
    ]
    assert ball_trail(observations, 0) == ()
    assert ball_trail(observations, 3) == ((1.0, 1.0), (11.0, 11.0))
    assert ball_trail(observations, 3, length=1) == ((11.0, 11.0),)
    assert ball_trail(observations, 99) == ()  # beyond the recorded frames: empty, no error
