"""ByteTrack-style player tracker. Pure: boxes in, tracks out, no frames or models.

Each sampled frame: predict every track's box from its velocity, match confident detections to
the predictions by IoU (Hungarian, optimal 1-to-1), then give the leftover confirmed/lost tracks a
second chance with low-confidence detections (often a partly hidden player). Unmatched tracks
stay "lost" for up to `max_age` frames so a briefly hidden player keeps their id. New tracks are
"tentative" until seen `min_hits` times; only then do they get a public id, so ids are 1..N.
"""

from dataclasses import replace

import numpy as np
from scipy.optimize import linear_sum_assignment

from .models import Box, Detection, Track, TrackerParams, TrackerState

VELOCITY_SMOOTHING = 0.5  # EMA weight of the newest centre step


def boxes_array(boxes: list[Box]) -> np.ndarray:
    return np.array([[b.x1, b.y1, b.x2, b.y2] for b in boxes], dtype=float).reshape(-1, 4)


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU of every box in `a` (N,4) against every box in `b` (M,4) -> (N,M)."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)


def associate(
    t_boxes: np.ndarray, d_boxes: np.ndarray, min_iou: float
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Optimal 1-to-1 matching maximising total IoU; pairs below `min_iou` are rejected.

    Returns (matches as (track_idx, det_idx), unmatched track idxs, unmatched det idxs).
    """
    iou = iou_matrix(t_boxes, d_boxes)
    if iou.size == 0:
        return [], list(range(len(t_boxes))), list(range(len(d_boxes)))
    rows, cols = linear_sum_assignment(-iou)
    matches = [(int(r), int(c)) for r, c in zip(rows, cols) if iou[r, c] >= min_iou]
    matched_t = {r for r, _ in matches}
    matched_d = {c for _, c in matches}
    return (
        matches,
        [i for i in range(len(t_boxes)) if i not in matched_t],
        [j for j in range(len(d_boxes)) if j not in matched_d],
    )


def predict(track: Track) -> Box:
    """Where the track should be this frame: last box moved by velocity × frames elapsed."""
    steps = track.misses + 1
    dx, dy = track.vx * steps, track.vy * steps
    b = track.box
    return Box(b.x1 + dx, b.y1 + dy, b.x2 + dx, b.y2 + dy)


def centre(box: Box) -> tuple[float, float]:
    return (box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2


def box_area(box: Box) -> float:
    return max(box.x2 - box.x1, 0.0) * max(box.y2 - box.y1, 0.0)


def player_detections(
    dets: list[Detection], frame_w: int, frame_h: int, params: TrackerParams
) -> list[Detection]:
    """Players only, dropping boxes smaller than `min_box_area_rel` of the frame."""
    min_area = params.min_box_area_rel * frame_w * frame_h
    return [d for d in dets if d.cls == "player" and box_area(d.box) >= min_area]


def pick_ball(dets: list[Detection]) -> Detection | None:
    """There is one ball: keep the highest-scoring ball detection, if any."""
    balls = [d for d in dets if d.cls == "ball"]
    return max(balls, key=lambda d: d.score, default=None)


def _matched(track: Track, det: Detection) -> Track:
    steps = track.misses + 1
    (ox, oy), (nx, ny) = centre(track.box), centre(det.box)
    a = VELOCITY_SMOOTHING
    state = "tentative" if track.state == "tentative" else "confirmed"
    return replace(
        track,
        box=det.box,
        vx=(1 - a) * track.vx + a * (nx - ox) / steps,
        vy=(1 - a) * track.vy + a * (ny - oy) / steps,
        hits=track.hits + 1,
        misses=0,
        state=state,
    )


def update(
    state: TrackerState, dets: list[Detection], p: TrackerParams
) -> tuple[TrackerState, list[Track]]:
    """Advance one sampled frame. Returns the new state and the confirmed tracks matched in
    THIS frame (sorted by public id). Non-player detections are ignored."""
    players = [d for d in dets if d.cls == "player"]
    high = [d for d in players if d.score >= p.high_thresh]
    low = [d for d in players if p.low_thresh <= d.score < p.high_thresh]
    tracks = list(state.tracks)
    predicted = boxes_array([predict(t) for t in tracks])

    # Stage 1: every track vs confident detections.
    matches, left_t, left_high = associate(
        predicted, boxes_array([d.box for d in high]), p.match_iou
    )
    updated: dict[int, Track] = {ti: _matched(tracks[ti], high[di]) for ti, di in matches}

    # Stage 2: leftover established tracks vs low-confidence detections. Tentative tracks do
    # not get a second chance, so a weak one-off box cannot grow into a track.
    second = [ti for ti in left_t if tracks[ti].state != "tentative"]
    matches2, _, _ = associate(
        predicted[second], boxes_array([d.box for d in low]), p.low_match_iou
    )
    for si, di in matches2:
        updated[second[si]] = _matched(tracks[second[si]], low[di])

    next_internal, next_public = state.next_internal, state.next_public
    survivors: list[Track] = []
    for i, track in enumerate(tracks):
        if i in updated:
            t = updated[i]
        elif track.state == "tentative":
            continue  # a tentative track that misses once was probably a false positive
        else:
            t = replace(track, misses=track.misses + 1, state="lost")
            if t.misses > p.max_age:
                continue
        survivors.append(t)

    # Unmatched confident detections start new tentative tracks; low ones never do.
    for di in left_high:
        survivors.append(
            Track(next_internal, None, high[di].box, 0.0, 0.0, hits=1, misses=0, state="tentative")
        )
        next_internal += 1

    # Promote in creation order so public ids follow first appearance.
    final: list[Track] = []
    for t in survivors:
        if t.state == "tentative" and t.hits >= p.min_hits:
            t = replace(t, state="confirmed", public_id=next_public)
            next_public += 1
        final.append(t)

    seen_now = sorted(
        (t for t in final if t.state == "confirmed" and t.misses == 0),
        key=lambda t: t.public_id or 0,
    )
    return TrackerState(tuple(final), next_internal, next_public), seen_now
