import math

import numpy as np
import pytest

from app.core.detection import (
    decode_yolox,
    letterbox_ratio,
    nms,
    select_detections,
    yolox_num_anchors,
)
from app.core.models import Box, DetectorParams

PARAMS = DetectorParams(
    input_size=64, player_min_score=0.1, ball_min_score=0.15, nms_iou=0.45, max_candidates=300
)
PERSON, BALL = 0, 32


def raw_output(size=64, cells=()):
    """A fake raw YOLOX output: every anchor zero-scored except `cells`.

    cells: (anchor_index, dx, dy, log_w, log_h, objectness, class_id, class_score)
    """
    out = np.zeros((1, yolox_num_anchors(size), 85), np.float32)
    for idx, dx, dy, lw, lh, obj, cls_id, cls_score in cells:
        out[0, idx, :5] = (dx, dy, lw, lh, obj)
        out[0, idx, 5 + cls_id] = cls_score
    return out


# ---- decode ----


def test_num_anchors_matches_real_yolox_s_at_640():
    assert yolox_num_anchors(640) == 8400  # 80² + 40² + 20², what the real model returns


def test_decode_first_stride8_cell_maps_to_pixels():
    # Anchor 0 = grid (0, 0) at stride 8. Offset (0.5, 0.5) → centre (4, 4); log size 0 → 8 px.
    out = raw_output(cells=[(0, 0.5, 0.5, 0.0, 0.0, 0.9, PERSON, 0.8)])
    boxes, scores = decode_yolox(out, 64)
    assert boxes[0] == pytest.approx([0, 0, 8, 8])
    assert scores[0, PERSON] == pytest.approx(0.72)


def test_decode_uses_grid_position_and_stride_of_later_levels():
    # size 64: stride 8 has 8×8=64 anchors, stride 16 has 4×4=16. Anchor 64+5 = (x=1, y=1) @16.
    out = raw_output(cells=[(69, 0.0, 0.0, math.log(2), 0.0, 1.0, PERSON, 1.0)])
    boxes, _ = decode_yolox(out, 64)
    assert boxes[69] == pytest.approx([16 - 16, 16 - 8, 16 + 16, 16 + 8])  # w=32, h=16


def test_decode_rejects_unexpected_shape():
    with pytest.raises(ValueError):
        decode_yolox(np.zeros((1, 10, 85), np.float32), 64)
    with pytest.raises(ValueError):
        decode_yolox(np.zeros((1, yolox_num_anchors(64), 84), np.float32), 64)


def test_decode_does_not_modify_input():
    out = raw_output(cells=[(0, 0.5, 0.5, 0.0, 0.0, 0.9, PERSON, 0.8)])
    before = out.copy()
    decode_yolox(out, 64)
    assert np.array_equal(out, before)


# ---- letterbox ratio ----


def test_letterbox_ratio_fits_long_side():
    assert letterbox_ratio(720, 1280, 640) == pytest.approx(0.5)
    assert letterbox_ratio(1280, 720, 640) == pytest.approx(0.5)
    assert letterbox_ratio(320, 320, 640) == pytest.approx(2.0)


# ---- nms ----


def test_nms_drops_overlapping_lower_score_box():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], np.float32)
    scores = np.array([0.9, 0.8, 0.7], np.float32)
    assert nms(boxes, scores, 0.45) == [0, 2]


def test_nms_keeps_touching_but_separate_players():
    boxes = np.array([[0, 0, 10, 20], [8, 0, 18, 20]], np.float32)  # IoU = 2/18 ≈ 0.11
    assert sorted(nms(boxes, np.array([0.6, 0.9], np.float32), 0.45)) == [0, 1]


def test_nms_orders_by_score():
    boxes = np.array([[0, 0, 10, 10], [0, 0, 10, 10]], np.float32)
    assert nms(boxes, np.array([0.3, 0.9], np.float32), 0.45) == [1]


def test_nms_empty():
    assert nms(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32), 0.45) == []


# ---- select_detections ----


def scored(n, rows):
    """boxes (n,4) at letterbox scale and scores (n,80); rows: (i, box, cls_id, score)."""
    boxes = np.zeros((n, 4), np.float32)
    scores = np.zeros((n, 80), np.float32)
    for i, box, cls_id, score in rows:
        boxes[i] = box
        scores[i, cls_id] = score
    return boxes, scores


def test_select_keeps_low_score_players_for_tracker_stage_two():
    boxes, scores = scored(3, [(0, [0, 0, 10, 20], PERSON, 0.9),
                               (1, [30, 0, 40, 20], PERSON, 0.12),
                               (2, [60, 0, 70, 20], PERSON, 0.05)])  # fmt: skip
    dets = select_detections(boxes, scores, 1.0, (100, 100), PARAMS)
    assert [round(d.score, 2) for d in dets] == [0.9, 0.12]
    assert all(d.cls == "player" for d in dets)


def test_select_keeps_only_the_best_ball():
    boxes, scores = scored(3, [(0, [0, 0, 4, 4], BALL, 0.3),
                               (1, [50, 50, 54, 54], BALL, 0.6),
                               (2, [80, 80, 84, 84], BALL, 0.1)])  # fmt: skip
    dets = select_detections(boxes, scores, 1.0, (100, 100), PARAMS)
    assert [(d.cls, round(d.score, 2)) for d in dets] == [("ball", 0.6)]
    assert dets[0].box == Box(50, 50, 54, 54)


def test_select_ignores_other_coco_classes():
    boxes, scores = scored(1, [(0, [0, 0, 10, 10], 2, 0.99)])  # 2 = car
    assert select_detections(boxes, scores, 1.0, (100, 100), PARAMS) == []


def test_select_rescales_by_letterbox_ratio_and_clips_to_frame():
    boxes, scores = scored(1, [(0, [10, 20, 300, 40], PERSON, 0.9)])
    (det,) = select_detections(boxes, scores, 0.5, (100, 200), PARAMS)  # frame h=100, w=200
    assert det.box == Box(20, 40, 200, 80)  # x2 600 clipped to width 200


def test_select_applies_nms_to_players():
    boxes, scores = scored(2, [(0, [0, 0, 10, 20], PERSON, 0.9),
                               (1, [1, 0, 11, 20], PERSON, 0.8)])  # fmt: skip
    assert len(select_detections(boxes, scores, 1.0, (100, 100), PARAMS)) == 1


def test_select_caps_candidates_before_nms():
    n = 50
    boxes = np.array([[i * 20, 0, i * 20 + 10, 20] for i in range(n)], np.float32)
    scores = np.zeros((n, 80), np.float32)
    scores[:, PERSON] = np.linspace(0.2, 0.9, n)
    params = DetectorParams(64, 0.1, 0.15, 0.45, max_candidates=5)
    dets = select_detections(boxes, scores, 1.0, (100, 2000), params)
    assert len(dets) == 5 and min(d.score for d in dets) > 0.8


def test_select_drops_degenerate_boxes():
    boxes, scores = scored(1, [(0, [500, 500, 600, 600], PERSON, 0.9)])  # entirely off-frame
    assert select_detections(boxes, scores, 1.0, (100, 100), PARAMS) == []
