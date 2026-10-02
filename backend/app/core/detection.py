"""YOLOX output → player/ball detections. Pure numpy: no model, no OpenCV, no I/O.

The released YOLOX ONNX models output raw grid predictions, shape (1, N, 85): per anchor
(dx, dy, log w, log h, objectness, 80 COCO class scores), objectness and class scores already
in 0..1. Anchors are laid out stride 8, then 16, then 32, row by row (YOLOX demo_postprocess).
"""

import numpy as np

from .models import Box, Detection, DetectorParams

STRIDES = (8, 16, 32)
NUM_CLASSES = 80
PERSON_CLASS_ID = 0  # COCO "person"
BALL_CLASS_ID = 32  # COCO "sports ball"
MIN_BOX_SIDE_PX = 1.0


def yolox_num_anchors(size: int) -> int:
    return sum((size // s) ** 2 for s in STRIDES)


def _grids(size: int) -> tuple[np.ndarray, np.ndarray]:
    cells, strides = [], []
    for s in STRIDES:
        n = size // s
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        cells.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), s))
    return np.concatenate(cells).astype(np.float32), np.concatenate(strides).astype(np.float32)


def decode_yolox(raw: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    """Raw (1, N, 85) output → (boxes xyxy in letterbox pixels (N, 4), class scores (N, 80))."""
    if raw.ndim != 3 or raw.shape[0] != 1 or raw.shape[2] != 5 + NUM_CLASSES:
        raise ValueError(f"unexpected YOLOX output shape {raw.shape}")
    if raw.shape[1] != yolox_num_anchors(size):
        raise ValueError(f"{raw.shape[1]} anchors, expected {yolox_num_anchors(size)} at {size}")
    pred = raw[0].astype(np.float32)  # astype copies: the caller's array is left untouched
    grid, stride = _grids(size)
    centre = (pred[:, :2] + grid) * stride
    half = np.exp(pred[:, 2:4]) * stride / 2
    boxes = np.concatenate((centre - half, centre + half), axis=1)
    scores = pred[:, 4:5] * pred[:, 5:]
    return boxes, scores


def letterbox_ratio(height: int, width: int, size: int) -> float:
    """Scale that fits a height×width frame inside the size×size model input."""
    return min(size / height, size / width)


def _iou_one_to_many(box: np.ndarray, others: np.ndarray) -> np.ndarray:
    w = np.clip(np.minimum(box[2], others[:, 2]) - np.maximum(box[0], others[:, 0]), 0, None)
    h = np.clip(np.minimum(box[3], others[:, 3]) - np.maximum(box[1], others[:, 1]), 0, None)
    inter = w * h
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    return inter / np.maximum(area + areas - inter, 1e-9)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy non-maximum suppression; returns kept indices, best score first."""
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        order = rest[_iou_one_to_many(boxes[i], boxes[rest]) <= iou_threshold]
    return keep


def _to_frame(boxes: np.ndarray, ratio: float, frame_hw: tuple[int, int]) -> np.ndarray:
    height, width = frame_hw
    out = boxes / ratio
    out[:, [0, 2]] = np.clip(out[:, [0, 2]], 0, width)
    out[:, [1, 3]] = np.clip(out[:, [1, 3]], 0, height)
    return out


def _valid(boxes: np.ndarray) -> np.ndarray:
    return ((boxes[:, 2] - boxes[:, 0]) >= MIN_BOX_SIDE_PX) & (
        (boxes[:, 3] - boxes[:, 1]) >= MIN_BOX_SIDE_PX
    )


def _detection(box: np.ndarray, score: float, cls: str) -> Detection:
    x1, y1, x2, y2 = (float(v) for v in box)
    return Detection(Box(x1, y1, x2, y2), float(score), cls)


def select_detections(
    boxes: np.ndarray,
    scores: np.ndarray,
    ratio: float,
    frame_hw: tuple[int, int],
    params: DetectorParams,
) -> list[Detection]:
    """Players (NMS, down to player_min_score) + at most one ball, in frame pixels.

    Scores are per class (objectness × class score), not argmax: a box that is 60 % "person"
    and 30 % "sports ball" can count for both, which helps the small, blurry ball.
    """
    frame_boxes = _to_frame(boxes, ratio, frame_hw)
    valid = _valid(frame_boxes)

    person = scores[:, PERSON_CLASS_ID]
    idx = np.flatnonzero(valid & (person >= params.player_min_score))
    idx = idx[np.argsort(-person[idx], kind="stable")][: params.max_candidates]
    kept = idx[nms(frame_boxes[idx], person[idx], params.nms_iou)] if idx.size else idx
    dets = [_detection(frame_boxes[i], person[i], "player") for i in kept]

    ball = scores[:, BALL_CLASS_ID]
    ball_idx = np.flatnonzero(valid & (ball >= params.ball_min_score))
    if ball_idx.size:
        best = int(ball_idx[np.argmax(ball[ball_idx])])
        dets.append(_detection(frame_boxes[best], ball[best], "ball"))
    return dets
