---
trigger: model_decision
description: Apply when working on the worker, video decoding/encoding, frame sampling, object detection, player tracking, metrics (distance, heatmaps, possession, ball visibility, teams), annotated video rendering or the stats JSON.
---

# Computer-vision pipeline rules

Deep guides: skills `ffmpeg-frame-streaming`, `object-detection-onnx`, `player-tracking`,
`sports-metrics`.

## Pipeline shape (one pass, streamed)
```
ffprobe → ffmpeg decode (-vf fps=SAMPLE_FPS, scale) → raw BGR frames on stdout pipe
   → for each frame: detect → split players/ball → tracker.update → accumulate metrics
   → draw boxes+IDs → write raw frame to ffmpeg encoder stdin (H.264, yuv420p, +faststart)
→ finalize metrics → persist (single transaction) → upload annotated.mp4 → mark succeeded
```
- Read exactly `width*height*3` bytes per frame; never load the whole video. Memory must stay flat.
- Update progress every N frames: `progress = frames_done / expected_frames` (expected from
  ffprobe duration × SAMPLE_FPS), capped at 99 until persisted.

## Purity boundary
- Detector is an adapter (`Detector` Protocol → `list[Detection]`). Everything after detection
  (tracker, metrics, heatmaps, possession, team clustering) is pure in `core/` and testable with
  fixture detections from `backend/tests/fixtures/*.json`.
- Frame drawing uses OpenCV in an adapter/service, not in core.

## Config-driven (env vars via config.py)
`SAMPLE_FPS, DETECT_CONF, DETECT_IOU_NMS, DETECT_INPUT_SIZE, PERSON_CLASS_ID, BALL_CLASS_ID,
TRACK_HIGH_THRESH, TRACK_LOW_THRESH, TRACK_MATCH_IOU, TRACK_MAX_AGE, TRACK_MIN_HITS,
POSSESSION_DIST_RATIO, POSSESSION_MIN_FRAMES, HEATMAP_GRID_W, HEATMAP_GRID_H, JITTER_PX,
MAX_VIDEO_SECONDS, MAX_UPLOAD_MB`. Snapshot the effective values into `jobs.config` JSON so
results are reproducible.

## Metric definitions (keep consistent everywhere; document in ADR)
- Anchor point of a player = bottom-centre of the box (feet).
- Distance = Σ step lengths of the anchor across consecutive confirmed observations, ignoring steps
  < `JITTER_PX`; reported in px and normalised by frame diagonal (`distance_rel`).
- Players tracked = number of confirmed tracks with ≥ `TRACK_MIN_HITS` hits.
- Heatmap = `HEATMAP_GRID_W × HEATMAP_GRID_H` histogram of anchor positions in normalised coords,
  per player and per team; stored as integer counts + max.
- Ball visible % = sampled frames with ≥1 ball detection / sampled frames × 100.
- Possession: per frame, nearest confirmed player to ball centre if distance ≤
  `POSSESSION_DIST_RATIO × player box height`; a player needs `POSSESSION_MIN_FRAMES` consecutive
  frames to take possession. Report % of ball-visible frames per player and "unassigned".
- Teams: k-means (k=2) on torso colour (HSV) per track; label `A`/`B`; if unreliable, `unknown`.

## Failure codes (worker → jobs.error_code)
`CORRUPT_FILE, UNSUPPORTED_FORMAT, DURATION_EXCEEDED, YOUTUBE_BLOCKED, URL_NOT_ALLOWED,
DOWNLOAD_FAILED, DECODE_ERROR, MODEL_ERROR, WORKER_CRASHED, INTERNAL`. Message must be human
readable and suggest the fix (e.g. "YouTube blocked our server, please upload the file instead").
