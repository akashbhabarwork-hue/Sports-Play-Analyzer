---
name: sports-metrics
description: Computes tactical metrics from tracks as pure functions — players tracked, per-player distance in pixels and frame-relative units with jitter filtering, per-player and per-team heatmap grids, ball-visible percentage, ball-near-player possession with hysteresis, k-means team split by jersey colour, the stats JSON contract, and optional homography for pitch-normalised distance. Use when implementing or testing metrics, heatmaps, possession or the stats/players API payloads.
---

# Sports metrics (pure core, tested with fixtures)

## Accumulator pattern
`MetricsState` (frozen) updated per frame via `accumulate(state, frame_idx, t_s, confirmed_tracks,
ball, frame_w, frame_h, params) -> MetricsState`; `finalize(state) -> JobStats`. Tuples/dicts
replaced functionally; fine for ≤300 frames × ≤30 players.
(If profiling shows it's slow, a mutable accumulator *inside the service* is acceptable — record it.)

## Definitions
- **Anchor** = feet point `((x1+x2)/2, y2)`; store normalised `(x/W, y/H)` for tracks/heatmaps.
- **Distance**: per track, sum of Euclidean distance between consecutive anchors in pixels,
  skipping steps < `JITTER_PX` (detector wobble) and steps across gaps > `TRACK_MAX_AGE` frames.
  `distance_rel = distance_px / hypot(W, H)` → "fraction of the frame diagonal"; 1.0 ≈ crossed the
  screen corner to corner. Camera pans inflate/deflate this — state in ADR.
- **Players tracked** = confirmed tracks with `hits >= TRACK_MIN_HITS`.
- **Heatmap**: grid `HEATMAP_GRID_W × HEATMAP_GRID_H` (default 32×18). Cell =
  `(min(int(nx*GW), GW-1), min(int(ny*GH), GH-1))`. Store `counts` as flat list row-major + `max`.
  Team heatmap = sum of member players' grids; also "all players".
- **Ball visible %** = frames with a ball detection / sampled frames × 100 (1 decimal).
- **Possession** (per frame with ball): candidate = confirmed player minimising distance from
  ball centre to player feet point; valid if `dist <= POSSESSION_DIST_RATIO * player_box_height`.
  Hysteresis: candidate becomes owner only after `POSSESSION_MIN_FRAMES` consecutive frames;
  owner keeps possession while ball not visible for ≤ 2 frames. Output per player
  `possession_pct` of ball-visible frames, plus `unassigned_pct`, plus team totals.
- **Teams**: for each confirmed track sample up to 10 torso crops (middle 40 % width, 20–50 %
  height of box), compute median HSV hue/sat → feature; k-means k=2 (numpy, fixed seed, 20 iters).
  If cluster centres are closer than `TEAM_MIN_SEPARATION`, label all `unknown`. Referee/goalie
  mislabels are expected — ADR note. (Crop extraction = adapter; clustering = pure core.)

## Stats JSON contract (GET /api/jobs/{id}/stats)
```json
{
  "job_id": "…", "video": {"duration_s": 42.1, "width": 1280, "height": 720, "sample_fps": 5},
  "players_tracked": 14,
  "ball_visible_pct": 37.5,
  "possession": {"by_player": [{"player_id": 3, "pct": 22.0}], "by_team": {"A": 55.0, "B": 30.0},
                 "unassigned_pct": 15.0},
  "players": [{"player_id": 3, "team": "A", "distance_px": 1834.2, "distance_rel": 1.24,
               "frames_visible": 180, "possession_pct": 22.0}],
  "teams": {"A": {"players": [1,3,5], "distance_rel_total": 8.1}, "B": {…}},
  "config": {"sample_fps": 5, "detect_conf": 0.35, "...": "…"}
}
```
`GET /api/jobs/{id}/players/{pid}` → `{player_id, team, distance_px, distance_rel,
possession_pct, track: [[t_s, nx, ny], …], heatmap: {w, h, counts, max}}`.
`GET /api/jobs/{id}/heatmap?team=A|B|all` → `{w, h, counts, max}`.

## Tests (fixtures, no model)
- Straight line 10 steps of 10 px → 100 px; add ±1 px jitter with JITTER_PX=2 → still ~100 px.
- Gap longer than max_age → distance not bridged.
- Heatmap edge cases: nx=1.0 lands in last column; totals equal number of observations.
- Ball visible: 3 of 12 frames → 25.0.
- Possession hysteresis: ball near P1 for 1 frame then P2 for 5 → P1 never owns (min_frames=3).
- k-means: two synthetic colour blobs → two labels; identical colours → `unknown`.

## BONUS: pitch-normalised distance (homography)
User clicks 4 known pitch points on the first frame in the UI (e.g. penalty box corners) and
enters real dimensions → backend `cv2.findHomography` (adapter) → store `H` in `jobs.config`;
pure `apply_homography(H, pts)` in core → distance in metres. Only valid for a static camera or
per-shot calibration; state that limit.
