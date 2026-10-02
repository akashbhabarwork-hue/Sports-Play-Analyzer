# Stage S05 — Tracking & metrics core (pure, no model)

**Dates:** 2026-10-02 → 2026-10-02 · **Tickets:** T-050, T-051, T-052

## What was built (plain English)
- A player tracker that follows each player from frame to frame and gives them a stable number. It predicts where everyone should be, matches the detector's boxes to those predictions, and keeps a briefly hidden player's number for up to 2 seconds. Numbers are handed out only after three sightings, so they run 1, 2, 3… with no gaps and one-frame false alarms never appear.
- Match metrics computed from what the tracker saw: distance covered per player (ignoring detector wobble), position heatmaps per player, per team and for everyone, how often the ball was visible, and ball possession, which only changes hands after the ball stays with a new player for three frames in a row.
- A team split by shirt colour: a small crop of each player's torso is reduced to one colour value, and the players are divided into two groups. If the two kits look too alike, everyone is labelled `unknown` instead of guessing.
- All of it is pure code (numpy/scipy maths, no video, no model, no database), tested in milliseconds with hand-built detections and synthetic frames.

## How it works now (data flow for this stage)
```mermaid
sequenceDiagram
  participant P as Pipeline (T-062)
  participant T as core/tracking.py
  participant C as core/teams.py
  participant M as core/metrics.py
  loop every sampled frame
    P->>T: update(state, detections) — players only, tiny boxes dropped
    T-->>P: confirmed tracks seen this frame (ids 1..N)
    P->>P: pick_ball(detections); append FrameObservation
    P->>C: colour_feature(torso_pixels(frame, box)) for a few frames per track
  end
  P->>C: assign_teams(samples) → {id: A | B | unknown}
  P->>M: build_stats(job_id, observations, W, H, params, teams)
  M-->>P: stats JSON + player_tracks rows (track, heatmap, distance, possession)
```

## Key decisions (and why)
| ID | Decision | Why | Alternative rejected |
|---|---|---|---|
| D-021 | ByteTrack-style tracker: velocity prediction, Hungarian (scipy) matching, low-confidence boxes only extend established tracks; `TRACKER_MAX_AGE` 10 | Stable ids through brief occlusion without a re-ID network; 30 frames at 5 fps (6 s) would let predictions drift onto other players | Greedy matching (a test shows it picks a worse pairing); DeepSORT (too heavy for CPU) |
| D-022 | Metrics computed in one pass over per-frame observations; jitter dead-band from the last counted point; loose ball is a possession candidate | Plain, separately tested functions; slow walkers keep their distance; a short pass doesn't reset possession | Frozen accumulator rebuilt every frame; dropping every short step |
| D-023 | Team colour = median `(s·cos h, s·sin h, v)` of torso crops; deterministic 2-means; `unknown` below a separation | Red hue wrap and white-vs-black kits both work; labels never flip between runs | Raw hue/saturation (splits red teams, merges white and black); random k-means start |

## How to demo / verify
```bash
cd backend
pytest -q tests/unit -k "track or metric or heatmap or possession or team"   # ~80 tests, ~2 s
python tests/fixtures/make_track_fixtures.py   # regenerates tracks_*.json (no diff expected)
```

## Tests added
- `tests/unit/test_tracking.py` (33): moving player keeps id, brief occlusion, drop after max age (and kept at exactly max age), low-confidence boxes keep but never start or grow tracks, two players crossing, one-frame false positive, contiguous ids, IoU table, optimal-not-greedy matching, settings.
- `tests/unit/test_metrics.py` (33): 100 px line, jitter, standing wobble = 0, slow walker, gaps, heatmap edges/totals/row-major, ball 3/12 = 25.0, possession hysteresis, short pass, ball gaps, stats contract, rows, empty video, settings.
- `tests/unit/test_teams.py` (15): two kits, identical kits → unknown, white vs black, red hue wrap, deterministic labels, too few players, separation threshold, minority pixels and garbage samples, crop clamping, team heatmap = sum of members.
- 23 mutations across the three modules, every one caught (three only after a test was added).

## AI corrections during this stage
- The skill's literal jitter rule ("skip steps under JITTER_PX") would give a slow-walking player zero distance — replaced with a dead-band measured from the last counted point.
- The skill's team feature (hue and saturation only) cannot separate white from black kits, and raw hue splits reds at 359°/1° — switched to the HSV cone with value.
- Mutation runs exposed three missing tests: low-confidence boxes feeding a tentative track, and median-vs-mean robustness at crop and track level.
- Two of my own test fixtures had wrong arithmetic (a "bridged" step that didn't move; a torso crop entirely outside the frame) and were fixed so the tests assert the intended behaviour.

## Known gaps / tech debt
- Nothing calls this code yet: the detector (T-061) and `process_job` (T-062) wire it to real frames.
- T-061 must keep player boxes down to `TRACKER_LOW_THRESH` (0.1), not drop them at `CONF_THRESHOLD`, or tracker stage 2 never runs.
- IoU-only tracking can swap ids when identical kits cross; distances are in pixels, not metres (homography is BONUS); referees and goalkeepers get a team.

## Interview prep — questions you may get about this stage
1. Q: How does the tracker keep a player's id when they are briefly hidden?
   A: An unmatched confirmed track becomes "lost" instead of being deleted, and its box keeps being predicted forward by its velocity (`predict` in `core/tracking.py`). If a box matches within `TRACKER_MAX_AGE` (10 sampled frames, 2 s), the same id continues; after that the track is dropped and a returning player gets a new id.
2. Q: What is the "ByteTrack" part?
   A: Two matching stages. Confident boxes are matched first; then leftover established tracks get a second chance against low-confidence boxes, which are often partly hidden players. Low boxes never start a track or grow a tentative one, so they can't create false players.
3. Q: Why Hungarian matching instead of greedy?
   A: Greedy gives each track its best box in turn and can leave a later track with nothing; Hungarian maximises total IoU over all pairs. `test_associate_is_optimal_not_greedy` is a case where greedy is wrong.
4. Q: How is possession decided, and why the hysteresis?
   A: Per frame, the nearest player's feet within half a box height of the ball is the candidate. The owner only changes when the same candidate (or "loose ball") wins three frames in a row, so a ball rolling past someone doesn't hand them possession, and a short pass stays with the passer. Percentages are of frames where the ball is visible.
5. Q: How are teams found without training?
   A: Torso crops are reduced to the median colour in the HSV cone, `(s·cos h, s·sin h, v)`, and split with two-cluster k-means started from the lowest-id player and the colour farthest from it. If the two centres are closer than `TEAM_MIN_SEPARATION`, the kits are indistinguishable and everyone is `unknown`.
