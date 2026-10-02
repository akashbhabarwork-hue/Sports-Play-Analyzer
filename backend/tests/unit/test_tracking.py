"""Tracker tests driven by fixture detections (tests/fixtures/tracks_*.json). No model, no video."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.config import Settings, validate_settings
from app.core.models import Box, Detection, TrackerParams, TrackerState
from app.core.tracking import associate, iou_matrix, pick_ball, player_detections, predict, update
from app.wiring import tracker_params

FIXTURES = Path(__file__).parent.parent / "fixtures"
TEST_PARAMS = TrackerParams(
    high_thresh=0.5, low_thresh=0.1, match_iou=0.3, low_match_iou=0.5, max_age=5, min_hits=3
)


def load_frames(name: str) -> list[list[Detection]]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return [
        [Detection(Box(*d["box"]), d["score"], d["cls"]) for d in frame] for frame in data["frames"]
    ]


def run(frames: list[list[Detection]], params: TrackerParams = TEST_PARAMS) -> list[list[int]]:
    """Feed every frame through the tracker; return the public ids reported per frame."""
    state = TrackerState()
    out = []
    for dets in frames:
        state, seen = update(state, dets, params)
        out.append([t.public_id for t in seen])
    return out


def all_ids(per_frame: list[list[int]]) -> set[int]:
    return {i for ids in per_frame for i in ids}


def test_single_player_keeps_id_while_moving():
    per_frame = run(load_frames("tracks_single_moving.json"))
    assert all_ids(per_frame) == {1}
    # Tentative for the first min_hits - 1 frames, then reported every frame.
    assert per_frame[:2] == [[], []]
    assert all(ids == [1] for ids in per_frame[2:])


def test_track_id_stable_when_player_briefly_occluded():
    per_frame = run(load_frames("tracks_occlusion.json"))
    assert per_frame[8:11] == [[], [], []]  # hidden: not reported, but kept as "lost"
    assert per_frame[11:] == [[1]] * (len(per_frame) - 11)
    assert all_ids(per_frame) == {1}


def test_track_dropped_after_max_age():
    frames = load_frames("tracks_long_gap.json")
    per_frame = run(frames)
    assert all_ids(per_frame) == {1, 2}
    # The reappearing player is a new tentative track: unreported until min_hits again.
    back = 6 + TEST_PARAMS.max_age + 1
    assert per_frame[back : back + 2] == [[], []]
    assert per_frame[back + 2] == [2]


def test_track_kept_at_exactly_max_age():
    frames = load_frames("tracks_long_gap.json")
    gap_start, gap_len = 6, TEST_PARAMS.max_age + 1
    # Shorten the gap by one frame -> missing exactly max_age frames -> same id.
    shorter = frames[: gap_start + gap_len - 1] + frames[gap_start + gap_len :]
    assert all_ids(run(shorter)) == {1}


def test_low_confidence_detection_keeps_track_alive():
    frames = load_frames("tracks_low_confidence.json")
    per_frame = run(frames)
    assert per_frame[6:11] == [[1]] * 5  # stage 2 matched the 0.3-score boxes
    assert all_ids(per_frame) == {1}
    # Without the second stage the track would go lost and the low boxes are ignored.
    no_low = replace(TEST_PARAMS, low_thresh=0.4)
    assert run(frames, no_low)[6:11] == [[]] * 5


def test_low_confidence_detection_never_starts_track():
    frames = [[Detection(Box(0, 0, 40, 100), 0.3, "player")] for _ in range(10)]
    assert all_ids(run(frames)) == set()


def test_low_confidence_detection_cannot_grow_a_tentative_track():
    # One confident box then only weak ones: stage 2 is for established tracks, so this
    # never reaches min_hits.
    box = Box(0, 0, 40, 100)
    frames = [[Detection(box, 0.9, "player")]] + [[Detection(box, 0.3, "player")]] * 5
    assert all_ids(run(frames)) == set()


def test_two_players_crossing_keep_ids():
    frames = load_frames("tracks_crossing.json")
    state = TrackerState()
    left_to_right: set[int] = set()
    for dets in frames:
        state, seen = update(state, dets, TEST_PARAMS)
        for t in seen:
            # Player 1 started on the left at y=200 and must stay the y=200 box throughout.
            if t.box.y1 == 200:
                left_to_right.add(t.public_id)
    assert left_to_right == {1}
    assert {t.public_id for t in state.tracks} == {1, 2}


def test_one_frame_false_positive_never_confirmed():
    state = TrackerState()
    for dets in load_frames("tracks_false_positive.json"):
        state, _ = update(state, dets, TEST_PARAMS)
    assert [t.public_id for t in state.tracks] == [1]
    assert state.next_public == 2


def test_public_ids_are_contiguous():
    per_frame = run(load_frames("tracks_staggered.json"))
    assert per_frame[-1] == [1, 2, 3]
    # Ids follow order of appearance.
    assert per_frame[2] == [1]
    assert per_frame[7] == [1, 2]


def test_min_hits_one_confirms_immediately():
    params = replace(TEST_PARAMS, min_hits=1)
    assert run([[Detection(Box(0, 0, 40, 100), 0.9, "player")]], params) == [[1]]


def test_ball_detections_are_not_tracked():
    ball = Detection(Box(10, 10, 20, 20), 0.9, "ball")
    assert all_ids(run([[ball]] * 5)) == set()


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ([0, 0, 10, 10], [0, 0, 10, 10], 1.0),
        ([0, 0, 10, 10], [20, 20, 30, 30], 0.0),
        ([0, 0, 10, 10], [5, 0, 15, 10], 1 / 3),  # half overlap: 50 / (100 + 100 - 50)
        ([0, 0, 10, 10], [10, 0, 20, 10], 0.0),  # touching edges
        ([0, 0, 10, 10], [2, 2, 8, 8], 0.36),  # contained
    ],
)
def test_iou_matrix_table(a, b, expected):
    assert iou_matrix(np.array([a], float), np.array([b], float))[0, 0] == pytest.approx(expected)


def test_iou_matrix_empty_inputs():
    one = np.array([[0, 0, 1, 1]], float)
    assert iou_matrix(np.zeros((0, 4)), one).shape == (0, 1)
    assert iou_matrix(one, np.zeros((0, 4))).shape == (1, 0)


def test_iou_matrix_zero_area_box_is_safe():
    point = np.array([[5, 5, 5, 5]], float)
    assert iou_matrix(point, point)[0, 0] == 0.0


def test_associate_is_optimal_not_greedy():
    # Greedy would give track 0 its best box (det 0, IoU 0.6) and leave track 1 unmatched;
    # Hungarian pairs 0->1 and 1->0 for a higher total.
    tracks = np.array([[0, 0, 10, 10], [4, 0, 14, 10]], float)
    dets = np.array([[2, 0, 12, 10], [-2, 0, 8, 10]], float)
    matches, left_t, left_d = associate(tracks, dets, 0.3)
    assert sorted(matches) == [(0, 1), (1, 0)]
    assert left_t == [] and left_d == []


def test_associate_rejects_pairs_below_min_iou():
    matches, left_t, left_d = associate(
        np.array([[0, 0, 10, 10]], float), np.array([[8, 0, 18, 10]], float), 0.3
    )
    assert matches == [] and left_t == [0] and left_d == [0]


def test_predict_moves_box_by_velocity_times_elapsed_frames():
    state = TrackerState()
    for i in range(6):
        state, _ = update(
            state, [Detection(Box(10 * i, 0, 10 * i + 40, 100), 0.9, "player")], TEST_PARAMS
        )
    t = replace(state.tracks[0], misses=2)
    p = predict(t)
    assert p.x1 == pytest.approx(t.box.x1 + 3 * t.vx)
    assert t.vx == pytest.approx(10, abs=0.5)


def test_player_detections_drops_tiny_boxes_and_balls():
    params = replace(TEST_PARAMS, min_box_area_rel=0.001)  # 0.001 * 1000 * 1000 = 1000 px²
    dets = [
        Detection(Box(0, 0, 40, 100), 0.9, "player"),  # 4000 px²
        Detection(Box(0, 0, 10, 10), 0.9, "player"),  # 100 px²: crowd/noise
        Detection(Box(0, 0, 40, 100), 0.9, "ball"),
    ]
    assert player_detections(dets, 1000, 1000, params) == dets[:1]


def test_pick_ball_takes_highest_score():
    balls = [Detection(Box(0, 0, 5, 5), s, "ball") for s in (0.4, 0.8, 0.6)]
    assert pick_ball(balls + [Detection(Box(0, 0, 5, 5), 0.99, "player")]).score == 0.8
    assert pick_ball([]) is None


def test_tracker_params_come_from_settings():
    s = Settings(
        app_env="dev",
        app_origin="http://x",
        database_url="",
        git_sha="",
        tracker_high_thresh=0.6,
        tracker_low_thresh=0.2,
        tracker_iou_threshold=0.25,
        tracker_low_iou=0.4,
        tracker_max_age=7,
        tracker_min_hits=2,
        min_box_area_rel=0.001,
    )
    assert tracker_params(s) == TrackerParams(0.6, 0.2, 0.25, 0.4, 7, 2, 0.001)


@pytest.mark.parametrize(
    "override",
    [
        {"tracker_low_thresh": 0.6},  # low above high
        {"tracker_low_thresh": 0.0},
        {"tracker_high_thresh": 1.5},
        {"tracker_iou_threshold": 0.0},
        {"tracker_low_iou": 1.2},
        {"tracker_max_age": 0},
        {"tracker_min_hits": 0},
        {"min_box_area_rel": 1.0},
    ],
)
def test_bad_tracker_settings_rejected(override):
    s = Settings(app_env="dev", app_origin="http://x", database_url="", git_sha="", **override)
    with pytest.raises(RuntimeError, match="TRACKER|MIN_BOX"):
        validate_settings(s)
