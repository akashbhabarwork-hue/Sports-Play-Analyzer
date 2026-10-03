---
trigger: glob
globs: backend/tests/**
---

# Testing rules

Deep guide: skill `testing-strategy`.

- `backend/tests/unit/`: no DB, no network, no model, no ffmpeg. Tracker, IoU, distance, heatmap,
  possession, team clustering, URL/IP validation, magic-byte sniffing, config parsing. Fast (<5 s).
- Fixture detections live in `backend/tests/fixtures/*.json` (hand-made, tiny, deterministic).
- `backend/tests/integration/`: real Postgres (docker compose / CI service). Cover at least:
  submit → claim → process (with a `FakeDetector`) → results; crash-mid-job retry idempotency;
  SKIP LOCKED two-worker claim.
- Authorization test (required): user A creates a job; user B gets 404 on `/api/jobs/{id}`,
  `/stats`, `/players/{pid}`, video endpoint, and A's job is absent from B's list.
- Tests create users/sessions directly through repositories, never real Google login.
- Every bug fix gets a regression test first.
- Name tests by behaviour: `test_track_id_stable_when_player_briefly_occluded`.
- Run: `pytest -q backend/tests/unit` (every change) and `pytest -q backend/tests/integration`
  (before commit on DB/worker/API tickets).
