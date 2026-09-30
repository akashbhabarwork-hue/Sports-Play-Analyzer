---
name: player-tracking
description: Implements a pure, unit-testable ByteTrack-style multi-object tracker for players — IoU matrix, Hungarian assignment, two-stage high/low confidence association, constant-velocity prediction, tentative/confirmed/lost track lifecycle, contiguous stable IDs and fixture-based tests. Use for tracking players across frames with stable IDs.
---

# ByteTrack-style tracker (pure core)

## Idea (explain it in 30 seconds)
Each frame we have boxes from the detector. We predict where each existing track should be, then
match predictions to detections by overlap (IoU) using the Hungarian algorithm (optimal 1-to-1).
ByteTrack's trick: first match confident detections; then give leftover tracks a second chance with
low-confidence detections (often an occluded player), instead of throwing those away. Unmatched
tracks survive `TRACK_MAX_AGE` frames as "lost" so a briefly hidden player keeps their ID.
New tracks are "tentative" until seen `TRACK_MIN_HITS` times — this filters one-frame false
positives, and we only hand out a public ID on confirmation so IDs are 1..N without gaps.

## Types (core/models.py)
```python
@dataclass(frozen=True, slots=True)
class Box: x1: float; y1: float; x2: float; y2: float

@dataclass(frozen=True, slots=True)
class Detection: box: Box; score: float; cls: str          # "player" | "ball"

@dataclass(frozen=True, slots=True)
class Track:
    internal_id: int; public_id: int | None; box: Box
    vx: float; vy: float; hits: int; misses: int; state: str   # tentative|confirmed|lost

@dataclass(frozen=True, slots=True)
class TrackerParams:
    high_thresh: float; low_thresh: float; match_iou: float; low_match_iou: float
    max_age: int; min_hits: int

@dataclass(frozen=True, slots=True)
class TrackerState:
    tracks: tuple[Track, ...] = (); next_internal: int = 1; next_public: int = 1
```

## Core functions (core/tracking.py) — all pure
```python
def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:        # (N,4),(M,4) -> (N,M)
    if len(a) == 0 or len(b) == 0: return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1]); area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9)

def associate(t_boxes, d_boxes, min_iou) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    iou = iou_matrix(t_boxes, d_boxes)
    if iou.size == 0: return [], list(range(len(t_boxes))), list(range(len(d_boxes)))
    rows, cols = linear_sum_assignment(-iou)             # maximise total IoU
    matches = [(r, c) for r, c in zip(rows, cols) if iou[r, c] >= min_iou]
    mt = {r for r, _ in matches}; md = {c for _, c in matches}
    return matches, [i for i in range(len(t_boxes)) if i not in mt], [j for j in range(len(d_boxes)) if j not in md]

def predict(t: Track) -> Box: ...          # shift box by (vx, vy)

def update(state: TrackerState, dets: list[Detection], p: TrackerParams) -> tuple[TrackerState, list[Track]]:
    """One frame. Returns new state + confirmed tracks updated THIS frame."""
    # 1. split dets: high = score>=p.high_thresh, low = p.low_thresh<=score<p.high_thresh
    # 2. stage 1: all tracks (predicted boxes) vs high dets @ p.match_iou
    # 3. stage 2: unmatched confirmed/lost tracks vs low dets @ p.low_match_iou
    # 4. matched: new box = det box; velocity = EMA(0.5) of centre delta; hits+=1; misses=0;
    #    tentative with hits>=min_hits -> confirmed and gets public_id=next_public; lost -> confirmed
    # 5. unmatched tracks: misses+=1; state = lost if confirmed; drop tentative immediately
    #    (after 1 miss) and any track with misses > max_age
    # 6. unmatched HIGH dets -> new tentative tracks (low dets never start tracks)
```
Players only — the ball is not tracked with this (one ball, pick highest score per frame).
Ignore tiny boxes (`MIN_BOX_AREA_REL`, e.g. 0.0005 of frame area) and optionally audience/bench by
a crude y-band later (BONUS).

## Fixture-driven tests (backend/tests/fixtures/tracks_*.json)
Format: `{"frames": [[{"box":[x1,y1,x2,y2],"score":0.9,"cls":"player"}, ...], ...]}`.
Must-have cases:
1. `test_single_player_keeps_id_while_moving` — box moves 5 px/frame for 20 frames → one public id.
2. `test_track_id_stable_when_player_briefly_occluded` — missing for 3 frames (< max_age) → same id.
3. `test_track_dropped_after_max_age` — missing max_age+1 frames → new id when reappearing.
4. `test_low_confidence_detection_keeps_track_alive` — score 0.3 in middle frames (ByteTrack stage 2).
5. `test_two_players_crossing_keep_ids` — linear paths crossing; velocity prediction keeps ids.
6. `test_one_frame_false_positive_never_confirmed` — lone detection → no public id.
7. `test_public_ids_are_contiguous` — 3 players appear at different times → ids 1,2,3.
8. `iou_matrix` table tests: identical=1, disjoint=0, half-overlap=1/3, empty inputs.
Tests call `update` in a loop — no model, no video, milliseconds.

## Known limits (ADR)
IoU-only association struggles with fast motion at low SAMPLE_FPS and with identical kits
crossing; ID switches happen. More time: Kalman filter + appearance embedding (DeepSORT/BoT-SORT),
or higher sample fps.
